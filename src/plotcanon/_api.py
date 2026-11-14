"""The public functions and the types they return."""

from __future__ import annotations

import os
import posixpath
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from types import MappingProxyType

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


def _findings(raw, only=None):
    errors = tuple(Finding(ERROR, path, msg) for path, msg in raw.errors
                   if only is None or path == only)
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
    docs, _by_id, raw = _checks.run_checks(files, head)
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
    docs, _by_id, raw = _checks.run_checks(files)
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


def vocabularies():
    """The allowed values for every enum field, and which field uses which."""
    return _checks.load_vocab()


def schema_files():
    """The schema as shipped: `{file name: text}` for `vocabularies.yml` and
    the markdown doc for each document type."""
    folder = resources.files("plotcanon").joinpath("schema")
    return {item.name: item.read_text(encoding="utf-8")
            for item in sorted(folder.iterdir(), key=lambda i: i.name)
            if item.name.endswith((".md", ".yml"))}
