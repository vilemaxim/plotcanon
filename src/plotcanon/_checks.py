"""The checks behind `plotcanon.load_world` and `plotcanon.check_file`.

Everything here works on a World held in memory as `{relative path: text}`.
Nothing here reads the disk or runs git; `plotcanon._api.read_directory` and
`plotcanon.cli` do.

Checks that every document has the frontmatter its type requires, that every
enum value comes from the packaged vocabularies, and that every id reference
resolves to a real document.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field as dc_field
from importlib import resources
from pathlib import PurePosixPath
from typing import NamedTuple

import yaml

# Directories whose .md files are validated. Everything else (lore/, schema/,
# .claude/, root docs) is deliberately unschema'd prose.
SCAN_DIRS = ["canon", "inbox", "mods", "after-actions", "interludes", "generated"]


def is_scanned(rel):
    """Whether a path, relative to the World's root, is a document to validate."""
    path = PurePosixPath(rel)
    return path.suffix == ".md" and len(path.parts) > 1 and path.parts[0] in SCAN_DIRS


def scan_order(rel):
    """Sort key: SCAN_DIRS order first, then path. Fixes the order of findings."""
    top = PurePosixPath(rel).parts[0]
    return (SCAN_DIRS.index(top) if top in SCAN_DIRS else len(SCAN_DIRS), rel)

# ── Structural schema ───────────────────────────────────────────────────────
# Enum values live in schema/vocabularies.yml. This table is only about which
# fields must exist and which are allowed.

SCHEMAS = {
    "campaign": {
        "dir": "canon/campaigns",
        "required": ["id", "type", "aliases"],
        "optional": ["owner", "tags"],
    },
    "event": {
        "dir": "canon/events",
        "required": ["id", "type", "campaign", "ordinal", "period_type", "aliases",
                     "real_date", "in_world", "status"],
        "optional": ["real_date_end"],
    },
    "npc": {
        "dir": "canon/npcs",
        "required": ["id", "type", "aliases", "status", "as_of", "canon", "visibility"],
        "optional": ["factions", "location", "plots", "first_seen", "owner", "tags"],
    },
    "faction": {
        "dir": "canon/factions",
        "required": ["id", "type", "aliases", "status", "as_of", "canon", "visibility"],
        "optional": ["seat", "members", "allies", "rivals", "plots", "owner", "tags"],
    },
    "location": {
        "dir": "canon/locations",
        "required": ["id", "type", "aliases", "status", "as_of", "canon", "visibility"],
        "optional": ["region", "controlled_by", "plots", "owner", "tags"],
    },
    "plot": {
        "dir": "canon/plots",
        "required": ["id", "type", "aliases", "status", "as_of", "canon", "visibility"],
        "optional": ["entities", "mods", "owner", "tags"],
    },
    "pc": {
        "dir": "canon/pcs",
        "required": ["id", "type", "aliases", "player", "canon", "visibility"],
        "optional": ["factions", "tags"],
    },
    "timeline": {
        "dir": "canon/timeline",
        "required": ["id", "type", "aliases", "in_world", "canon", "visibility"],
        "optional": ["event", "era", "sort_hint", "involves", "tags"],
    },
    "mod": {
        "dir": None,  # inbox/ or mods/** — checked against `state` instead
        "required": ["id", "type", "title", "aliases", "mod_writer", "state",
                     "canon", "visibility", "features"],
        "optional": ["campaign", "events", "slot", "duration_est", "requires",
                     "expected_changes", "supersedes", "tags"],
    },
    "after-action": {
        "dir": "after-actions",
        "required": ["id", "type", "mod", "event", "ran", "finished", "mod_runner", "pcs",
                     "canon_changes"],
        "optional": ["group", "path"],
    },
    "interlude-changes": {
        "dir": "interludes",
        "required": ["id", "type", "event", "recorded_by", "canon_changes"],
        "optional": [],
    },
}

# Which fields hold id references, and what they may point at.
REFS = {
    "event":    {"campaign": ["campaign"]},
    "npc":      {"factions": ["faction"], "location": ["location"],
                 "plots": ["plot"], "as_of": ["event"], "first_seen": ["event"]},
    "faction":  {"seat": ["location"], "members": ["npc"], "allies": ["faction"],
                 "rivals": ["faction"], "plots": ["plot"], "as_of": ["event"]},
    "location": {"controlled_by": ["faction"], "plots": ["plot"], "as_of": ["event"]},
    "plot":     {"entities": ["npc", "faction", "location"],
                 "mods": ["mod"], "as_of": ["event"]},
    "pc":       {"factions": ["faction"]},
    "timeline": {"event": ["event"]},
    "mod":      {"campaign": ["campaign"], "events": ["event"], "supersedes": ["mod"]},
    "after-action": {"mod": ["mod"], "event": ["event"], "pcs": ["pc"]},
    "interlude-changes": {"event": ["event"]},
}

# The documents that carry canon changes: a Mod Runner's report on play, and a
# record of what changed during an Interlude, with no mod run.
CHANGE_SOURCES = ("after-action", "interlude-changes")

# mods/<this>/ holds shelved mods, so no campaign may use it as its id.
SHELVED_DIR = "shelved"

# The kinds of canon change whose `from` and `to` are ids, and what they may
# point at. For the other transition kinds they are words from a vocabulary.
CHANGE_REFS = {"location": ["location"], "affiliation": ["faction"]}

# `first_seen` may say this instead of naming an event.
PRE_CAMPAIGN = "pre-campaign"

# The keys of a mod's `features` and a timeline entry's `involves`, and the
# document type each one lists.
LINK_KEYS = {"npcs": "npc", "factions": "faction", "pcs": "pc",
             "locations": "location", "plots": "plot"}

# The field that holds those links, per document type.
LINK_FIELD = {"mod": "features", "timeline": "involves"}

ENTITY_TYPES = {"npc", "faction", "location", "plot", "pc", "timeline"}

# Aliases shorter than this are not scanned for in prose — too noisy.
MIN_ALIAS_SCAN_LEN = 4


@dataclass
class Doc:
    rel: str
    fm: dict
    body: str
    type: str
    id: str
    # Fields whose shape was wrong. Each has had its error, and holds a
    # stand-in value, so the checks that follow say nothing more about it.
    misshapen: frozenset = frozenset()

    @property
    def stem(self):
        return PurePosixPath(self.rel).stem

    @property
    def parent(self):
        """The directory this document sits in, relative to the World's root."""
        return str(PurePosixPath(self.rel).parent)


@dataclass
class Change:
    entity: str
    kind: str
    frm: object
    to: object
    summary: str
    event: str
    ordinal: int
    source: str
    report_id: str
    position: int = 0

    @property
    def order(self):
        """Sort key. Reports at the same event are taken in id order, with
        numbers compared as numbers: `aa-<mod>`, `aa-<mod>-2`, `aa-<mod>-10`.
        Changes within one report are taken in the order the report lists them.

        Reports from parallel Groups at one event (see `LinesOfPlay`) are
        taken in id order too: it is only a tie-break, so the result is always
        the same, and `check_parallel_changes` warns where it decides a field."""
        return (self.ordinal, natural_key(self.report_id), self.position)


def natural_key(text):
    """Sort key for an id that compares the numbers in it as numbers, so
    `aa-x` comes before `aa-x-2` and that before `aa-x-10`. Only the digits 0
    to 9 count; any other character is compared as text."""
    return [int(part) if part.isascii() and part.isdigit() and len(part) <= 18 else part
            for part in re.split(r"([0-9]+)", str(text))]


@dataclass
class Findings:
    errors: list = dc_field(default_factory=list)
    warnings: list = dc_field(default_factory=list)

    def error(self, rel, msg):
        self.errors.append((rel, msg))

    def warn(self, rel, msg, code=None):
        self.warnings.append((rel, msg, code))


FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.S)
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")


