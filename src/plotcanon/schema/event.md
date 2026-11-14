# `event` — the campaign clock

`canon/events/<id>.md`. One file per game event or interlude. **This is the only
place in the repo where time is defined.** Everything else references an event id
and inherits its timing.

**Every event belongs to one campaign**, named in `campaign`. The clock itself
is world-wide: `ordinal` is unique across every campaign in the world, so a
canon change reported in one campaign can be ordered against a mod in another.

Create these ahead of time wherever you can. A mod cannot list an event that
does not exist yet.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. Convention: `eNN-short-name` — the `eNN` prefix is a human convenience, `ordinal` is what actually sorts. |
| `type` | ● | `event` | |
| `campaign` | ● | id | `canon/campaigns/`. The campaign this event is part of. |
| `ordinal` | ● | int | **The canonical sort key.** Unique and gapless across all events in the world, whatever their campaign. |
| `period_type` | ● | `enum:period_type` | `event` for a game, `interlude` for a downtime period. |
| `aliases` | ● | text[] | Display names. Include the plain form authors will say out loud, e.g. `"Event 8"`. |
| `real_date` | ● | date | First day. |
| `real_date_end` | ○ | date | Last day. Omit for single-day events and interludes. |
| `in_world` | ● | text | Free text, and **authoritative**. Your setting has no hard calendar, so this is a phrase, not a date. |
| `status` | ● | `enum:event_status` | |

A cancelled event **keeps its ordinal**. Renumbering would silently rewrite the
ordering of every document that references a later event.

Interludes take their own ordinal in sequence, so downtime sorts correctly
between the events it sits between.

## Body

`## Summary` · `## GM Notes`

Short. The event file is a clock entry, not a writeup — what happened lives in
the mods and after-actions that point at it.

## Example

```markdown
---
id: e08-harvest-mourn
type: event
campaign: greymoor
ordinal: 8
period_type: event
aliases: ["Harvest Mourn", "Event 8"]
real_date: 2026-10-17
real_date_end: 2026-10-19
in_world: "late autumn, the year after the Siege"
status: planned
---

## Summary

Three days at Greymoor. The Ashen Order's move on the chapel is the spine of
the weekend.

## GM Notes

Varen's reveal is scheduled here. Do not let an author burn it earlier.
```

An interlude, for comparison:

```markdown
---
id: e08b-the-long-frost
type: event
campaign: greymoor
ordinal: 9
period_type: interlude
aliases: ["The Long Frost", "downtime after Harvest Mourn"]
real_date: 2026-10-20
in_world: "the first hard frost"
status: complete
---
```
