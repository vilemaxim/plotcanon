"""Applying an approved Canon Change to an entity's file, and taking it back
out.

These are the rules `load_world` checks when it warns that a change is
approved but not applied. A `factions` change takes `before` out of the list
and puts `after` in, so where it leaves the list depends on every change
before it: factions changes are decided in the order they happened. Any other
field goes from `before` to `after`, and the approved changes to it form a
chain, each taking the field from where the one before left it. `as_of`
moves forward when a change is applied and back when one is taken out.

The caller finds a change's neighbours in the chain and passes them in; what
the changes are and how they are decided is the caller's.
"""

from dataclasses import dataclass

import yaml

from . import editing
from ._checks import Loader, split_frontmatter

FACTIONS = "factions"


@dataclass(frozen=True)
class Change:
    """One Canon Change that moves a field: from `before` to `after`, at the
    Event `event`. `replaced` is what the entity's `as_of` and the field held
    before the change was applied, as `{field: value, "as_of": id}`, if the
    caller kept it."""

    before: object
    after: object
    event: str
    replaced: dict | None = None


class ChangeRefused(Exception):
    """A change cannot be applied or taken out. `reason` says why:

    - `"factions-out-of-order"`: a later factions change is already approved.
    - `"not-a-member"`: the entity is not in the faction `before` names.
    - `"contradicts-previous"`: `before` is not where the previous change left the field.
    - `"contradicts-following"`: `after` is not where the following change starts.
    - `"contradicts-current"`: `before` is not the field's current value.
    - `"followed-on"`: a later approved change follows on from this one, so it
      cannot be taken out first.

    `neighbor` is `"previous"` or `"following"` when the reason involves that
    change, which is `other`; otherwise both are None. `current` is the
    field's current value."""

    def __init__(self, reason, *, neighbor=None, other=None, current=None):
        super().__init__(reason)
        self.reason = reason
        self.neighbor = neighbor
        self.other = other
        self.current = current


def _fields(text):
    raw, _body = split_frontmatter(text)
    try:
        fields = yaml.load(raw, Loader=Loader) if raw is not None else None  # noqa: S506
    except yaml.YAMLError:
        fields = None
    if not isinstance(fields, dict):
        raise editing.CannotEdit("the file has no frontmatter that can be read")
    return fields


def _value(text):
    return text or None


def _ordinal(event, event_ordinal):
    return None if event is None else event_ordinal(event)


def _listed(value):
    return list(value) if isinstance(value, list) else []


def applied(text, field, change, *, previous=None, following=None, event_ordinal):
    """The entity's file `text` with an approved `change` to `field` applied,
    or as it was if `following` already decides the field. `previous` and
    `following` are the approved changes just before and after it to the same
    field, if any. `event_ordinal(event_id)` is the Event's ordinal, or None.
    Raises `ChangeRefused` if the change does not fit, and
    `editing.CannotEdit` if the file cannot be changed."""
    fields = _fields(text)
    if field == FACTIONS:
        if following is not None:
            raise ChangeRefused("factions-out-of-order", neighbor="following", other=following)
        listed = _listed(fields.get(field))
        if change.before and change.before not in listed:
            raise ChangeRefused("not-a-member", current=listed)
        updated = [faction for faction in listed if faction != change.before]
        if change.after and change.after not in updated:
            updated.append(change.after)
        text = editing.set_field(text, field, editing.flow_list(updated))
    else:
        if previous is not None and _value(previous.after) != _value(change.before):
            raise ChangeRefused("contradicts-previous", neighbor="previous", other=previous)
        if following is not None:
            if _value(following.before) != _value(change.after):
                raise ChangeRefused("contradicts-following", neighbor="following",
                                    other=following)
            # A later change already decides the field; this one fits between.
            return text
        current = fields.get(field)
        if _value(current) != _value(change.before):
            raise ChangeRefused("contradicts-current", current=current,
                                neighbor="previous" if previous is not None else None,
                                other=previous)
        text = editing.set_field(text, field, change.after or "null")

    # The entity's state is now as of this change's Event, unless it already
    # stood at a later one.
    as_of = _ordinal(fields.get("as_of"), event_ordinal)
    if as_of is None or as_of < (_ordinal(change.event, event_ordinal) or 0):
        text = editing.set_field(text, "as_of", change.event)
    return text


def unapplied(text, field, change, *, previous=None, following=None, remaining_events=(),
              event_ordinal):
    """The entity's file `text` with an approved `change` to `field` taken
    out. The field goes back to where `previous` left it, or to the change's
    `before` if there is none; a list of factions goes back to what
    `change.replaced` recorded, or, with nothing recorded, loses `after` and
    gets `before` back. `as_of` goes back too, if this change's Event is what
    it stands at: to the latest of what `change.replaced` recorded and
    `remaining_events`, the Events of the entity's other approved changes
    that move a field. With neither, it stays. Raises `ChangeRefused` if
    `following` is given, since a later approved change follows on from this
    one, and `editing.CannotEdit` if the file cannot be changed."""
    if following is not None:
        raise ChangeRefused("followed-on", neighbor="following", other=following)
    fields = _fields(text)
    replaced = change.replaced or {}
    if field == FACTIONS:
        # Factions changes are decided in order, so this is the latest.
        if field in replaced:
            listed = _listed(replaced[field])
        else:
            # Applied before what it replaced was kept: take back out the
            # faction it put in, and put back the one it took out.
            listed = [faction for faction in _listed(fields.get(field))
                      if faction != change.after or change.after == change.before]
            if change.before and change.before not in listed:
                listed.append(change.before)
        text = editing.set_field(text, field, editing.flow_list(listed))
    else:
        restored = previous.after if previous is not None else change.before
        text = editing.set_field(text, field, restored or "null")

    if fields.get("as_of") == change.event:
        candidates = list(remaining_events)
        if replaced.get("as_of"):
            candidates.append(replaced["as_of"])
        known = [c for c in candidates if _ordinal(c, event_ordinal) is not None]
        if known:
            latest = max(known, key=event_ordinal)
            if latest != change.event:
                text = editing.set_field(text, "as_of", latest)
    return text