def split_frontmatter(text):
    m = FM_RE.match(text.removeprefix("\ufeff"))
    if not m:
        return None, text
    return m.group(1), m.group(2)


@functools.lru_cache(maxsize=1)
def load_vocab():
    """The vocabularies and bindings shipped with this version of the package.
    Read once and shared, so treat what it returns as read-only."""
    text = resources.files("plotcanon").joinpath("schema/vocabularies.yml").read_text(
        encoding="utf-8")
    return yaml.safe_load(text)


# A document larger than this is refused unread, and frontmatter longer or
# nested deeper than this is refused unparsed. Parsing YAML costs far more per
# character than reading text, which is why the frontmatter has the tighter
# limit. Real documents come nowhere near any of them (the largest file in the
# sample World is under 2,000 characters and nests four deep); a file that does
# is a mistake or an attack, and both cost time and memory.
MAX_FILE_CHARACTERS = 1_000_000
MAX_FRONTMATTER_CHARACTERS = 100_000
MAX_NESTING = 20

# No document needs an id, a name or a list of names anywhere near these. They
# are bounded because each one is compared, sorted or searched for, and the
# cost of that grows with their size and number.
MAX_ID_CHARACTERS = 200
MAX_ALIAS_CHARACTERS = 200
MAX_ALIASES = 100
MAX_GROUP_CHARACTERS = 60
# The `code` of the warning that two Groups that played side by side change
# the same field of the same entity, so a caller can find it without its
# wording.
PARALLEL_GROUPS_CLASH = "parallel-groups-clash"

# A whole number wider than this many bits is not a count, an order or a date.
# Python cannot even print a number of a few thousand digits.
MAX_NUMBER_BITS = 64


# Reference fields that name exactly one document. The rest take a list.
ONE_ID = {"campaign", "event", "mod", "as_of", "first_seen", "location", "seat",
          "controlled_by"}


class Refused(yaml.YAMLError):
    """Frontmatter that is valid YAML but is not accepted in a World's files."""


class Loader(yaml.SafeLoader):
    """Reads frontmatter. It is the safe loader, with two things refused.

    Aliases: YAML lets one value stand in for another (`&name`, `*name`).
    Nested, a few hundred bytes stand for millions of values and exhaust memory
    when expanded. A World's files have no use for them, so a file that uses
    one is refused at the first alias, before anything is expanded.

    Deep nesting: nothing in the format nests more than a few levels.
    """

    depth = 0

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise Refused("uses a YAML alias (`*name`), which is not allowed in a World's "
                          "files — write the value out where it is used")
        self.depth += 1
        try:
            if self.depth > MAX_NESTING:
                raise Refused(f"frontmatter is nested more than {MAX_NESTING} levels deep")
            return super().compose_node(parent, index)
        finally:
            self.depth -= 1


def is_single(value):
    """Whether a value is one thing, not a list or mapping of things."""
    return not isinstance(value, (list, dict, set, tuple))


def showable(text):
    """Whether text can be shown, stored and sent as it is: no control
    characters other than line breaks and tabs, and no broken halves of
    characters (lone surrogates), which cannot be encoded at all."""
    return not any((ord(c) < 32 and c not in "\n\r\t") or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF
                   for c in text)


def tamed(rel, value, where, f):
    """A parsed YAML value with anything in it that cannot safely be compared,
    printed or stored reported and replaced. Returns the value and whether
    anything was replaced. YAML can produce all of these from a few bytes."""
    if isinstance(value, bool) or value is None:
        return value, False
    if isinstance(value, int):
        if value.bit_length() > MAX_NUMBER_BITS:
            f.error(rel, f"`{where}` is a number too large to be meant")
            return 0, True
        return value, False
    if isinstance(value, str):
        if not showable(value):
            f.error(rel, f"`{where}` contains characters that cannot be shown "
                         f"(control characters, or broken text)")
            return "".join(c for c in value if showable(c)), True
        return value, False
    if isinstance(value, list):
        changed, out = False, []
        for i, item in enumerate(value):
            item, item_changed = tamed(rel, item, f"{where}[{i}]", f)
            out.append(item)
            changed = changed or item_changed
        return out, changed
    if isinstance(value, dict):
        changed, out = False, {}
        for key, item in value.items():
            if isinstance(key, str) and not showable(key):
                f.error(rel, f"a field name under `{where}` contains characters that "
                             f"cannot be shown")
                changed = True
                continue
            item, item_changed = tamed(rel, item, f"{where}.{key}", f)
            out[key] = item
            changed = changed or item_changed
        return out, changed
    return value, False


def well_shaped(rel, fm, typ, f):
    """The frontmatter with every value the checks rely on in the shape they
    expect, and the names of the fields that had to be changed to get there.

    Wherever a value has the wrong shape, that is reported as an error against
    the file, and a harmless value is put in its place so that the rest of the
    checks can still run and say what else is wrong. The field's name is
    returned so that those checks do not complain a second time about the
    stand-in.

    A file that is changed here always has an error, so what a caller is handed
    for a valid file is exactly what the file says.
    """
    fm = dict(fm)
    misshapen = set()

    def wrong(field, message):
        f.error(rel, message)
        misshapen.add(field)

    for key in [key for key in fm if not isinstance(key, str) or not showable(key)]:
        shown = key if isinstance(key, (int, float, bool, type(None))) else "…"
        if isinstance(key, int) and not isinstance(key, bool) \
                and key.bit_length() > MAX_NUMBER_BITS:
            shown = "…"
        f.error(rel, f"`{shown}` is not a field name — field names are words")
        del fm[key]

    for field in list(fm):
        fm[field], changed = tamed(rel, fm[field], field, f)
        if changed:
            misshapen.add(field)

    if fm.get("id") is not None and not isinstance(fm["id"], str):
        wrong("id", f"`id` must be a slug, got {fm['id']!r}")
        fm["id"] = None
    elif isinstance(fm.get("id"), str) and len(fm["id"]) > MAX_ID_CHARACTERS:
        wrong("id", f"`id` is longer than {MAX_ID_CHARACTERS} characters")
        fm["id"] = None

    group = fm.get("group") if typ == "after-action" else None
    if group is not None and group_label_problem(group):
        wrong("group", group_label_problem(group))
        fm["group"] = None

    def id_list(field, where, listed):
        """A list of ids. Anything in it that is not one is reported and left out."""
        good = [item for item in listed if isinstance(item, str) or item is None]
        if len(good) != len(listed):
            wrong(field, f"`{where}` must be a list of ids")
        return good

    for field in REFS.get(typ, {}):
        value = fm.get(field)
        if value is None or (isinstance(value, str) and field in ONE_ID):
            continue
        if field in ONE_ID:
            if isinstance(value, list):
                wrong(field, f"`{field}` must be one id, not a list")
            elif is_single(value):
                wrong(field, f"`{field}` must be an id, got {value!r}")
            else:
                wrong(field, f"`{field}` must be one id")
            fm[field] = None
        elif isinstance(value, list):
            fm[field] = id_list(field, field, value)
        else:
            wrong(field, f"`{field}` must be a list of ids")
            fm[field] = []

    # A field that takes a value from a vocabulary takes one value.
    for field in load_vocab()["bindings"].get(typ, {}):
        if field in fm and not is_single(fm[field]):
            wrong(field, f"`{field}` must be a single value, not a list")
            fm[field] = None

    if "aliases" in fm and fm["aliases"] is not None:
        aliases = fm["aliases"]
        if not isinstance(aliases, list) or not all(is_single(a) for a in aliases):
            wrong("aliases", "`aliases` must be a list of names")
            aliases = [a for a in aliases if is_single(a)] if isinstance(aliases, list) else []
        if len(aliases) > MAX_ALIASES:
            wrong("aliases", f"`aliases` has more than {MAX_ALIASES} names")
            aliases = aliases[:MAX_ALIASES]
        if any(len(str(a)) > MAX_ALIAS_CHARACTERS for a in aliases):
            wrong("aliases", f"a name in `aliases` is longer than {MAX_ALIAS_CHARACTERS} "
                             f"characters")
            aliases = [a for a in aliases if len(str(a)) <= MAX_ALIAS_CHARACTERS]
        fm["aliases"] = aliases

    for field in set(LINK_FIELD.values()) & set(fm):
        links = fm[field]
        if links is None:
            continue
        if not isinstance(links, dict):
            f.error(rel, f"`{field}` must be a mapping of {'/'.join(LINK_KEYS)} to id lists")
            fm[field] = {}
            continue
        shaped = {}
        for key, listed in links.items():
            if not isinstance(key, str):
                f.error(rel, f"`{field}.{key}` is not a recognised key ({', '.join(LINK_KEYS)})")
            elif not isinstance(listed, list):
                f.error(rel, f"`{field}.{key}` must be a list of ids")
            else:
                shaped[key] = id_list(field, f"{field}.{key}", listed)
        fm[field] = shaped

    if "canon_changes" in fm and fm["canon_changes"] is not None:
        changes = fm["canon_changes"]
        if not isinstance(changes, list):
            f.error(rel, "`canon_changes` must be a list")
            changes = []
        shaped = []
        for i, change in enumerate(changes):
            where = f"canon_changes[{i}]"
            if not isinstance(change, dict):
                f.error(rel, f"{where} must be a mapping")
                shaped.append(None)  # Kept, so that the changes after it keep their place.
                continue
            # A change with a wrongly shaped part is reported once, here, and
            # then left out of the checks that follow, like one that is not a
            # mapping at all.
            if change.get("entity") is not None and not isinstance(change["entity"], str):
                f.error(rel, f"{where}.entity must be an id")
                change = None
            else:
                for key in ("kind", "decision", "from", "to"):
                    if key in change and not is_single(change[key]):
                        f.error(rel, f"{where}.{key} must be a single value")
                        change = None
                        break
            if change is not None and change.get("note") is not None \
                    and not isinstance(change["note"], str):
                f.error(rel, f"{where}.note must be text")
                change = None
            shaped.append(change)
        fm["canon_changes"] = shaped

    if "requires" in fm and fm["requires"] is not None:
        clauses = fm["requires"]
        if not isinstance(clauses, list):
            f.error(rel, "`requires` must be a list of clauses")
            clauses = []
        shaped = []
        for i, clause in enumerate(clauses):
            where = f"requires[{i}]"
            # A clause that is wrong is reported here and kept as an empty
            # place, so that the clauses after it keep their numbers.
            if not isinstance(clause, dict):
                f.error(rel, f"{where} needs `entity` and `field`")
                clause = None
            elif not isinstance(clause.get("entity"), str) \
                    or not isinstance(clause.get("field"), str):
                f.error(rel, f"{where} needs `entity` and `field`, each a single word")
                clause = None
            elif "in" in clause and (not isinstance(clause["in"], list)
                                     or not all(is_single(v) for v in clause["in"])):
                f.error(rel, f"{where}.in must be a list of values")
                clause = None
            elif "equals" in clause and not is_single(clause["equals"]):
                f.error(rel, f"{where}.equals must be a single value")
                clause = None
            shaped.append(clause)
        fm["requires"] = shaped

    return fm, frozenset(misshapen)


