"""The public functions and the types they return."""

from __future__ import annotations

import copy
import os
import posixpath
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from types import MappingProxyType

import yaml

from . import _checks

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    """One problem with one file.

    `message` names the field and says what is wrong with it. An error means the
    file is not valid; a warning is for a person to judge.
    """

    severity: str
    path: str
    message: str

    def __str__(self):
        label = "ERROR " if self.severity == ERROR else "WARN  "
        return f"{label} {self.path}: {self.message}"


@dataclass(frozen=True)
class Document:
    """One parsed file: its frontmatter as `fields`, and its markdown `body`."""

    path: str
    type: str
    id: str
    fields: Mapping
    body: str


class World:
    """A World that passed validation: every document, by id and by type."""

    def __init__(self, documents, files):
        self.documents = tuple(documents)
        self.files = MappingProxyType(dict(files))
        self._by_id = {d.id: d for d in self.documents}

    def get(self, doc_id):
        """The document with this id, or None."""
        return self._by_id.get(doc_id)

    def of_type(self, doc_type):
        """Every document of one type, such as "npc" or "mod", in path order."""
        return [d for d in self.documents if d.type == doc_type]


@dataclass(frozen=True)
class Report:
    """What `load_world` or `check_file` found.

    `world` (from `load_world`) or `document` (from `check_file`) is set only
    when there are no errors. Warnings do not prevent either.
    """

    errors: tuple = ()
    warnings: tuple = ()
    world: World | None = None
    document: Document | None = None
    document_count: int = field(default=0, compare=False)

    @property
    def ok(self):
        return not self.errors

    @property
    def findings(self):
        return self.errors + self.warnings

    def text(self):
        """Every finding, one per line: the file, then the field and what is
        wrong with it. Written to be read by a person or pasted into an LLM."""
        return "\n".join(str(f) for f in self.findings)

    def summary(self):
        """One line of counts."""
        return (f"{self.document_count} documents · {len(self.errors)} errors · "
                f"{len(self.warnings)} warnings")


