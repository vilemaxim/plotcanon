"""The `plotcanon` command.

    plotcanon validate                  # the World in the current directory
    plotcanon validate canon/npcs/x.md  # report only on these paths
    plotcanon validate --strict         # treat warnings as errors
    plotcanon validate --quiet          # findings only, no summary
    plotcanon pov varen-ashcroft        # everything canon records about one entity
    plotcanon schema --write schema/    # copy the schema docs into a World

Every command takes `--root DIR` to work on a World somewhere else. Paths given
to `validate` are relative to where you are; `--write` is relative to the root.

Exit codes: 0 clean, 1 the World has problems, 2 the command could not run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import _pov
from ._api import Finding, WARNING, load_world, read_directory, schema_files

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
    copy = root / "schema" / VOCAB_FILE
    if not copy.exists() or copy.read_text(encoding="utf-8") == schema_files()[VOCAB_FILE]:
        return []
    return [Finding(WARNING, f"schema/{VOCAB_FILE}",
                    "differs from the schema this version of plotcanon validates "
                    "against — refresh the copy with `plotcanon schema --write schema/`")]


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

    for parser in (v, p, s):
        parser.add_argument("--root", default=".", help="the World's directory (default: here)")

    args = ap.parse_args(argv)
    try:
        return args.run(args)
    except (UsageError, NotADirectoryError, ValueError) as e:
        print(f"plotcanon: {e}", file=sys.stderr)
        return COULD_NOT_RUN


if __name__ == "__main__":
    sys.exit(main())