def collect_docs(files, f: Findings):
    """Index every schema'd document, plus derived artifacts kept separately.

    `files` maps each path, relative to the World's root, to that file's text.

    Files under generated/ are not canon and do not carry a schema `type` — they
    have their own frontmatter shape and are only checked for a freshness stamp.
    """
    docs, by_id, generated = [], {}, []
    for rel in sorted(files, key=scan_order):
        if not is_scanned(rel):
            continue
        if len(files[rel]) > MAX_FILE_CHARACTERS:
            f.error(rel, f"is larger than {MAX_FILE_CHARACTERS:,} characters, which is more "
                         f"than one document should need")
            continue
        raw, body = split_frontmatter(files[rel])
        if raw is None:
            f.error(rel, "no YAML frontmatter block")
            continue
        if len(raw) > MAX_FRONTMATTER_CHARACTERS:
            f.error(rel, f"frontmatter is longer than {MAX_FRONTMATTER_CHARACTERS:,} "
                         f"characters, which is more than a document's fields should need")
            continue
        try:
            fm = yaml.load(raw, Loader=Loader)  # noqa: S506 - a SafeLoader subclass
        except Refused as e:
            f.error(rel, str(e))
            continue
        except Exception as e:  # noqa: BLE001
            # PyYAML raises more than its own errors: a tag that does not fit
            # its value fails inside the constructor with whatever that hit.
            # Whatever it was, the block could not be read as YAML.
            reason = " ".join(str(e).split())[:300] or type(e).__name__
            f.error(rel, f"frontmatter is not valid YAML: {reason}")
            continue
        if fm is None:
            fm = {}
        if not isinstance(fm, dict):
            f.error(rel, "frontmatter must be a mapping")
            continue
        if rel.startswith("generated/"):
            fm, _changed = tamed(rel, fm, "frontmatter", f)
            generated.append(Doc(rel, fm, body, "generated", None))
            continue
        typ = fm.get("type")
        if not isinstance(typ, str) or typ not in SCHEMAS:
            f.error(rel, f"unknown or missing `type`: {typ!r}")
            continue
        fm, misshapen = well_shaped(rel, fm, typ, f)
        doc = Doc(rel, fm, body, typ, fm.get("id"), misshapen)
        docs.append(doc)
        if doc.id:
            if doc.id in by_id:
                f.error(rel, f"duplicate id `{doc.id}` — also in {by_id[doc.id].rel}")
            else:
                by_id[doc.id] = doc
    return docs, by_id, generated


# ── Checks ──────────────────────────────────────────────────────────────────

def check_fields(doc, f):
    """E1 required fields, E2 id matches filename, plus unknown-key noise."""
    schema = SCHEMAS[doc.type]
    for key in schema["required"]:
        if key not in doc.fm:
            f.error(doc.rel, f"missing required field `{key}`")
        elif (doc.fm[key] is None and key not in doc.misshapen
              and key not in ("location", "seat", "controlled_by")):
            f.error(doc.rel, f"required field `{key}` is empty")

    allowed = set(schema["required"]) | set(schema["optional"])
    for key in doc.fm:
        if key not in allowed:
            f.warn(doc.rel, f"unrecognised field `{key}` — typo, or update schema/")

    stem = doc.stem
    if doc.id != stem and "id" not in doc.misshapen:
        f.error(doc.rel, f"`id` is `{doc.id}` but filename stem is `{stem}` — they must match")

    if doc.id and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(doc.id)):
        f.error(doc.rel, f"`id` `{doc.id}` is not a clean slug (lowercase, hyphens, no spaces)")

    if doc.type == "campaign" and doc.id == SHELVED_DIR:
        f.error(doc.rel, f"a campaign cannot have the id `{SHELVED_DIR}` — "
                         f"mods/{SHELVED_DIR}/ is where shelved mods live")

    expected_dir = schema["dir"]
    if expected_dir and not doc.rel.startswith(expected_dir + "/"):
        f.error(doc.rel, f"type `{doc.type}` must live under {expected_dir}/")


def check_enums(doc, vocab, f):
    """E3: every enum-typed field holds a value from its vocabulary."""
    for fieldname, vocab_name in vocab["bindings"].get(doc.type, {}).items():
        if fieldname not in doc.fm or fieldname in doc.misshapen:
            continue
        value = doc.fm[fieldname]
        allowed = vocab["vocabularies"][vocab_name]
        if not isinstance(value, str) or value not in allowed:
            f.error(doc.rel,
                    f"`{fieldname}: {value}` is not in vocabulary `{vocab_name}` "
                    f"({', '.join(allowed)})")


