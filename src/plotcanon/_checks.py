"""The checks behind `plotcanon.load_world` and `plotcanon.check_file`.

Everything here works on a World held in memory as `{relative path: text}`.
Nothing here reads the disk or runs git; `plotcanon._api.read_directory` and
`plotcanon.cli` do.

Checks that every document has the frontmatter its type requires, that every
enum value comes from the packaged vocabularies, and that every id reference
resolves to a real document.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from importlib import resources
from pathlib import PurePosixPath

import yaml

# Directories whose .md files are validated. Everything else (lore/, schema/,
# .claude/, root docs) is deliberately unschema'd prose.
SCAN_DIRS = ["canon", "inbox", "mods", "after-actions", "generated"]


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
}

# mods/<this>/ holds shelved mods, so no campaign may use it as its id.
SHELVED_DIR = "shelved"

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

    @property
    def order(self):
        """Sort key. Reports at the same event are taken in id order, with
        numbers compared as numbers: `aa-<mod>`, `aa-<mod>-2`, `aa-<mod>-10`."""
        return (self.ordinal, natural_key(self.report_id))


def natural_key(text):
    """Sort key for an id that compares the numbers in it as numbers, so
    `aa-x` comes before `aa-x-2` and that before `aa-x-10`. Only the digits 0
    to 9 count; any other character is compared as text."""
    return [int(part) if part.isascii() and part.isdigit() else part
            for part in re.split(r"([0-9]+)", str(text))]


@dataclass
class Findings:
    errors: list = dc_field(default_factory=list)
    warnings: list = dc_field(default_factory=list)

    def error(self, rel, msg):
        self.errors.append((rel, msg))

    def warn(self, rel, msg):
        self.warnings.append((rel, msg))


FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.S)
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")


def split_frontmatter(text):
    m = FM_RE.match(text.removeprefix("\ufeff"))
    if not m:
        return None, text
    return m.group(1), m.group(2)


def load_vocab():
    """The vocabularies and bindings shipped with this version of the package."""
    text = resources.files("plotcanon").joinpath("schema/vocabularies.yml").read_text(
        encoding="utf-8")
    return yaml.safe_load(text)


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
        raw, body = split_frontmatter(files[rel])
        if raw is None:
            f.error(rel, "no YAML frontmatter block")
            continue
        try:
            fm = yaml.safe_load(raw) or {}
        except yaml.YAMLError as e:
            f.error(rel, f"frontmatter is not valid YAML: {' '.join(str(e).split())}")
            continue
        if not isinstance(fm, dict):
            f.error(rel, "frontmatter must be a mapping")
            continue
        if rel.startswith("generated/"):
            generated.append(Doc(rel, fm, body, "generated", None))
            continue
        typ = fm.get("type")
        if typ not in SCHEMAS:
            f.error(rel, f"unknown or missing `type`: {typ!r}")
            continue
        doc = Doc(rel, fm, body, typ, fm.get("id"))
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
        elif doc.fm[key] is None and key not in ("location", "seat", "controlled_by"):
            f.error(doc.rel, f"required field `{key}` is empty")

    allowed = set(schema["required"]) | set(schema["optional"])
    for key in doc.fm:
        if key not in allowed:
            f.warn(doc.rel, f"unrecognised field `{key}` — typo, or update schema/")

    stem = doc.stem
    if doc.id != stem:
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
        if fieldname not in doc.fm:
            continue
        value = doc.fm[fieldname]
        allowed = vocab["vocabularies"][vocab_name]
        if value not in allowed:
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
        if not isinstance(o, int):
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


def check_report_placement(doc, by_id, f):
    parent = doc.parent
    ev = doc.fm.get("event")
    if ev and parent != f"after-actions/{ev}":
        f.error(doc.rel, f"must live in after-actions/{ev}/, not {parent}/")

    if not isinstance(doc.fm.get("pcs", []), list):
        f.error(doc.rel, "`pcs` must be a list of ids")

    finished = doc.fm.get("finished")
    if finished is not None and not isinstance(finished, bool):
        shown = repr(finished) if isinstance(finished, str) and finished in ("true", "false") \
            else finished
        f.error(doc.rel, f"`finished: {shown}` must be true or false — true if this "
                         f"report is the last on its mod, false if there is more to play")
    if finished is True and doc.fm.get("ran") is False:
        f.error(doc.rel, "`ran: false` with `finished: true` — a mod that did not run was "
                         "not finished by this report. Say `finished: false`")
    for single in ("mod", "event"):
        if isinstance(doc.fm.get(single), (list, dict)):
            f.error(doc.rel, f"`{single}` must be one id, not a list")

    # A mod lists every event it runs at, so a report can only be for one of those.
    mod_id = doc.fm.get("mod")
    mod = by_id.get(mod_id) if isinstance(mod_id, str) else None
    if ev and mod is not None and mod.type == "mod" and ev not in mod_events(mod):
        f.error(doc.rel, f"`event: {ev}` is not in the `events` of mod `{mod.id}` — "
                         f"add it there, or fix this report")


def check_finished(docs, by_id, vocab, f):
    """A mod's reports, read in order, against whether the mod is finished.

    The report that says the mod is finished must be the last one. If another
    report comes after it, both are in error: either may be the one just
    submitted, so each is told about the other. And the mod's own `state`,
    which a person sets, is compared with what its latest report says; a
    disagreement is a warning on the mod, since the state is theirs to bring
    up to date.

    Reports are read by event, then by id (see `natural_key`). A report whose
    event does not resolve has no place in that order and is left out; it is
    already in error.
    """
    reports = {}
    for doc in docs:
        mod = by_id.get(doc.fm.get("mod")) if isinstance(doc.fm.get("mod"), str) else None
        if doc.type != "after-action" or mod is None or mod.type != "mod":
            continue
        ordinal = ordinal_of(doc.fm.get("event"), by_id) \
            if isinstance(doc.fm.get("event"), str) else None
        if ordinal is not None:
            reports.setdefault(mod.id, []).append(((ordinal, natural_key(doc.id)), doc))

    unfinished = vocab["mod_states_unfinished"]
    has_run = vocab["mod_states_that_have_run"]
    for mod_id, filed in sorted(reports.items()):
        filed = [doc for _order, doc in sorted(filed, key=lambda pair: pair[0])]
        ended_by = None
        for report in filed:
            if ended_by is not None:
                f.error(report.rel, f"mod `{mod_id}` was finished by `{ended_by.id}` — a "
                                    f"finished mod cannot be reported on again. If there was "
                                    f"more to play, `{ended_by.id}` should say `finished: false`")
                f.error(ended_by.rel, f"says mod `{mod_id}` is finished, but `{report.id}` "
                                      f"reports on it afterwards — only the last report on a "
                                      f"mod can say `finished: true`")
            elif finishes(report):
                ended_by = report

        if sum(1 for doc in docs if doc.id == mod_id) > 1:
            continue  # Two documents claim this id; that is already an error.
        mod, latest = by_id[mod_id], filed[-1]
        state = mod.fm.get("state")
        fix = "set the state to match, or correct the report"
        if finishes(latest) and state in unfinished:
            f.warn(mod.rel, f"`state: {state}`, but its latest report (`{latest.id}`) says "
                            f"the mod is finished — {fix}")
        elif latest.fm.get("finished") is False and state == vocab["mod_state_finished"]:
            f.warn(mod.rel, f"`state: {state}`, but its latest report (`{latest.id}`) says "
                            f"there is more to play — {fix}")
        elif (latest.fm.get("finished") is False and latest.fm.get("ran") is True
              and state in unfinished and state not in has_run):
            f.warn(mod.rel, f"`state: {state}`, but its latest report (`{latest.id}`) says "
                            f"it has been run and has more to play — {fix}")


def finishes(report):
    """Whether this report is the one that ends its mod. A mod that did not run
    is not finished by the report that says so."""
    return report.fm.get("finished") is True and report.fm.get("ran") is not False


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
        if doc.type != "after-action":
            continue
        changes = doc.fm.get("canon_changes")
        if changes is None:
            continue
        if not isinstance(changes, list):
            f.error(doc.rel, "`canon_changes` must be a list")
            continue
        ev = doc.fm.get("event")
        ordinal = by_id[ev].fm.get("ordinal") if ev in by_id else None

        for i, d in enumerate(changes):
            where = f"canon_changes[{i}]"
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
                elif kind == "location":
                    resolve(val, ["location"], by_id, doc, f"{where}.{slot}", f)
                elif kind == "affiliation":
                    resolve(val, ["faction"], by_id, doc, f"{where}.{slot}", f)

            if ordinal is not None and decision == in_canon:
                out.append(Change(ent, kind, d["from"], d["to"], d.get("summary", ""),
                                  ev, ordinal, doc.rel, str(doc.id)))
    return out


def ordinal_of(event_id, by_id):
    doc = by_id.get(event_id)
    if doc is None or doc.type != "event":
        return None
    o = doc.fm.get("ordinal")
    return o if isinstance(o, int) else None


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
            ids = ", ".join(sorted(d.id for d in owners))
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
                lookup.append((re.compile(rf"\b{re.escape(t)}\b", re.I), doc, t))

    for doc in docs:
        link_field = LINK_FIELD.get(doc.type)
        if link_field is None:
            continue
        links = doc.fm.get(link_field) or {}
        if not isinstance(links, dict):
            continue
        linked = {i for ids in links.values() if isinstance(ids, list) for i in ids}
        body = INLINE_CODE_RE.sub(" ", CODE_FENCE_RE.sub(" ", doc.body))
        hits = {}
        for pattern, target, term in lookup:
            if target.id in linked or target.id == doc.id:
                continue
            if pattern.search(body):
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


def run_checks(files, head=None):
    """Run every check over a World's files.

    Returns `(docs, by_id, findings)`. Reference checks need the whole World, so
    this always checks all of it; callers narrow the findings afterwards.
    """
    vocab = load_vocab()
    f = Findings()
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

    check_events(docs, f)
    check_finished(docs, by_id, vocab, f)

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
    return docs, by_id, f
