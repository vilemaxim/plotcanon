"""A World's settings: the file `world.yml` at its root.

    dry_run_structure: encouraged     # off | encouraged | required

Only what belongs to the World is here. Who may do what, and Organizations,
live in the app (rpg-plot-helper ADR-0001) and never in a World's files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import yaml

from . import _checks

WORLD_SETTINGS_FILE = "world.yml"

OFF, ENCOURAGED, REQUIRED = "off", "encouraged", "required"


def structures():
    """The allowed values of `dry_run_structure`, in order of strictness."""
    return list(_checks.load_vocab()["vocabularies"]["dry_run_structure"])


def default_structure():
    return _checks.load_vocab()["dry_run_structure_default"]


@dataclass(frozen=True)
class WorldSettings:
    """A World's settings, as `world.yml` holds them. Every setting has a
    default, used when the file or that entry in it is absent.

    `dry_run_structure` is how strictly Mods are held to the Dry Run
    convention: "off", "encouraged" or "required".
    """

    dry_run_structure: str = field(default_factory=default_structure)

    def __post_init__(self):
        if self.dry_run_structure not in structures():
            raise ValueError(f"dry_run_structure must be one of {', '.join(structures())}, "
                             f"not {self.dry_run_structure!r}")

    def text(self):
        """The contents of `world.yml` for these settings."""
        return ("# This World's settings. See plotcanon's schema/README.md.\n"
                f'dry_run_structure: "{self.dry_run_structure}"\n')


def read(files, f):
    """The settings in a World's `{path: text}`, with what is wrong with
    `world.yml` reported on `f`. Anything that cannot be read is left at its
    default."""
    text = files.get(WORLD_SETTINGS_FILE)
    if text is None:
        return WorldSettings()
    where = WORLD_SETTINGS_FILE
    if len(text) > _checks.MAX_FRONTMATTER_CHARACTERS:
        f.error(where, f"is longer than {_checks.MAX_FRONTMATTER_CHARACTERS:,} characters, "
                       f"which is more than a World's settings should need")
        return WorldSettings()
    try:
        raw = yaml.load(text, Loader=_checks.Loader)  # noqa: S506 - a SafeLoader subclass
    except _checks.Refused as e:
        f.error(where, str(e))
        return WorldSettings()
    except Exception as e:  # noqa: BLE001 - as for frontmatter
        reason = " ".join(str(e).split())[:300] or type(e).__name__
        f.error(where, f"is not valid YAML: {reason}")
        return WorldSettings()
    if raw is None:
        return WorldSettings()
    if not isinstance(raw, dict):
        f.error(where, "must be a mapping of settings, such as `dry_run_structure: encouraged`")
        return WorldSettings()
    raw, _ = _checks.tamed(where, raw, "settings", f)
    known = {"dry_run_structure"}
    for name in raw:
        if name not in known:
            f.error(where, f"unknown setting `{name}` — the settings are: "
                           f"{', '.join(sorted(known))}")
    value = raw.get("dry_run_structure", default_structure())
    if value is False:
        value = OFF  # A bare `off` is false to YAML; it still means off.
    if not isinstance(value, str) or value not in structures():
        shown = str(value).lower() if isinstance(value, bool) else value
        f.error(where, f"`dry_run_structure: {shown}` is not one of {', '.join(structures())}")
        return WorldSettings()
    return WorldSettings(value)