def is_submission(doc):
    """A mod in inbox/ carries ids invented by a Mod Writer outside this repo.

    Mod Writers cannot see canon and are told to make slugs up
    (larp-llm's `prompts/mod-writer-intake.md`), so unresolved references in a submission are
    its expected state, not a defect — mapping them is exactly what the
    reconciler is for. Erroring would put the whole repo in a failing state the
    moment a mod landed, blocking every commit until reconciliation finished.

    This is not the schema being relaxed to silence an error (CLAUDE.md §10).
    Referential integrity is a guarantee about canon, and CLAUDE.md §4 is
    explicit that inbox/ is not canon. Everything else about the file is still
    checked as an error, including that a submission may not claim
    `canon: approved`.
    """
    return doc.type == "mod" and doc.parent == "inbox"


def resolve(value, allowed_types, by_id, doc, fieldname, f):
    """E4: one id reference resolves to a document of an acceptable type."""
    if value is None:
        return
    if not isinstance(value, (str, int)):
        f.error(doc.rel, f"`{fieldname}` must hold ids, got {value!r}")
        return
    target = by_id.get(value)
    if target is None:
        if is_submission(doc):
            f.warn(doc.rel, f"`{fieldname}: {value}` does not resolve — the Mod Writer's "
                            f"slug, to be mapped at intake")
        else:
            f.error(doc.rel, f"`{fieldname}: {value}` does not resolve to any document")
    elif target.type not in allowed_types:
        f.error(doc.rel, f"`{fieldname}: {value}` points at a `{target.type}`, "
                         f"expected {' or '.join(allowed_types)}")


def check_refs(doc, by_id, f):
    """E4 for scalar and list reference fields, and for `features`/`involves`."""
    for fieldname, types in REFS.get(doc.type, {}).items():
        if fieldname not in doc.fm:
            continue
        value = doc.fm[fieldname]
        if fieldname == "first_seen" and value == PRE_CAMPAIGN:
            continue
        if isinstance(value, list):
            for item in value:
                resolve(item, types, by_id, doc, fieldname, f)
        else:
            resolve(value, types, by_id, doc, fieldname, f)

    link_field = LINK_FIELD.get(doc.type)
    links = doc.fm.get(link_field) if link_field else None
    if links is not None:
        if not isinstance(links, dict):
            f.error(doc.rel, f"`{link_field}` must be a mapping of npcs/factions/pcs/"
                             "locations/plots to id lists")
        else:
            for key, ids in links.items():
                if key not in LINK_KEYS:
                    f.error(doc.rel, f"`{link_field}.{key}` is not a recognised key "
                                     f"({', '.join(LINK_KEYS)})")
                    continue
                if not isinstance(ids, list):
                    f.error(doc.rel, f"`{link_field}.{key}` must be a list of ids")
                    continue
                for item in ids:
                    resolve(item, [LINK_KEYS[key]], by_id, doc, f"{link_field}.{key}", f)


def check_events(docs, f):
    """E6: ordinals are unique and gapless."""
    events = [d for d in docs if d.type == "event"]
    seen = {}
    for e in events:
        o = e.fm.get("ordinal")
        if not isinstance(o, int) or isinstance(o, bool):
            f.error(e.rel, f"`ordinal` must be an integer, got {o!r}")
            continue
        if o in seen:
            f.error(e.rel, f"`ordinal: {o}` is already used by {seen[o]}")
        seen[o] = e.rel
    ordinals = sorted(seen)
    if ordinals:
        expected = list(range(ordinals[0], ordinals[0] + len(ordinals)))
        if ordinals != expected:
            missing = sorted(set(expected) - set(ordinals))
            f.error("canon/events/", f"event ordinals are not gapless — missing {missing}. "
                                     "A cancelled event keeps its ordinal.")


def check_timeline(doc, f):
    """A timeline entry is either on the clock or pre-campaign, never both."""
    has_event = doc.fm.get("event") is not None
    has_era = doc.fm.get("era") is not None
    if has_event and has_era:
        f.error(doc.rel, "`event` and `era` are mutually exclusive — an entry is "
                         "either on the clock or pre-campaign")
    elif not has_event and not has_era:
        f.error(doc.rel, "needs either `event` (on the clock) or `era` (pre-campaign)")


def mod_events(doc):
    """The ids in a mod's `events` list, or [] when it has none."""
    events = doc.fm.get("events")
    if not isinstance(events, list):
        return []
    return [e for e in events if isinstance(e, str)]  # others: check_refs reports


def check_mod_placement(doc, vocab, by_id, f):
    """E5: `state` and `campaign` must agree with the directory the file sits in."""
    state = doc.fm.get("state")
    dirs = vocab["mod_state_dirs"].get(state)
    if dirs is None:
        return  # bad state value already reported by check_enums
    parent = doc.parent
    campaign = doc.fm.get("campaign")

    if parent != "inbox" and not campaign:
        f.error(doc.rel, "a mod outside inbox/ needs a `campaign`")
    else:
        expected = [d.replace("<campaign>", str(campaign)) for d in dirs]
        if parent not in expected:
            f.error(doc.rel, f"`state: {state}` requires the file to live in "
                             f"{' or '.join(expected)}, but it is in {parent}/")

    events = doc.fm.get("events")
    if events is not None and not isinstance(events, list):
        f.error(doc.rel, "`events` must be a list of event ids")
    if state in vocab["mod_states_that_have_run"] and not mod_events(doc):
        f.error(doc.rel, f"`state: {state}` requires at least one event in `events`")
    for evid in mod_events(doc):
        event = by_id.get(evid)
        if event is None or event.type != "event":
            continue  # already reported by check_refs
        theirs = event.fm.get("campaign")
        if campaign and theirs and theirs != campaign:
            f.error(doc.rel, f"`events: {evid}` belongs to campaign `{theirs}`, "
                             f"but this mod belongs to `{campaign}`")

    # A submission is not canon, whatever its frontmatter claims. Mods arrive
    # from Mod Writers outside this repo, so `canon` is the Plot Master's to set — a
    # Mod Writer who writes `approved` must not be believed.
    if parent == "inbox" and doc.fm.get("canon") != "proposed":
        f.error(doc.rel, f"`canon: {doc.fm.get('canon')}` in inbox/ — a submitted "
                         f"mod must be `proposed`. Set it at intake; never "
                         f"take a Mod Writer's word for it.")


def yes_or_no(doc, field, meaning, f):
    """A field that must be true or false. Quoted `"true"` is text, not true,
    so it is shown quoted to make that plain."""
    value = doc.fm.get(field)
    if value is None or isinstance(value, bool):
        return
    shown = repr(value) if isinstance(value, str) and value in ("true", "false") else value
    f.error(doc.rel, f"`{field}: {shown}` must be true or false — {meaning}")


def check_interlude_placement(doc, by_id, f):
    """Canon changes made during an Interlude live under it, and name an event
    that is an Interlude: changes at a gathering of play come from its mods'
    reports."""
    ev = doc.fm.get("event")
    if not isinstance(ev, str):
        return
    if doc.parent != f"interludes/{ev}":
        f.error(doc.rel, f"must live in interludes/{ev}/, not {doc.parent}/")
    event = by_id.get(ev)
    if event is not None and event.type == "event" \
            and event.fm.get("period_type") != "interlude":
        f.error(doc.rel, f"`event: {ev}` is not an Interlude (its `period_type` is "
                         f"{event.fm.get('period_type')}). Changes at a gathering of play "
                         f"are recorded in its mods' after-action reports")


