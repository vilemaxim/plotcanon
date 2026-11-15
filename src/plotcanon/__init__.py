"""plotcanon — the shared file format for RPG plot canon.

A World is a set of markdown files with YAML frontmatter. This package reads
those files into structured data and validates them.

    report = plotcanon.load_world("path/to/world")      # or {path: text}
    if report.ok:
        npc = report.world.get("varen-ashcroft")
    else:
        print(report.text())                             # paste into an LLM

    report = plotcanon.check_file(world, "inbox/my-mod.md", text)

The document types and their fields are described in the files under
`plotcanon/schema/`, which ship with the package.
"""

from importlib.metadata import version as _version

from ._wording import avoided_words
from ._api import (
    Document,
    Finding,
    Flag,
    Report,
    ScriptedReport,
    World,
    check_file,
    flagged_mods,
    flags,
    load_world,
    read_directory,
    sample_script,
    sample_world,
    schema_files,
    vocabularies,
)

__version__ = _version("plotcanon")

__all__ = [
    "Document",
    "Finding",
    "Flag",
    "Report",
    "ScriptedReport",
    "World",
    "avoided_words",
    "check_file",
    "flagged_mods",
    "flags",
    "load_world",
    "read_directory",
    "sample_script",
    "sample_world",
    "schema_files",
    "vocabularies",
    "__version__",
]
