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

from . import editing
from ._changes import Change, ChangeRefused, applied, unapplied
from ._wording import avoided_words
from ._gm_notes import without_gm_notes
from ._interview import (
    interview_fix_request,
    interview_instructions,
    interview_report_opener,
    interview_revise_opener,
)
from ._plot_team import (
    RECONCILIATION_SECTIONS,
    RECONCILIATION_VERDICTS,
    ReadReconciliation,
    ReadReport,
    ReportFinding,
    ReportSection,
    WORLD_REVIEW_SECTIONS,
    read_reconciliation,
    read_world_review,
    reconciliation_instructions,
    world_review_instructions,
)
from ._story import Contest, Exit, Passage, Section, Story, story
from ._path import LastStop, Path, check_path, path_steps
from ._checks import MAX_GROUP_CHARACTERS, PARALLEL_GROUPS_CLASH, group_label
from ._twine import FromTwine, from_twine, to_twee
from ._references import Reference, name_of, references, referrers, vocabulary_fields
from ._api import (
    Document,
    Finding,
    Flag,
    Report,
    ScriptedReport,
    WORLD_SETTINGS_FILE,
    World,
    WorldSettings,
    check_file,
    flagged_mods,
    flags,
    group_of,
    last_stop,
    load_world,
    read_directory,
    sample_script,
    sample_world,
    schema_files,
    vocabularies,
    world_settings,
)

__version__ = _version("plotcanon")

__all__ = [
    "Change",
    "ChangeRefused",
    "Contest",
    "Document",
    "Exit",
    "Finding",
    "Flag",
    "FromTwine",
    "LastStop",
    "MAX_GROUP_CHARACTERS",
    "PARALLEL_GROUPS_CLASH",
    "Passage",
    "Path",
    "Report",
    "RECONCILIATION_SECTIONS",
    "RECONCILIATION_VERDICTS",
    "ReadReconciliation",
    "ReadReport",
    "Reference",
    "ReportFinding",
    "ReportSection",
    "ScriptedReport",
    "Section",
    "Story",
    "WORLD_SETTINGS_FILE",
    "World",
    "WORLD_REVIEW_SECTIONS",
    "WorldSettings",
    "applied",
    "avoided_words",
    "check_file",
    "check_path",
    "editing",
    "flagged_mods",
    "flags",
    "from_twine",
    "group_label",
    "group_of",
    "interview_fix_request",
    "interview_instructions",
    "interview_report_opener",
    "interview_revise_opener",
    "last_stop",
    "load_world",
    "name_of",
    "path_steps",
    "read_directory",
    "read_reconciliation",
    "read_world_review",
    "reconciliation_instructions",
    "references",
    "referrers",
    "sample_script",
    "sample_world",
    "schema_files",
    "story",
    "to_twee",
    "unapplied",
    "vocabularies",
    "vocabulary_fields",
    "without_gm_notes",
    "world_review_instructions",
    "world_settings",
    "__version__",
]