def check_report_placement(doc, by_id, f):
    parent = doc.parent
    ev = doc.fm.get("event")
    if ev and parent != f"after-actions/{ev}":
        f.error(doc.rel, f"must live in after-actions/{ev}/, not {parent}/")

    yes_or_no(doc, "ran", "true if the mod was played, false if it was not", f)
    yes_or_no(doc, "finished", "true if this report is the last on its mod, false if "
                               "there is more to play", f)
    finished = doc.fm.get("finished")
    if finished is True and doc.fm.get("ran") is False:
        f.error(doc.rel, "`ran: false` with `finished: true` — a mod that did not run was "
                         "not finished by this report. Say `finished: false`")

    # A mod lists every event it runs at, so a report can only be for one of those.
    mod_id = doc.fm.get("mod")
    mod = by_id.get(mod_id) if isinstance(mod_id, str) else None
    if ev and mod is not None and mod.type == "mod" and ev not in mod_events(mod):
        f.error(doc.rel, f"`event: {ev}` is not in the `events` of mod `{mod.id}` — "
                         f"add it there, or fix this report")


def reports_by_mod(docs, by_id):
    """Each Mod's reports, in the order they are read: by event, then by id
    (see `natural_key`). `{mod id: [report, ...]}`. A report whose Mod or
    event does not resolve has no place in that order and is left out; it is
    already in error."""
    reports = {}
    for doc in docs:
        mod = by_id.get(doc.fm.get("mod")) if isinstance(doc.fm.get("mod"), str) else None
        if doc.type != "after-action" or mod is None or mod.type != "mod":
            continue
        ordinal = ordinal_of(doc.fm.get("event"), by_id) \
            if isinstance(doc.fm.get("event"), str) else None
        if ordinal is not None:
            reports.setdefault(mod.id, []).append(((ordinal, natural_key(doc.id)), doc))
    return {mod_id: [doc for _order, doc in sorted(filed, key=lambda pair: pair[0])]
            for mod_id, filed in reports.items()}


def group_label(value):
    """A `group` as the label of a Group: its text stripped, or None when it
    is not text or is blank, which is no Group. A label that is valid in a
    file is also on one line and at most `MAX_GROUP_CHARACTERS` long."""
    return (value.strip() or None) if isinstance(value, str) else None


def group_label_problem(value):
    """Why `value` will not do as a Group's label, as the check of a file
    says it, or None when it will: text, not blank, on one line and at most
    `MAX_GROUP_CHARACTERS` long once stripped."""
    label = group_label(value)
    if label is None or "\n" in label or len(label) > MAX_GROUP_CHARACTERS:
        return (f"`group` must be a short label, as text on one line of at most "
                f"{MAX_GROUP_CHARACTERS} characters")
    return None


def group_of(report):
    """The Group a report covers, its `group`, or None when it has none: the
    report then covers the whole Mod."""
    return group_label(report.fm.get("group"))


class Placement(NamedTuple):
    """Where a report with a `group` sits: the split it is in, counted from
    1 in report order, and its Group's label."""

    split: int
    group: str


class Changing(NamedTuple):
    """A report in a Group that changes a field, at `index` in its
    `canon_changes`."""

    report: Doc
    group: str
    index: int


class LinesOfPlay:
    """A Mod's reports, read in order, as the lines of play they make.

    Before any split there is one line. Groups are parallel at one Event: a
    report with a `group` is on that Group's line at its Event. Its first
    report there branches from the Mod's line as it stood before the split,
    and each later one with the same label follows the one before it. Reports
    with different labels at one Event ran side by side, in parallel.

    A split ends when the Groups come back together: at a report with no
    `group`, or at the end of the split's Event. What comes next follows
    every Group that had not finished, or every Group when all had. So a
    Group at a later Event, whatever its label, branches from there, and a
    label used again at a later Event names a new Group.

    `follows[rel]` is what each report follows on from: a tuple of reports,
    or of None for the start of the Mod. `parallel[rel]` is the `Placement`
    of a report with a `group`, or None for a report with none.
    """

    def __init__(self, filed, by_id):
        self.trunk = (None,)    # What the Mod's own line follows on from.
        self.split = {}         # Each Group's last report at `ordinal`, by label.
        self.ordinal = None     # The Event of the last report, as its ordinal.
        self.splits = 0
        self.follows, self.parallel = {}, {}
        self.enders, self.enders_before = {}, {}
        for report in filed:
            ordinal = ordinal_of(report.fm.get("event"), by_id)
            group = group_of(report)
            self.follows[report.rel] = self.follow(group, ordinal)
            self.read_ends(report)
            if self.split and ordinal != self.ordinal:
                self.trunk, self.split = self.joined(), {}
            self.ordinal = ordinal
            if group is None:
                self.trunk, self.split = (report,), {}
                self.parallel[report.rel] = None
            else:
                if not self.split:
                    self.splits += 1
                self.split[group] = report
                self.parallel[report.rel] = Placement(self.splits, group)

    def joined(self):
        """What follows the open split once its Groups come back together:
        every Group that had not finished, or every Group when all had."""
        tips = tuple(self.split.values())
        return tuple(tip for tip in tips if not self.ended(tip)) or tips

    def follow(self, group, ordinal=None):
        """What a report in `group` (None for none) would follow on from,
        next, at the Event `ordinal` (None for the Event of the last report)."""
        split = self.split if ordinal is None or ordinal == self.ordinal else {}
        trunk = self.joined() if self.split and not split else self.trunk
        if group is not None:
            return (split[group],) if group in split else trunk
        return self.joined() if split else trunk

    @property
    def tips(self):
        """The last report on each line still open after the last report: on
        each Group at the Mod's latest Event, when it ended split."""
        if self.split:
            return tuple(self.split.values())
        return tuple(report for report in self.trunk if report is not None)

    def ended(self, report):
        """The reports that finished the line `report` is on, by the time of
        `report`: itself when it finishes it, or the reports that had already
        finished every line it follows on from. Empty when its line goes on."""
        return () if report is None else self.enders[report.rel]

    def ended_before(self, report):
        """The reports that had finished every line `report` follows on from,
        or empty when one of them goes on."""
        return self.enders_before[report.rel]

    def read_ends(self, report):
        """Note what had finished the lines `report` follows on from, and
        what has finished its own, from the reports before it."""
        ended = [self.ended(prev) for prev in self.follows[report.rel]]
        before = tuple({r.rel: r for enders in ended for r in enders}.values()) \
            if all(ended) else ()
        self.enders_before[report.rel] = before
        self.enders[report.rel] = before or ((report,) if finishes(report) else ())


def listed_ids(reports):
    """Reports' ids, for saying so: `a` and `b`."""
    return " and ".join(f"`{r.id}`" for r in reports)


def check_finished(docs, by_id, vocab, f):
    """A mod's reports, read in order, against whether the mod is finished.

    Nothing may follow a report that finishes its line of play (see
    `LinesOfPlay`): the whole Mod's, or a Group's. If another report comes
    after it on that line, both are in error: either may be the one just
    submitted, so each is told about the other. And the mod's own `state`,
    which a person sets, is compared with what its latest reports say: the
    latest on each line still open, so on each Group of a split. The Mod is
    finished when every one of them finishes it. A disagreement is a warning
    on the mod, since the state is theirs to bring up to date.

    Reports are read by event, then by id (see `natural_key`). A report whose
    event does not resolve has no place in that order and is left out; it is
    already in error.
    """
    unfinished = vocab["mod_states_unfinished"]
    has_run = vocab["mod_states_that_have_run"]
    for mod_id, filed in sorted(reports_by_mod(docs, by_id).items()):
        lines = LinesOfPlay(filed, by_id)
        for report in filed:
            enders = lines.ended_before(report)
            if not enders:
                continue
            fix = (f"`{enders[0].id}` should say" if len(enders) == 1
                   else "one of them should say")
            f.error(report.rel, f"mod `{mod_id}` was finished by {listed_ids(enders)} — a "
                                f"finished mod cannot be reported on again. If there was "
                                f"more to play, {fix} `finished: false`")
            for ender in enders:
                last = "in a Group" if lines.parallel[ender.rel] else "on a mod"
                f.error(ender.rel, f"says mod `{mod_id}` is finished, but `{report.id}` "
                                   f"reports on it afterwards — only the last report "
                                   f"{last} can say `finished: true`")

        if sum(1 for doc in docs if doc.id == mod_id) > 1:
            continue  # Two documents claim this id; that is already an error.
        mod, tips = by_id[mod_id], lines.tips
        state = mod.fm.get("state")
        fix = "set the state to match, or correct the report"
        if len(tips) == 1:
            latest = f"its latest report (`{tips[0].id}`) says"
        else:
            latest = f"its latest reports, one for each Group ({listed_ids(tips)}), say"
            fix += "s"
        if all(finishes(tip) for tip in tips) and state in unfinished:
            f.warn(mod.rel, f"`state: {state}`, but {latest} the mod is finished — {fix}")
        elif any(tip.fm.get("finished") is False for tip in tips) \
                and state == vocab["mod_state_finished"]:
            f.warn(mod.rel, f"`state: {state}`, but {latest} there is more to play — {fix}")
        elif (any(tip.fm.get("finished") is False and tip.fm.get("ran") is True
                  for tip in tips)
              and state in unfinished and state not in has_run):
            f.warn(mod.rel, f"`state: {state}`, but {latest} it has been run and has more "
                            f"to play — {fix}")


