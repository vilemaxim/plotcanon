# `timeline`

`canon/timeline/<id>.md`. A dated occurrence that **has no owning mod** —
a world event, an off-event resolution, a death between games, a piece of
history.

## What does not go here

Mods are never duplicated into `canon/timeline/`. A mod that ran is
already on the clock via its `events` list and its after-actions. Copying it
here would create a second account of the same thing, and the two would drift.

The full campaign chronology is a **generated view** (`generated/chronology/`)
that merges mods, after-actions, and these entries, sorted by
`(event.ordinal, slot)`. Do not maintain a chronology by hand.

## Two kinds of entry

**On the clock** — set `event` to an event or interlude id. It sorts with
everything else at that event.

**Pre-campaign** — set `era` and optionally `sort_hint`. These order relative to
*each other* only. They are explicitly unordered against campaign events, because
your setting's in-world time is vague and pretending otherwise would invent
precision that does not exist.

Exactly one of the two is required. Setting both is an error.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. |
| `type` | ● | `timeline` | |
| `aliases` | ● | text[] | What this occurrence is called. |
| `event` | ◐ | event-id | On-the-clock entries. Mutually exclusive with `era`. |
| `era` | ◐ | `enum:era` | Pre-campaign entries. Mutually exclusive with `event`. |
| `sort_hint` | ○ | int | Orders pre-campaign entries against each other. Ignored when `event` is set. |
| `in_world` | ● | text | Free text. For pre-campaign entries this is all the dating there is. |
| `involves` | ○ | same shape as a mod's `features` | Ids only. Feeds POV summaries. |
| `canon` | ● | `enum:canon` | |
| `visibility` | ● | `enum:visibility` | |
| `tags` | ○ | text[] | |

`involves` matters more here than it looks. A historical entry that names an NPC
is part of that NPC's POV summary, and the only way retrieval finds it is
through these links.

## Body

`## What Happened` · `## Consequences` · `## GM Notes`

## Examples

On the clock — something that happened during downtime, with no mod:

```markdown
---
id: the-council-vote-on-the-chapel
type: timeline
aliases: ["the council vote", "the chapel vote"]
event: e08b-the-long-frost
in_world: "the first hard frost"
involves:
  factions: [greymoor-council, ashen-order]
  locations: [greymoor-chapel]
  plots: [siege-of-greymoor]
canon: approved
visibility: public
tags: [greymoor]
---

## What Happened

The council voted four to three not to contest the chapel. No mod covered
this; it was resolved by letter between events.

## Consequences

The Order's hold on the chapel is now tacitly legal. Two councillors who voted
against are looking for someone to fund a challenge.
```

Pre-campaign:

```markdown
---
id: the-retreat-at-kells-ford
type: timeline
aliases: ["Kell's Ford", "the retreat at Kell's Ford"]
era: recent-history
sort_hint: 40
in_world: "two years before the campaign, late summer"
involves:
  npcs: [varen-ashcroft]
  pcs: [pc-tomas-veil]
canon: approved
visibility: player-known
tags: [military]
---

## What Happened

Varen Ashcroft ordered a retreat that cost the ford and saved his company. He
was stripped of his commission for it.

## Consequences

He was right, and being right has not helped him once. Tomas Veil was there and
has never had an answer about it.
```