def read_directory(directory):
    """Read a World's files from a directory into `{relative path: text}`.

    Only the files that make up the World are read: markdown under the scanned
    top-level folders. Paths use forward slashes whatever the platform.
    """
    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(f"no World directory at {root}")
    files = {}
    for top in _checks.SCAN_DIRS:
        for path in sorted((root / top).rglob("*.md")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            try:
                files[rel] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raise ValueError(f"{rel} is not UTF-8 text") from None
    return files


def _tidy(path):
    """A file's path in its tidy form: relative to the World's root, forward
    slashes, no `./` or `..`. Refuses a path that points outside the World."""
    tidy = posixpath.normpath(str(path).replace("\\", "/"))
    if tidy.startswith(("/", "../")) or tidy == ".." or ":" in tidy.split("/")[0]:
        raise ValueError(f"{path!r} is not a path inside the World")
    return tidy


def _files_of(source):
    if isinstance(source, World):
        return dict(source.files)
    if isinstance(source, Mapping):
        files = {}
        for path, text in source.items():
            if not isinstance(text, str):
                raise TypeError(f"the contents of {path!r} must be text, "
                                f"not {type(text).__name__}")
            files[_tidy(path)] = text
        return files
    if isinstance(source, (str, os.PathLike)):
        return read_directory(source)
    raise TypeError("a World source is a directory, a {path: text} mapping or a World, "
                    f"not {type(source).__name__}")


def _document(doc):
    return Document(doc.rel, doc.type, doc.id, MappingProxyType(doc.fm), doc.body)


# Where a finding is filed when it is about the World as a whole, not one file.
THE_WORLD = "(the World)"


def _checked(files, head=None):
    """Run every check. The checks are written not to raise whatever a file
    holds, and are tested for it. Should one raise all the same, that is
    reported as a finding about the World, so that a caller taking files from
    strangers is never handed an exception for something in a file."""
    try:
        return _checks.run_checks(files, head)
    except MemoryError:
        raise  # Not something in a file to report: the machine is out of memory.
    except Exception as error:  # noqa: BLE001 - the last resort, by design
        raw = _checks.Findings()
        # Only the kind of error is given. Its message could quote a file's
        # contents or a path on the machine running this.
        raw.error(THE_WORLD, f"could not be checked ({type(error).__name__}). This is a "
                             f"fault in plotcanon, set off by something in one of the "
                             f"files; please report it")
        return [], {}, raw


def _findings(raw, only=None):
    errors = tuple(Finding(ERROR, path, msg) for path, msg in raw.errors
                   if only is None or path in (only, THE_WORLD))
    warnings = tuple(Finding(WARNING, path, msg) for path, msg in raw.warnings
                     if only is None or path == only)
    return errors, warnings


def load_world(source, *, head=None):
    """Parse and validate a whole World.

    `source` is a directory, or a mapping of each file's path (relative to the
    World's root, forward slashes) to its text. `head` is the World's current
    git commit, if it has one; it is only used to spot stale generated files.

    Returns a `Report`. `report.world` is the parsed World when there are no
    errors, and None otherwise.
    """
    files = _files_of(source)
    docs, _by_id, raw = _checked(files, head)
    errors, warnings = _findings(raw)
    world = None if errors else World([_document(d) for d in docs], files)
    return Report(errors, warnings, world=world, document_count=len(docs))


def check_file(world, path, text):
    """Validate one file, such as a submitted Mod or After-Action Report,
    against a World.

    `world` is a `World`, a directory or a `{path: text}` mapping. `path` is
    where the file would sit in the World, such as `inbox/the-ashen-vigil.md`;
    it replaces any file already there. The World itself is not changed.

    Returns a `Report` holding only the findings about that file.
    `report.document` is the parsed file when it has no errors.
    """
    path = _tidy(path)
    if not isinstance(text, str):
        raise TypeError(f"the contents of {path!r} must be text, not {type(text).__name__}")
    if not _checks.is_scanned(path):
        folders = ", ".join(f"{d}/" for d in _checks.SCAN_DIRS)
        return Report((Finding(ERROR, path, "not a document path — a World's documents "
                                            f"are .md files under {folders}"),))
    files = _files_of(world)
    files[path] = text
    docs, _by_id, raw = _checked(files)
    errors, warnings = _findings(raw, only=path)
    parsed = next((d for d in docs if d.rel == path), None)
    # A clash of ids is reported on whichever file sorts later. Here it is
    # always the submitted file that is at fault, so say so on that one.
    if parsed is not None and parsed.id:
        for other in docs:
            if other.id == parsed.id and other.rel != path:
                clash = Finding(ERROR, path, f"duplicate id `{parsed.id}` — also in {other.rel}")
                if clash not in errors:
                    errors += (clash,)
    document = _document(parsed) if parsed is not None and not errors else None
    return Report(errors, warnings, document=document, document_count=1 if parsed else 0)


@dataclass(frozen=True)
class Flag:
    """One reason a Mod is in question: a canon change touched one of its
    Features.

    `mod` is the Mod's id. `entity` is the Feature the change names. `change`
    is the position of that change in the report's `canon_changes` list,
    counting from 0.
    """

    mod: str
    entity: str
    change: int


def flags(world, report):
    """The Flags a report's canon changes raise. `report` may also be a record
    of changes made during an Interlude (`interlude-changes`), which has no
    mod of its own and so finishes none.

    A canon change flags every unfinished Mod that features the entity it
    changes, in any Campaign of the World. Unfinished means the Mod still has
    play ahead of it: not finished and not shelved. That includes the report's
    own Mod when it has more to play, since what happened so far may affect
    the rest of it. A report that says it finished its Mod does not flag that
    Mod, whatever state the Mod's file is still in.

    A Flag is raised when a change is proposed and stands once it is approved;
    it is for a person to dismiss. A rejected change did not happen, so it
    raises none. Only the entity a change names counts: for a change of
    location or affiliation, the place or faction moved from or to does not.

    `world` is a `World`. `report` is an After-Action Report: either its
    `Document` or the `Report` that `check_file` returned for it. Returns a
    list of `Flag`, ordered by Mod id and then by the change's position.
    """
    if isinstance(report, Report):
        if report.document is None:
            raise TypeError("that report has errors, so it has no document to work from")
        report = report.document
    vocab = _checks.load_vocab()
    unfinished = vocab["mod_states_unfinished"]
    not_raising = vocab["canon_change_decisions_raising_no_flag"]
    changes = report.fields.get("canon_changes")
    raised = []
    ends_its_mod = (report.fields.get("finished") is True
                    and report.fields.get("ran") is not False)
    just_finished = report.fields.get("mod") if ends_its_mod else None
    for mod in world.of_type("mod"):
        if mod.fields.get("state") not in unfinished or mod.id == just_finished:
            continue
        features = mod.fields.get("features")
        featured = {entity for entities in (features.values() if isinstance(features, Mapping) else [])
                    if isinstance(entities, list) for entity in entities if isinstance(entity, str)}
        for position, change in enumerate(changes if isinstance(changes, list) else []):
            if not isinstance(change, Mapping) or change.get("decision") in not_raising:
                continue
            entity = change.get("entity")
            if isinstance(entity, str) and entity in featured:
                raised.append(Flag(mod.id, entity, position))
    return sorted(raised, key=lambda flag: (flag.mod, flag.change))


def flagged_mods(world, report):
    """The ids of the Mods a report flags, in alphabetical order, each once.
    See `flags` for the rule."""
    return sorted({flag.mod for flag in flags(world, report)})


@dataclass(frozen=True)
class ScriptedReport:
    """One After-Action Report from the sample World's script.

    `path` is where the report goes in the World and `text` is the file.
    `flags` are the ids of the Mods it should flag. `contradicts` are the paths
    of other scripted reports that disagree with it about the same entity.
    `interrupts` is true when the report stops a Mod that has more to play,
    and `finishes` when it is the last report on its Mod.
    """

    path: str
    text: str
    summary: str
    flags: tuple = ()
    contradicts: tuple = ()
    interrupts: bool = False
    finishes: bool = False


def _sample_files(folder):
    """Every markdown file under one folder of the packaged sample, as
    `{path relative to that folder: text}`."""
    files = {}

    def walk(node, prefix):
        for item in sorted(node.iterdir(), key=lambda i: i.name):
            if item.is_dir():
                walk(item, f"{prefix}{item.name}/")
            elif item.name.endswith(".md"):
                files[f"{prefix}{item.name}"] = item.read_text(encoding="utf-8")

    walk(resources.files("plotcanon").joinpath("sample", folder), "")
    return files


def sample_world():
    """A small World to test against and to give a new user: two Campaigns,
    four Events, a dozen NPCs, three factions, three Plots and eleven Mods in
    every state, with some play already reported and approved.

    Returns `{path: text}`, ready for `load_world`. Each call returns a fresh
    copy.
    """
    return _sample_files("world")


def sample_script():
    """After-Action Reports to submit to the sample World, in order, each with
    the Mods it should flag. None of them is in `sample_world()`.

    Returns a list of `ScriptedReport`. Check one with
    `check_file(world, scripted.path, scripted.text)`.
    """
    reports = _sample_files("script")
    manifest = yaml.safe_load(resources.files("plotcanon").joinpath(
        "sample", "script.yml").read_text(encoding="utf-8"))
    listed = [entry["report"] for entry in manifest["reports"]]
    if sorted(listed) != sorted(reports):
        raise RuntimeError("the sample script is inconsistent: script.yml lists "
                           f"{sorted(listed)} but the report files are {sorted(reports)}")
    return [
        ScriptedReport(
            path=entry["report"],
            text=reports[entry["report"]],
            summary=entry["summary"],
            flags=tuple(entry.get("flags") or ()),
            contradicts=tuple(entry.get("contradicts") or ()),
            interrupts=bool(entry.get("interrupts", False)),
            finishes=bool(entry.get("finishes", False)),
        )
        for entry in manifest["reports"]
    ]


def vocabularies():
    """The allowed values for every enum field, and which field uses which.
    Each call returns a copy of its own."""
    return copy.deepcopy(_checks.load_vocab())


def schema_files():
    """The schema as shipped: `{file name: text}` for `vocabularies.yml` and
    the markdown doc for each document type."""
    folder = resources.files("plotcanon").joinpath("schema")
    return {item.name: item.read_text(encoding="utf-8")
            for item in sorted(folder.iterdir(), key=lambda i: i.name)
            if item.name.endswith((".md", ".yml"))}