def finishes_its_mod(filed, by_id, report):
    """Whether the Mod is finished once `report`, one of its reports `filed`
    in order, has been played: when every Group at the Mod's latest Event by
    then has a report that finishes it, or, with no split, when `report`
    finishes the Mod (see `LinesOfPlay`)."""
    if report not in filed:
        return finishes(report)
    tips = LinesOfPlay(filed[:filed.index(report) + 1], by_id).tips
    return bool(tips) and all(finishes(tip) for tip in tips)


def finishes(report):
    """Whether this report is the one that ends its mod. A mod that did not run
    is not finished by the report that says so."""
    return report.fm.get("finished") is True and report.fm.get("ran") is not False


def check_parallel_changes(docs, by_id, vocab, f):
    """A warning on both reports when two Groups that played side by side
    (see `LinesOfPlay`) change the same field of the same entity. Their
    changes are still decided in one order, by `Change.order`, but which
    comes last is only the order of their ids, so a Plot Master checks it.
    A prose change moves no field, and a rejected one moves nothing."""
    transition_kinds = set(vocab["canon_change_transition_kinds"])
    kind_fields = vocab["canon_change_kind_fields"]
    moving = set(vocab["vocabularies"]["canon_change_decision"]) \
        - set(vocab["canon_change_decisions_raising_no_flag"])
    for _mod_id, filed in sorted(reports_by_mod(docs, by_id).items()):
        lines = LinesOfPlay(filed, by_id)
        changing = {}   # (split, entity, field) -> {report rel: Changing}
        for report in filed:
            placed = lines.parallel[report.rel]
            changes = report.fm.get("canon_changes")
            if placed is None or not isinstance(changes, list):
                continue
            for i, change in enumerate(changes):
                if not isinstance(change, dict) or change.get("kind") not in transition_kinds \
                        or change.get("decision") not in moving \
                        or not isinstance(change.get("entity"), str):
                    continue
                key = (placed.split, change["entity"], kind_fields[change["kind"]])
                changing.setdefault(key, {}).setdefault(
                    report.rel, Changing(report, placed.group, i))
        for (_split, entity, field), reports in changing.items():
            for this in reports.values():
                others = [other for other in reports.values() if other.group != this.group]
                if not others:
                    continue
                each = [f"`{others[0].report.id}` does in the Group `{others[0].group}`"]
                each += [f"`{other.report.id}` in the Group `{other.group}`"
                         for other in others[1:]]
                listed = each[0] if len(each) == 1 else ", ".join(each[:-1]) + " and " + each[-1]
                f.warn(this.report.rel,
                       f"`canon_changes[{this.index}]` changes `{field}` of `{entity}`, as "
                       f"{listed}, which played alongside this one — they are "
                       f"decided in order of report id, so check that they agree",
                       code=PARALLEL_GROUPS_CLASH)


def collect_changes(docs, by_id, vocab, f):
    """E7 plus canon change shape.

    Returns every well-formed transition change that has been approved. A
    proposed or rejected change is not canon, so nothing downstream counts it.
    """
    transition_kinds = set(vocab["canon_change_transition_kinds"])
    kind_fields = vocab["canon_change_kind_fields"]
    kind_vocab = vocab["vocabularies"]["canon_change_kind"]
    decision_vocab = vocab["vocabularies"]["canon_change_decision"]
    in_canon = vocab["canon_change_decision_in_canon"]
    out = []

    for doc in docs:
        if doc.type not in CHANGE_SOURCES:
            continue
        changes = doc.fm.get("canon_changes")
        if changes is None:
            continue
        if not isinstance(changes, list):
            f.error(doc.rel, "`canon_changes` must be a list")
            continue
        ev = doc.fm.get("event")
        ordinal = ordinal_of(ev, by_id) if isinstance(ev, str) else None

        for i, d in enumerate(changes):
            where = f"canon_changes[{i}]"
            if d is None:
                continue  # Wrongly shaped, and already reported by `well_shaped`.
            if not isinstance(d, dict):
                f.error(doc.rel, f"{where} must be a mapping")
                continue
            ent, kind = d.get("entity"), d.get("kind")
            if not ent:
                f.error(doc.rel, f"{where} missing `entity`")
            else:
                resolve(ent, list(ENTITY_TYPES), by_id, doc, f"{where}.entity", f)
            decision = d.get("decision")
            if decision is None:
                f.error(doc.rel, f"{where} missing `decision` — one of "
                                 f"{', '.join(decision_vocab)}")
            elif not isinstance(decision, str) or decision not in decision_vocab:
                f.error(doc.rel, f"{where} `decision: {decision}` is not in vocabulary "
                                 f"`canon_change_decision` ({', '.join(decision_vocab)})")
            if not isinstance(kind, str) or kind not in kind_vocab:
                f.error(doc.rel, f"{where} `kind: {kind}` is not in vocabulary "
                                 f"`canon_change_kind` ({', '.join(kind_vocab)})")
                continue
            if not d.get("summary"):
                f.error(doc.rel, f"{where} missing `summary` — every canon change needs one line of prose")

            has_transition = "from" in d or "to" in d
            if kind in transition_kinds:
                if "from" not in d or "to" not in d:
                    f.error(doc.rel, f"{where} `kind: {kind}` requires both `from` and `to`")
                    continue
            elif has_transition:
                f.error(doc.rel, f"{where} `kind: {kind}` is prose-only — remove `from`/`to`")
                continue
            else:
                continue

            target = by_id.get(ent)
            if target is None:
                continue
            tfield = kind_fields.get(kind)

            # `from`/`to` are checked against whatever governs that field on the
            # target: an enum for `status`, an id reference for location/affiliation.
            for slot in ("from", "to"):
                val = d[slot]
                if kind == "status":
                    vname = vocab["bindings"].get(target.type, {}).get("status")
                    allowed = vocab["vocabularies"].get(vname, {})
                    if vname and val not in allowed:
                        f.error(doc.rel, f"{where}.{slot}: `{val}` is not in vocabulary "
                                         f"`{vname}` for {target.type} `{ent}`")
                elif kind in CHANGE_REFS:
                    resolve(val, CHANGE_REFS[kind], by_id, doc, f"{where}.{slot}", f)

            if ordinal is not None and decision == in_canon:
                out.append(Change(ent, kind, d["from"], d["to"], d.get("summary", ""),
                                  ev, ordinal, doc.rel, str(doc.id), i))
    return out


def ordinal_of(event_id, by_id):
    """An event's place in the order, or None if the id is not an event's or
    the event's `ordinal` is not a whole number."""
    doc = by_id.get(event_id) if isinstance(event_id, str) else None
    if doc is None or doc.type != "event":
        return None
    o = doc.fm.get("ordinal")
    return o if isinstance(o, int) and not isinstance(o, bool) else None


