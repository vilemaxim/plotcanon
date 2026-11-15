# `plot`

`canon/plots/<id>.md`. A narrative through-line that runs across several mods.
A plot lists the mods that advance it in `mods:`, in order. A plot belongs to the world, so its mods can come from any campaign.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. |
| `type` | ● | `plot` | |
| `aliases` | ● | text[] | What people call this plot. |
| `status` | ● | `enum:plot_status` | |
| `as_of` | ● | event-id | |
| `entities` | ○ | id[] | The NPCs, factions and locations this plot turns on. |
| `mods` | ○ | id[] | Mods that advance it, **in intended order**. |
| `canon` | ● | `enum:canon` | |
| `visibility` | ● | `enum:visibility` | |
| `owner` | ○ | text | Who is steering this plot. |
| `tags` | ○ | text[] | |

`dormant` is the important value: not closed, nothing currently advancing it,
free for a Mod Writer to pick up. `abandoned` means it will not conclude — do not
build on it. `resolved` means reopening is a deliberate act, not an oversight.

## Body

`## Premise` · `## Current State` · `## Where It Could Go` · `## GM Notes`

`## Where It Could Go` is written for other Mod Writers. It is the main place a review
across plots looks for weaving opportunities.

## Example

```markdown
---
id: siege-of-greymoor
type: plot
aliases: ["The Siege of Greymoor", "the Greymoor plot"]
status: open
as_of: e08-harvest-mourn
entities: [varen-ashcroft, sister-oleen, ashen-order, greymoor-chapel]
mods: [a-debt-in-copper, the-ashen-vigil]
canon: approved
visibility: gm-only
owner: alex
tags: [faction-war]
---

## Premise

The Ashen Order wants Greymoor and is taking it a building at a time, legally
where it can and otherwise where it must.

## Current State

The Order holds the chapel as of Harvest Mourn. The town council has not yet
acknowledged this out loud.

## Where It Could Go

- The council splits over whether to contest the chapel. Good talky mod.
- Whoever reads the chapel register learns which councillors already signed.
- Varen is loose and hunted by both sides. Available to any Mod Writer who wants him.

## GM Notes

The Order is not the villain here and should not read as one until at least e10.
```
