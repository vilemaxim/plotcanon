"""Retrieve everything canon records about one entity, in chronological order.

This is the deterministic half of a point-of-view summary. It is a structured
query over feature links and after-action canon changes — never a judgement about
what is relevant. Whoever writes the prose only ever shapes what this emits.
"""

from __future__ import annotations

import re

from ._checks import (
    LINK_KEYS, LINK_FIELD, ENTITY_TYPES, REFS, Findings, collect_docs,
    first_event_ordinal, load_vocab, mod_events, ordinal_of,
)

TYPE_TO_LINK_KEY = {v: k for k, v in LINK_KEYS.items()}

# Pre-campaign material sorts before everything on the clock.
PRE_CAMPAIGN_ORD = float("-inf")


def section(body, heading):
    """Pull one `## Heading` section out of a markdown body."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)",
                  body, re.M | re.S)
    return m.group(1).strip() if m else ""


class NoSuchEntity(Exception):
    """The id asked for is not an entity in this World."""


def build(files, entity_id):
    f = Findings()
    docs, by_id, _generated = collect_docs(files, f)
    in_canon = load_vocab()["canon_change_decision_in_canon"]

    subject = by_id.get(entity_id)
    if subject is None:
        candidates = sorted(
            d.id for d in docs
            if d.type in ENTITY_TYPES and entity_id.lower() in str(d.id).lower()
        )
        hint = f"  Did you mean: {', '.join(candidates)}" if candidates else ""
        raise NoSuchEntity(f"no entity with id `{entity_id}`.{hint}")
    if subject.type not in ENTITY_TYPES:
        raise NoSuchEntity(f"`{entity_id}` is a {subject.type}, not an entity. "
                           f"POV summaries are for npc, faction, pc, location, plot, timeline.")

    link_key = TYPE_TO_LINK_KEY.get(subject.type)
    items = []

    # ── Documents that link to this entity ────────────────────────────────
    for doc in docs:
        link_field = LINK_FIELD.get(doc.type)
        if link_field is None:
            continue
        links = doc.fm.get(link_field)
        if not isinstance(links, dict):
            continue
        linked = link_key and entity_id in (links.get(link_key) or [])
        if not linked:
            continue

        if doc.type == "mod":
            # A mod sits in the chronology at the first event it runs at. Each
            # report under it carries the event that report covers.
            ordinal = first_event_ordinal(doc, by_id)
            items.append({
                "kind": "mod",
                "id": doc.id,
                "path": doc.rel,
                "title": doc.fm.get("title", doc.id),
                "event": next((e for e in mod_events(doc)
                               if ordinal_of(e, by_id) == ordinal), None),
                "events": mod_events(doc),
                "campaign": doc.fm.get("campaign"),
                "ordinal": ordinal if ordinal is not None else PRE_CAMPAIGN_ORD,
                "slot": doc.fm.get("slot") or 0,
                "state": doc.fm.get("state"),
                "mod_writer": doc.fm.get("mod_writer"),
                "premise": section(doc.body, "Premise"),
                "expected": (doc.fm.get("expected_changes") or {}).get(entity_id),
                "reports": [],
            })
        else:
            ev = doc.fm.get("event")
            ordinal = ordinal_of(ev, by_id) if ev else None
            items.append({
                "kind": "timeline",
                "id": doc.id,
                "path": doc.rel,
                "title": (doc.fm.get("aliases") or [doc.id])[0],
                "event": ev,
                "era": doc.fm.get("era"),
                "in_world": doc.fm.get("in_world"),
                "ordinal": ordinal if ordinal is not None else PRE_CAMPAIGN_ORD,
                "slot": doc.fm.get("sort_hint") or 0,
                "what": section(doc.body, "What Happened"),
                "consequences": section(doc.body, "Consequences"),
                "reports": [],
            })

    by_mod = {i["id"]: i for i in items if i["kind"] == "mod"}

    # ── After-action reports naming this entity ───────────────────────────
    loose = []
    for doc in docs:
        if doc.type != "after-action":
            continue
        mine = [d for d in (doc.fm.get("canon_changes") or [])
                if isinstance(d, dict) and d.get("entity") == entity_id]
        pcs = doc.fm.get("pcs")
        attended = isinstance(pcs, list) and entity_id in pcs
        if not mine and not attended:
            continue

        ev = doc.fm.get("event")
        record = {
            "source": doc.rel,
            "id": str(doc.id),
            "event": ev,
            "ordinal": ordinal_of(ev, by_id),
            "ran": doc.fm.get("ran"),
            "mod_runner": doc.fm.get("mod_runner"),
            "attended": attended,
            "canon_changes": [
                {"kind": d.get("kind"), "decision": d.get("decision"),
                 "in_canon": d.get("decision") == in_canon,
                 "from": d.get("from"), "to": d.get("to"),
                 "summary": d.get("summary")}
                for d in mine
            ],
            "divergences": section(doc.body, "Divergences From The Mod"),
        }
        target = by_mod.get(doc.fm.get("mod"))
        if target is not None:
            target["reports"].append(record)
        else:
            # After-action for a mod this entity is not a feature of. Keep it —
            # a canon change is direct evidence of involvement even when the
            # link is missing, and the gap is itself worth reporting.
            ordinal = ordinal_of(ev, by_id)
            loose.append({
                "kind": "after-action-only",
                "id": doc.id,
                "path": doc.rel,
                "title": f"{doc.fm.get('mod')} (not listed in `features`)",
                "event": ev,
                "ordinal": ordinal if ordinal is not None else PRE_CAMPAIGN_ORD,
                "slot": 0,
                "reports": [record],
            })
    items.extend(loose)
    for i in items:
        i["reports"].sort(key=lambda r: (r["ordinal"] if r["ordinal"] is not None
                                         else PRE_CAMPAIGN_ORD, r["id"]))
    items.sort(key=lambda i: (i["ordinal"], i["slot"], str(i["id"])))

    # ── Backlinks: entities that point at this one ────────────────────────
    backlinks = []
    for doc in docs:
        if doc.type not in ENTITY_TYPES or doc.id == entity_id:
            continue
        for fieldname in REFS.get(doc.type, {}):
            v = doc.fm.get(fieldname)
            if entity_id == v or (isinstance(v, list) and entity_id in v):
                backlinks.append({"id": doc.id, "type": doc.type,
                                  "field": fieldname, "path": doc.rel})
    return subject, items, backlinks, by_id


def emit_markdown(subject, items, backlinks, by_id, head, out):
    p = out.append
    p(f"# Retrieval bundle — `{subject.id}` ({subject.type})")
    p("")
    p("Everything canon records about this entity, in chronological order.")
    p("This is a complete, mechanical query over feature links and after-action")
    p("canon changes. It is not a summary and nothing has been judged.")
    p("")
    p(f"- `generated_from_commit`: {head or 'unknown'}")
    p(f"- aliases: {', '.join(str(a) for a in (subject.fm.get('aliases') or []))}")
    if subject.fm.get("status"):
        p(f"- status: **{subject.fm['status']}** as of `{subject.fm.get('as_of')}`")
    p(f"- source file: `{subject.rel}`")
    p(f"- {len(items)} documents involve this entity")
    p("")

    p("## Entity file")
    p("")
    p(subject.body.strip() or "_(empty)_")
    p("")

    p(f"## Chronology ({len(items)} items)")
    p("")
    if not items:
        p("_Nothing in canon references this entity. There is no history to")
        p("summarise — say so rather than inventing one._")
        p("")

    for i in items:
        if i["ordinal"] == PRE_CAMPAIGN_ORD:
            when = f"pre-campaign · {i.get('era') or 'undated'}"
        else:
            when = f"ordinal {int(i['ordinal'])} · `{i['event']}`"
            ev = by_id.get(i["event"])
            if ev is not None:
                when += f" · {ev.fm.get('in_world')}"
        p(f"### [{when}] {i['title']}")
        p("")
        p(f"- kind: {i['kind']} · `{i['id']}` · `{i['path']}`")
        if i.get("state"):
            p(f"- mod state: {i['state']} · mod writer: {i.get('mod_writer')} · "
              f"campaign: `{i.get('campaign')}`")
            if len(i.get("events") or []) > 1:
                p(f"- runs at: {', '.join(f'`{e}`' for e in i['events'])}")
        if i.get("in_world"):
            p(f"- in-world: {i['in_world']}")
        if i.get("expected"):
            p(f"- mod expected of this entity: \"{i['expected']}\"")
        p("")
        for text, label in ((i.get("premise"), "Premise"),
                            (i.get("what"), "What happened"),
                            (i.get("consequences"), "Consequences")):
            if text:
                p(f"**{label}.** {text}")
                p("")
        for rec in i["reports"]:
            if rec["attended"] and not rec["canon_changes"]:
                p(f"**Took part** at `{rec['event']}` (`{rec['source']}`), "
                  f"no canon changes recorded.")
                p("")
                continue
            p(f"**Reported at `{rec['event']}`** (`{rec['source']}`):")
            if rec["ran"] is False:
                p("- mod did not run")
            for d in rec["canon_changes"]:
                # Anything not approved is labelled, so it is never read as canon.
                label = "" if d["in_canon"] else f" **[not canon: {d['decision']}]**"
                if d["from"] is not None or d["to"] is not None:
                    p(f"- `{d['kind']}`{label}: {d['from']} → {d['to']} — {d['summary']}")
                else:
                    p(f"- `{d['kind']}`{label}: {d['summary']}")
            if rec["divergences"]:
                p("")
                p(f"_Divergences from the mod:_ {rec['divergences']}")
            p("")

    p("## Backlinks")
    p("")
    if backlinks:
        p("Entities that reference this one. Context only — their histories are")
        p("not included and must not be invented.")
        p("")
        for b in backlinks:
            p(f"- `{b['id']}` ({b['type']}) via `{b['field']}` — `{b['path']}`")
    else:
        p("_None._")
    p("")
    return out