def state_as_of(entity_id, fieldname, target_ordinal, by_id, changes_by_key):
    """The value of a field at the START of the given event.

    A canon change recorded at event N is the *result* of event N, so it has not
    happened yet when a mod that first runs at event N begins. Everything strictly
    before N has. This is what lets a mod use an NPC who dies in that same
    event without the precondition failing against its own consequences.

    The file holds the value as of its own `as_of` — that is, after every canon
    change up to and including that event. Roll forward or back from there.
    """
    rec = by_id.get(entity_id)
    if rec is None:
        return None, "unknown entity"
    current = rec.fm.get(fieldname)
    as_of_ord = ordinal_of(rec.fm.get("as_of"), by_id)
    ds = sorted(changes_by_key.get((entity_id, fieldname), []), key=lambda d: d.order)
    if as_of_ord is None or not ds:
        return current, "current value"
    if as_of_ord < target_ordinal:
        # Roll forward through any change recorded after `as_of` but before the target.
        later = [d for d in ds if as_of_ord < d.ordinal < target_ordinal]
        if later:
            return later[-1].to, f"approved canon change from {later[-1].source}, not yet applied"
        return current, "current value"
    # `as_of` is at or past the target: undo everything from the target onward.
    back = [d for d in ds if target_ordinal <= d.ordinal <= as_of_ord]
    if back:
        return back[0].frm, f"as of the start of that event, before {back[0].source}"
    return current, "current value"


def first_event_ordinal(doc, by_id):
    """The ordinal of the earliest event a mod lists, or None if it lists none."""
    ordinals = [o for o in (ordinal_of(e, by_id) for e in mod_events(doc)) if o is not None]
    return min(ordinals) if ordinals else None


def check_preconditions(docs, by_id, changes_by_key, f):
    """W9: a `requires` clause that does not hold as of the mod's first event."""
    for doc in docs:
        if doc.type != "mod":
            continue
        reqs = doc.fm.get("requires")
        if not reqs:
            continue
        if not isinstance(reqs, list):
            f.error(doc.rel, "`requires` must be a list of clauses")
            continue
        target_ord = first_event_ordinal(doc, by_id)
        for i, clause in enumerate(reqs):
            where = f"requires[{i}]"
            if clause is None:
                continue  # Wrongly shaped, and already reported by `well_shaped`.
            if not isinstance(clause, dict) or "entity" not in clause or "field" not in clause:
                f.error(doc.rel, f"{where} needs `entity` and `field`")
                continue
            if ("equals" in clause) == ("in" in clause):
                f.error(doc.rel, f"{where} needs exactly one of `equals` or `in`")
                continue
            ent, fld = clause["entity"], clause["field"]
            if ent not in by_id:
                if is_submission(doc):
                    f.warn(doc.rel, f"{where} `entity: {ent}` does not resolve — "
                                    f"the Mod Writer's slug, to be mapped at intake")
                else:
                    f.error(doc.rel, f"{where} `entity: {ent}` does not resolve")
                continue
            if target_ord is None:
                actual, how = by_id[ent].fm.get(fld), "current value (mod has no event yet)"
            else:
                actual, how = state_as_of(ent, fld, target_ord, by_id, changes_by_key)
            expected = clause.get("equals", clause.get("in"))
            ok = actual == expected if "equals" in clause else actual in expected
            if not ok:
                f.warn(doc.rel, f"{where} expects `{ent}.{fld}` to be "
                                f"{expected!r} but it is {actual!r} ({how})")


def check_changes_applied(changes, kind_fields, by_id, f):
    """W10: a canon change was approved but never applied to the registry."""
    latest = {}
    for d in changes:
        key = (d.entity, d.kind)
        if key not in latest or d.order > latest[key].order:
            latest[key] = d
    for (ent, kind), d in sorted(latest.items()):
        rec = by_id.get(ent)
        if rec is None:
            continue
        fld = kind_fields[kind]
        current = rec.fm.get(fld)
        matches = (d.to in current) if isinstance(current, list) else (current == d.to)
        if not matches:
            f.warn(rec.rel, f"`{fld}` is {current!r} but the latest approved {kind} change "
                            f"({d.source}) says it should be {d.to!r} — "
                            f"approved but not applied")
        as_of_ord = ordinal_of(rec.fm.get("as_of"), by_id)
        if as_of_ord is not None and as_of_ord < d.ordinal:
            f.warn(rec.rel, f"`as_of` is {rec.fm.get('as_of')} but {d.source} records a "
                            f"{kind} change at {d.event} — advance `as_of`")


def check_alias_collisions(docs, f):
    """W11: an alias claimed by more than one entity makes name lookup ambiguous."""
    claims = {}
    for doc in docs:
        if doc.type not in ENTITY_TYPES:
            continue
        for alias in doc.fm.get("aliases") or []:
            claims.setdefault(str(alias).strip().lower(), []).append(doc)
    for alias, owners in sorted(claims.items()):
        if len(owners) > 1:
            ids = ", ".join(sorted(str(d.id) for d in owners))
            f.warn(owners[0].rel, f"alias {alias!r} is claimed by {len(owners)} entities "
                                  f"({ids}) — name lookup is ambiguous")


def check_body_mentions(docs, by_id, f):
    """W8: an entity named in a mod or timeline body but missing from its links."""
    lookup = []
    for doc in docs:
        if doc.type not in ENTITY_TYPES:
            continue
        terms = {str(doc.id)}
        terms |= {str(a) for a in (doc.fm.get("aliases") or [])}
        for t in terms:
            if len(t) >= MIN_ALIAS_SCAN_LEN:
                lookup.append((t.lower(), doc, t))

    for doc in docs:
        link_field = LINK_FIELD.get(doc.type)
        if link_field is None:
            continue
        links = doc.fm.get(link_field) or {}
        if not isinstance(links, dict):
            continue
        linked = {i for ids in links.values() if isinstance(ids, list) for i in ids}
        body = INLINE_CODE_RE.sub(" ", CODE_FENCE_RE.sub(" ", doc.body))
        lowered = body.lower()
        hits = {}
        for term_lowered, target, term in lookup:
            if target.id in linked or target.id == doc.id:
                continue
            # A plain search is far cheaper than a pattern, and nearly every
            # name is absent from nearly every body. Only a name that does
            # appear is then checked for standing as a word of its own.
            if term_lowered not in lowered:
                continue
            if re.search(rf"\b{re.escape(term)}\b", body, re.I):
                hits.setdefault(target.id, set()).add(term)
        for eid, terms in sorted(hits.items()):
            shown = ", ".join(sorted(terms))
            f.warn(doc.rel, f"body mentions `{eid}` (matched: {shown}) but it is not in "
                            f"`{link_field}` — add it, or rename to avoid the clash")


def check_orphans(docs, by_id, f):
    """W13: an entity nothing references."""
    referenced = set()
    for doc in docs:
        for fieldname, _ in REFS.get(doc.type, {}).items():
            v = doc.fm.get(fieldname)
            referenced.update(i for i in (v if isinstance(v, list) else [v])
                              if isinstance(i, (str, int)))
        links = doc.fm.get(LINK_FIELD.get(doc.type))
        if isinstance(links, dict):
            for ids in links.values():
                if isinstance(ids, list):
                    referenced.update(ids)
        for d in doc.fm.get("canon_changes") or []:
            if isinstance(d, dict):
                referenced.add(d.get("entity"))
    for doc in docs:
        if doc.type in ENTITY_TYPES and doc.id not in referenced:
            f.warn(doc.rel, "nothing references this entity — unused, or a link is missing")


def check_generated_freshness(gen, head, f):
    """W12: a derived artifact built from a commit that is no longer HEAD.

    `head` is the World's current commit, or None when it is not in git (or the
    caller does not know), in which case there is nothing to compare against.
    """
    if not head:
        return
    for doc in gen:
        stamp = doc.fm.get("generated_from_commit")
        if not stamp:
            f.warn(doc.rel, "generated file has no `generated_from_commit` stamp")
        elif not head.startswith(str(stamp)):
            f.warn(doc.rel, f"generated from {stamp}, HEAD is {head[:len(str(stamp))]} — "
                            f"stale, regenerate before relying on it")


