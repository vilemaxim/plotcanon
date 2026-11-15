"""The `plotcanon` command.

    plotcanon validate                  # the World in the current directory
    plotcanon validate canon/npcs/x.md  # report only on these paths
    plotcanon validate --strict         # treat warnings as errors
    plotcanon validate --quiet          # findings only, no summary
    plotcanon pov varen-ashcroft        # everything canon records about one entity
    plotcanon schema --write schema/    # copy the schema docs into a World
    plotcanon sample --write demo/      # copy the sample World to disk
    plotcanon words README.md docs/     # check wording against the glossary

Every command takes `--root DIR` to work on a World somewhere else. Paths given
to `validate` are relative to where you are; paths given to `words`, `--write`
and `--script` are relative to the root.

Exit codes: 0 clean, 1 the World has problems, 2 the command could not run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from importlib import resources
from pathlib import Path

from . import _pov
from ._wording import find_avoided
from ._api import (
    Finding, WARNING, load_world, read_directory, sample_script, sample_world, schema_files,
)

VOCAB_FILE = "vocabularies.yml"

# Exit codes: 0 clean, 1 the World has problems, 2 the command could not run.
COULD_NOT_RUN = 2


class UsageError(Exception):
    """The command was asked for something it cannot do."""


def head_commit(root):
    """The World's current git commit, or None if it is not in git."""
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def stale_schema_copy(root):
    """A World may keep a copy of the schema docs for people and agents to read.
    Warn when that copy is not the one this version of the package validates
    against, because then the docs describe rules that are not being applied."""
    copy = root / "schema"
    if not (copy / VOCAB_FILE).exists():
        return []
    refresh = "refresh the copy with `plotcanon schema --write schema/`"
    stale = []
    for name, shipped in schema_files().items():
        path = copy / name
        if not path.exists():
            stale.append(Finding(WARNING, f"schema/{name}",
                                 f"is missing from this copy of the schema — {refresh}"))
        elif path.read_text(encoding="utf-8") != shipped:
            stale.append(Finding(WARNING, f"schema/{name}",
                                 "differs from the schema this version of plotcanon "
                                 f"validates against — {refresh}"))
    return stale


def validate(args):
    root = Path(args.root).resolve()

    # Work out which files to report on before doing any work, so that a
    # mistyped path is an error and not a clean bill of health.
    wanted = set()
    for given in args.paths:
        path = Path(given).resolve()
        if not path.is_file() or not path.is_relative_to(root):
            raise UsageError(f"{given} is not a file in the World at {root}")
        wanted.add(path.relative_to(root).as_posix())

    report = load_world(root, head=head_commit(root))
    errors = list(report.errors)
    warnings = list(report.warnings) + stale_schema_copy(root)

    # Restrict reporting to the requested paths, but only after the whole World
    # has been checked — reference checks are meaningless on one file alone.
    if wanted:
        errors = [x for x in errors if x.path in wanted]
        warnings = [x for x in warnings if x.path in wanted]

    for finding in errors + warnings:
        print(finding)

    failed = bool(errors) or (args.strict and bool(warnings))
    if not args.quiet:
        print(f"\n{report.document_count} documents · {len(errors)} errors · "
              f"{len(warnings)} warnings")
        if not failed and not warnings:
            print("canon is clean")
    return 1 if failed else 0


def pov(args):
    root = Path(args.root).resolve()
    head = head_commit(root)
    try:
        subject, items, backlinks, by_id = _pov.build(read_directory(root), args.entity_id)
    except _pov.NoSuchEntity as e:
        print(e, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({
            "entity": {"id": subject.id, "type": subject.type,
                       "path": subject.rel, "frontmatter": subject.fm},
            "generated_from_commit": head or "unknown",
            "chronology": items,
            "backlinks": backlinks,
        }, indent=2, default=str))
    else:
        print("\n".join(_pov.emit_markdown(subject, items, backlinks, by_id, head, [])))
    return 0


def schema(args):
    files = schema_files()
    if args.write is None:
        for name in files:
            print(name)
        return 0
    target = Path(args.root) / args.write
    target.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (target / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} schema files to {target}/")
    return 0


def write_into_empty(target, files):
    """Write `{relative path: text}` under a folder, which must not already
    hold anything."""
    if target.exists() and any(target.iterdir()):
        raise UsageError(f"{target} is not empty; choose a new folder for the sample")
    for path, text in files.items():
        (target / path).parent.mkdir(parents=True, exist_ok=True)
        (target / path).write_text(text, encoding="utf-8")


def sample(args):
    """Copy the sample World to disk, and optionally its scripted reports."""
    world = Path(args.root) / args.write
    write_into_empty(world, sample_world())
    print(f"wrote the sample World to {world}/")
    if args.script:
        script = Path(args.root) / args.script
        scripted = {report.path: report.text for report in sample_script()}
        scripted["script.yml"] = (resources.files("plotcanon")
                                  .joinpath("sample", "script.yml").read_text(encoding="utf-8"))
        write_into_empty(script, scripted)
        print(f"wrote {len(scripted) - 1} scripted reports and script.yml to {script}/")
    return 0


def words(args):
    """Check files for words the glossary says to avoid. Paths are relative to
    the root; a folder is searched for markdown files."""
    root = Path(args.root).resolve()
    files = []
    for given in args.paths:
        path = (root / given).resolve()
        if not path.is_relative_to(root) or not path.exists():
            raise UsageError(f"{given} is not a file or folder under {root}")
        for file in (sorted(path.rglob("*.md")) if path.is_dir() else [path]):
            if file not in files:
                files.append(file)
    found = 0
    for path in files:
        name = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise UsageError(f"{name} is not UTF-8 text") from None
        for start, word, use in find_avoided(text):
            line = text.count("\n", 0, start) + 1
            print(f"{name}:{line}: {word!r} (use {use})")
            found += 1
    return 1 if found else 0


def main(argv=None):
    from . import __version__

    ap = argparse.ArgumentParser(prog="plotcanon", description="Validate and query a World's canon files.")
    ap.add_argument("--version", action="version", version=f"plotcanon {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="validate the World")
    v.add_argument("paths", nargs="*", help="report only on these paths")
    v.add_argument("--strict", action="store_true", help="treat warnings as errors")
    v.add_argument("--quiet", action="store_true", help="findings only, no summary")
    v.set_defaults(run=validate)

    p = sub.add_parser("pov", help="everything canon records about one entity")
    p.add_argument("entity_id")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(run=pov)

    s = sub.add_parser("schema", help="list the schema files, or copy them somewhere")
    s.add_argument("--write", metavar="DIR", help="write the schema files into DIR")
    s.set_defaults(run=schema)

    d = sub.add_parser("sample", help="copy the sample World to disk")
    d.add_argument("--write", metavar="DIR", required=True,
                   help="a new or empty folder for the sample World")
    d.add_argument("--script", metavar="DIR",
                   help="also write the scripted reports, into this new or empty folder")
    d.set_defaults(run=sample)

    w = sub.add_parser("words", help="check files for words the glossary says to avoid")
    w.add_argument("paths", nargs="+", help="files, or folders to search for markdown")
    w.set_defaults(run=words)

    for parser in (v, p, s, d, w):
        parser.add_argument("--root", default=".", help="the World's directory (default: here)")

    args = ap.parse_args(argv)
    try:
        return args.run(args)
    except (UsageError, NotADirectoryError, ValueError) as e:
        print(f"plotcanon: {e}", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    sys.exit(main())
