"""Which values in a document name other documents, which documents name a
given one, and what to call a document on a page."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from . import _checks


@dataclass(frozen=True)
class Reference:
    """One value in a document that names another document by its id.

    `field` is the frontmatter field it was found in, such as `campaign`,
    `features` or `canon_changes`. `id` is the id it names. `position` is its
    place in a list, counting from 0, or None when the field holds one id.
    `part` says where inside the field it sits: the group of a Mod's
    `features` or a timeline entry's `involves` (`npcs`, `factions`, ...), or
    for a Canon Change `entity`, `from` or `to`, with `position` the change's
    place in `canon_changes`.
    """

    field: str
    id: str
    position: int | None = None
    part: str | None = None


def _is_id(value):
    return isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool))


def references(document):
    """The references a document makes, in the order its fields are listed in
    the schema: plain reference fields, then a Mod's `features` or a timeline
    entry's `involves`, then its Canon Changes.

    Only fields the file format says hold ids are looked at, so a value that
    is not a reference (a Mod Writer's handle, a date) is never returned, even
    when it equals another document's id. A Canon Change's `from` and `to` are
    returned only for the kinds where they name documents (a change of
    location or affiliation); for a change of status they are words. An id
    that names no document in the World is still returned: whether it resolves
    is for `load_world` or `check_file` to say.

    `document` is a `Document`. Returns a list of `Reference`.
    """
    fields = document.fields
    found = []
    for name in _checks.REFS.get(document.type, {}):
        value = fields.get(name)
        if name == "first_seen" and value == _checks.PRE_CAMPAIGN:
            continue
        if isinstance(value, list):
            found += [Reference(name, item, position)
                      for position, item in enumerate(value) if _is_id(item)]
        elif _is_id(value):
            found.append(Reference(name, value))

    link_field = _checks.LINK_FIELD.get(document.type)
    links = fields.get(link_field) if link_field else None
    if isinstance(links, Mapping):
        for group, ids in links.items():
            if group in _checks.LINK_KEYS and isinstance(ids, list):
                found += [Reference(link_field, item, position, group)
                          for position, item in enumerate(ids) if _is_id(item)]

    changes = fields.get("canon_changes") if document.type in _checks.CHANGE_SOURCES else None
    for position, change in enumerate(changes if isinstance(changes, list) else []):
        if not isinstance(change, Mapping):
            continue
        slots = ["entity"]
        if change.get("kind") in _checks.CHANGE_REFS:
            slots += ["from", "to"]
        found += [Reference("canon_changes", change[slot], position, slot)
                  for slot in slots if _is_id(change.get(slot))]
    return found


def referrers(world, document):
    """The documents in a World that refer to a document, each once, in the
    World's order. `document` is a `Document` or an id. A document that names
    itself is included. See `references` for what counts as a reference."""
    target = getattr(document, "id", document)
    return [other for other in world.documents
            if any(ref.id == target for ref in references(other))]


def name_of(world, document):
    """What to call a document on a page: its title, or the first of its
    aliases, or failing both its id. An After-Action Report has neither, so it
    is called after its Mod and Event ("The Low Tide Market at Low Tide"), and
    a record of an Interlude's changes after the Interlude ("Changes during
    ..."). `world` is the `World` the document is in."""
    fields = document.fields
    if document.type == "interlude-changes":
        event = _get(world, fields.get("event"))
        if event is not None:
            return f"Changes during {name_of(world, event)}"
    if document.type == "after-action":
        mod, event = _get(world, fields.get("mod")), _get(world, fields.get("event"))
        if mod is not None and event is not None:
            return f"{name_of(world, mod)} at {name_of(world, event)}"
    title = fields.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    aliases = fields.get("aliases")
    if isinstance(aliases, list) and aliases and str(aliases[0]).strip():
        return str(aliases[0]).strip()
    return str(document.id)


def _get(world, doc_id):
    return world.get(doc_id) if _is_id(doc_id) else None


def vocabulary_fields(document):
    """The fields of a document that hold a value from a vocabulary, as
    `{field: vocabulary name}`, such as `{"state": "mod_state", ...}` for a
    Mod. A Canon Change's `kind` and `decision` are always from the
    `canon_change_kind` and `canon_change_decision` vocabularies. `document`
    is a `Document`, or a document type such as "mod"."""
    doc_type = document if isinstance(document, str) else document.type
    return dict(_checks.load_vocab()["bindings"].get(doc_type) or {})
