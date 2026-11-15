# `npc`

`canon/npcs/<id>.md`. One file per NPC.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. Never changes. |
| `type` | ● | `npc` | |
| `aliases` | ● | text[] | Every name this NPC is known by, including titles and false names. Keep it fed — this is how Mod Writers and Obsidian find them. |
| `status` | ● | `enum:npc_status` | A claim about `as_of`, not about now. |
| `as_of` | ● | event-id | The event `status` and `## Current Situation` are true as of. |
| `factions` | ○ | id[] | `canon/factions/`. |
| `location` | ○ | id \| null | `canon/locations/`. `null` is meaningful — use it when they are nowhere fixed. |
| `plots` | ○ | id[] | `canon/plots/` they are entangled in. |
| `first_seen` | ○ | event-id | Or the literal `pre-campaign`. |
| `canon` | ● | `enum:canon` | |
| `visibility` | ● | `enum:visibility` | |
| `owner` | ○ | text | Plot-team handle who maintains this NPC. |
| `tags` | ○ | text[] | Free-form. Not validated. |

### On `status`

`dead` and `final-death` are different claims and the distinction is the whole
point of having both. Your world can reverse `dead`; a mod using a `dead`
NPC gets a warning and must explain the return. `final-death` is an error.

`missing` versus `departed`: `missing` means canon does not know where they are
and their reappearance is a story in itself. `departed` means alive and elsewhere,
usable with a travel justification.

`unknown` is a legitimate state. Use it rather than guessing — the reconciler
treats it as "ask", which is what you want.

## Body

`## Summary` · `## Background` · `## Portrayal` · `## Personality & Goals` ·
`## Knowledge & Secrets` · `## Relationships` · `## Current Situation` · `## GM Notes`

- **`## Background`** — pre-campaign only, and effectively static. This is the
  part of an NPC that is not derivable from anything else in the repo.
- **`## Portrayal`** — appearance, voice, bearing, costume and casting needs.
  Written for whoever plays them on the night.
- **`## Relationships`** — reference other entities by id.
- **`## Current Situation`** — where they are and what they want, true as of `as_of`.

### There is deliberately no `## History` section

An NPC's in-campaign history is fully reconstructable from the mods that
list them in `features` and the after-action canon changes that name them. Writing it
into the NPC file would duplicate that record, and the copy would go stale
silently the first time someone forgot to update it.

**To read an NPC's history, generate their POV summary** (`/pov <id>`). That is
what the involvement links and canon changes are for.

## Example

```markdown
---
id: varen-ashcroft
type: npc
aliases: ["Varen Ashcroft", "The Ashen Knight", "Varen", "the knight in grey"]
status: missing
as_of: e08-harvest-mourn
factions: [ashen-order]
location: null
plots: [siege-of-greymoor]
first_seen: e03-hollow-night
canon: approved
visibility: gm-only
owner: alex
tags: [noble, antagonist]
---

## Summary

A disgraced knight who has spent three years buying his way back into a family
that no longer wants him.

## Background

Second son of the Ashcrofts of Greymoor. Stripped of his commission after the
retreat at Kell's Ford — a retreat he ordered and was right to order.

## Portrayal

Mid-forties, grey at the temples, immaculate in a way that costs him effort.
Speaks quietly and makes people lean in. Costume: dark grey, no house colours.
Needs a competent fighter — he is expected to lose the chapel duel convincingly.

## Personality & Goals

Wants his name back and has stopped caring what it costs. Courteous to everyone,
loyal to almost no one.

## Knowledge & Secrets

Knows the chapel's lower door was never sealed. Will trade that for a name on a
charter and nothing less.

## Relationships

- `sister-oleen` — she absolved him once and he has never forgiven her for it.
- `pc-tomas-veil` — sees a younger version of himself and finds it unbearable.

## Current Situation

Fled north after the chapel. Whereabouts unknown to anyone in Greymoor,
including the Order, which is now hunting him too.

## GM Notes

He did not betray the party for the Order. He did it to be *seen* betraying them
by someone specific, and that person was not in the room.
```
