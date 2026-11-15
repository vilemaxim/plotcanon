# `pc`

`canon/pcs/<id>.md`. A **lightweight stub**, nothing more.

## The player-data boundary

This repo does not own the player roster or character sheets. A PC stub exists
for exactly one reason: to give a player character a stable id that mods
and after-action canon changes can reference. It is a hook to hang links on.

**PC stubs carry no status field.** No vital state, no "active/retired", no
sheet data, no player contact details. Anything of that kind would be a second
copy of information the roster owns, and the two copies would disagree within a
season.

What happened to a PC lives in the after-action canon changes that name them and in the
POV summary generated from those canon changes. That record is complete, sourced, and
cannot drift — it *is* the primary record.

If you find yourself wanting a status field here, what you actually want is
`/pov <pc-id>`.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. Convention: `pc-<character-name>`, so PC ids are obvious at a glance in a `features` block. |
| `type` | ● | `pc` | |
| `aliases` | ● | text[] | Character name and any in-world titles. Not the player's name. |
| `player` | ● | text | Player handle — enough to know who to ask. Not contact details. |
| `factions` | ○ | id[] | In-world affiliations that matter to the story. |
| `canon` | ● | `enum:canon` | |
| `visibility` | ● | `enum:visibility` | |
| `tags` | ○ | text[] | |

## Body

`## Summary` · `## Plot Hooks` · `## GM Notes`

Keep all three short.

- **`## Summary`** — two or three sentences, as much as a Mod Writer needs to write
  this PC into a mod. Not a biography.
- **`## Plot Hooks`** — what this PC is chasing, owed, or afraid of. This
  is the section Mod Writers actually read.
- **`## GM Notes`** — anything the plot team knows that the player has not
  established in play.

Do not write the PC's history here. It accumulates in after-actions.

## Example

```markdown
---
id: pc-tomas-veil
type: pc
aliases: ["Tomas Veil", "Veil"]
player: sam
factions: [greymoor-council]
canon: approved
visibility: gm-only
tags: [greymoor]
---

## Summary

A young council clerk who keeps ending up in fights he is not equipped for and
winning enough of them to keep going.

## Plot Hooks

- Owed an answer by Varen Ashcroft about Kell's Ford. Has been owed it for two years.
- Wants a seat on the council and is not subtle about it.

## GM Notes

Sam has said out loud they want Tomas to fail at something publicly. Take them
up on it.
```