def check_dry_runs(docs, structure, f):
    """Each Mod's story against the Dry Run convention, at the World's
    strictness: none when `off`; warnings when `encouraged`, and only for a
    Mod that uses the convention at all; errors when `required`, including for
    a Mod with no structure."""
    from ._story import story

    if structure == "off":
        return
    report = f.error if structure == "required" else f.warn
    for doc in docs:
        if doc.type != "mod":
            continue
        told = story(doc.body)
        if not told.structured and structure != "required":
            continue
        for message in told.problems + told.gaps:
            report(doc.rel, message)


class PathReader:
    """The Paths of a World's reports, each read against its Mod's story from
    where play stopped before it. Each story and each Path is read once."""

    def __init__(self, docs, by_id):
        from ._story import story

        self._story = story
        self.by_id = by_id
        self.ordered = reports_by_mod(docs, by_id)
        self.stories, self.walked, self.lines_by_mod = {}, {}, {}
        self.stopped, self.done = {}, set()

    def told(self, mod):
        if mod.id not in self.stories:
            self.stories[mod.id] = self._story(mod.body)
        return self.stories[mod.id]

    def lines(self, mod):
        if mod.id not in self.lines_by_mod:
            self.lines_by_mod[mod.id] = LinesOfPlay(self.ordered.get(mod.id, []), self.by_id)
        return self.lines_by_mod[mod.id]

    def last_stop(self, mod, before=None, group=None, ordinal=None):
        """Where play stopped on `mod` before the report `before`, or after
        its last report when `before` is None, as a `LastStop`, for a report
        in `group`. With `before`, `group` is that report's own when None.
        Without `before`, `ordinal` is the Event of the report to come, as
        its ordinal, or None for the Event of the Mod's last report.

        It is where the lines of play the report follows on from stopped (see
        `LinesOfPlay`): the end of the Path of the last report on each that
        ran; no earlier report; or not known, when that report has no Path
        that fits, or `before` has no place in the order. A report that
        follows several Groups may start where any of them stopped."""
        from ._path import LastStop

        filed = self.ordered.get(mod.id, [])
        if before is None:
            follows = self.lines(mod).follow(group, ordinal)
        elif before not in filed:
            return LastStop(known=False)
        elif group is None or group == group_of(before):
            follows = self.lines(mod).follows[before.rel]
        else:
            follows = LinesOfPlay(filed[:filed.index(before)], self.by_id).follow(
                group, ordinal_of(before.fm.get("event"), self.by_id))
        return self.stop_after(mod, follows)

    def stop_after(self, mod, reports):
        """Where play stopped after any of `reports`, each the last on a line
        of play, or None for the start of the Mod."""
        from ._path import LastStop

        self.read(mod)
        stops = [LastStop() if report is None else self.stopped[report.rel]
                 for report in reports]
        if not all(stop.known for stop in stops):
            return LastStop(known=False)
        passages = list(dict.fromkeys(p for stop in stops for p in stop.passages))
        if len(passages) > 1:
            return LastStop(among=tuple(passages))
        return LastStop(passages[0]) if passages else LastStop()

    def read(self, mod):
        """Read every report on `mod` once, in order: its Path, from where
        play stopped before it, and where play stopped after it. Each report
        follows on only from reports before it, so one pass reads them all."""
        from ._path import LastStop, check_path, has_path

        if mod.id in self.done:
            return
        self.done.add(mod.id)
        lines = self.lines(mod)
        for report in self.ordered.get(mod.id, []):
            before = self.stop_after(mod, lines.follows[report.rel])
            if has_path(report.fm.get("path")) and self.told(mod).playable:
                self.walked[report.rel] = check_path(self.told(mod), report.fm.get("path"),
                                                     continues_from=before)
            if report.fm.get("ran") is False:
                self.stopped[report.rel] = before
            elif report.rel not in self.walked:
                self.stopped[report.rel] = LastStop(known=False)
            else:
                end = self.walked[report.rel].end
                self.stopped[report.rel] = LastStop(known=False) if end is None \
                    else LastStop(end.name)

    def path_of(self, doc, mod):
        """The report's Path, read from where play stopped before it."""
        from ._path import check_path

        self.read(mod)
        if doc.rel not in self.walked:
            self.walked[doc.rel] = check_path(self.told(mod), doc.fm.get("path"),
                                              continues_from=self.last_stop(mod, doc))
        return self.walked[doc.rel]


def check_paths(docs, by_id, f):
    """Each report's `path` against its Mod's Dry Run. A report with no
    `path` is not checked.

    A Path may start where the Path of the report before it on the same Mod
    stopped (see `PathReader.last_stop`), or at any scene when that is not
    known.
    """
    from ._path import has_path

    reader = PathReader(docs, by_id)
    for doc in docs:
        if doc.type != "after-action" or not has_path(doc.fm.get("path")):
            continue
        mod_id = doc.fm.get("mod")
        mod = by_id.get(mod_id) if isinstance(mod_id, str) else None
        if mod is None or mod.type != "mod":
            continue
        told = reader.told(mod)
        if not told.playable:
            f.warn(doc.rel, f"has a `path`, but mod `{mod.id}` has no Dry Run to check it "
                            f"against — {told.problems[0]}")
            continue
        walked = reader.path_of(doc, mod)
        for problem in walked.problems:
            f.error(doc.rel, problem)
        finished = doc.fm.get("finished")
        if walked.finished is None or not isinstance(finished, bool) \
                or walked.finished == finished:
            continue
        if walked.finished:
            where, why = "outcome", "an ending reached leaves the Mod nothing to play"
        else:
            where, why = "scene", "play that stopped at a scene has more of the Mod to play"
        f.warn(doc.rel, f"`path` ends at the {where} `{walked.end.name}`, but the report "
                        f"says `finished: {str(finished).lower()}` — {why}. Say "
                        f"`finished: {str(walked.finished).lower()}`, or correct the Path")


def run_checks(files, head=None, dry_run_structure=None):
    """Run every check over a World's files.

    `dry_run_structure` overrides the World's setting in `world.yml`.

    Returns `(docs, by_id, findings)`. Reference checks need the whole World, so
    this always checks all of it; callers narrow the findings afterwards.
    """
    from . import _settings

    vocab = load_vocab()
    f = Findings()
    settings = _settings.read(files, f)
    if dry_run_structure is not None:
        settings = _settings.WorldSettings(dry_run_structure)
    docs, by_id, generated = collect_docs(files, f)

    for doc in docs:
        check_fields(doc, f)
        check_enums(doc, vocab, f)
        check_refs(doc, by_id, f)
        if doc.type == "timeline":
            check_timeline(doc, f)
        elif doc.type == "mod":
            check_mod_placement(doc, vocab, by_id, f)
        elif doc.type == "after-action":
            check_report_placement(doc, by_id, f)
        elif doc.type == "interlude-changes":
            check_interlude_placement(doc, by_id, f)

    check_events(docs, f)
    check_finished(docs, by_id, vocab, f)
    check_parallel_changes(docs, by_id, vocab, f)

    changes = collect_changes(docs, by_id, vocab, f)
    changes_by_key = {}
    kind_fields = vocab["canon_change_kind_fields"]
    for d in changes:
        changes_by_key.setdefault((d.entity, kind_fields[d.kind]), []).append(d)

    check_preconditions(docs, by_id, changes_by_key, f)
    check_changes_applied(changes, kind_fields, by_id, f)
    check_alias_collisions(docs, f)
    check_body_mentions(docs, by_id, f)
    check_orphans(docs, by_id, f)
    check_generated_freshness(generated, head, f)
    check_dry_runs(docs, settings.dry_run_structure, f)
    check_paths(docs, by_id, f)
    return docs, by_id, f
