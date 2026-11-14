# `faction`

`canon/factions/<id>.md`. Any body that can act as a body — an order, a house,
a guild, a warband, a town council.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. |
| `type` | ● | `faction` | |
| `aliases` | ● | text[] | Formal name, common name, what their enemies call them. |
| `status` | ● | `enum:faction_status` | |
| `as_of` | ● | event-id | |
| `seat` | ○ | id \| null | `canon/locations/` — where they are based. |
| `members` | ○ | id[] | `canon/npcs/`. Notable members only; this is not a roster. |
| `allies` | ○ | id[] | `canon/factions/`. |
| `rivals` | ○ | id[] | `canon/factions/`. |
| `plots` | ○ | id[] | |
| `canon` | ● | `enum:canon` | |
| `visibility` | ● | `enum:visibility` | |
| `owner` | ○ | text | |
| `tags` | ○ | text[] | |

`fractured` earns its place: a faction that still exists but no longer acts with
one voice is a common and very usable plot state, and collapsing it into
`active` or `disbanded` loses the thing that makes it interesting.

`members` lists NPCs worth naming. PC membership is not tracked here — PCs join
and leave things constantly and the roster is not this repo's to own.

## Body

`## Summary` · `## Goals` · `## Structure & Notable Members` · `## Standing` ·
`## Current Situation` · `## GM Notes`

`## Standing` — how they are regarded, and by whom. `## Current Situation` is
true as of `as_of`.

## Example

```markdown
---
id: ashen-order
type: faction
aliases: ["The Ashen Order", "the Order", "greycloaks"]
status: active
as_of: e08-harvest-mourn
seat: greymoor-chapel
members: [varen-ashcroft]
allies: []
rivals: [greymoor-council]
plots: [siege-of-greymoor]
canon: approved
visibility: public
owner: alex
tags: [religious, expansionist]
---

## Summary

A penitential order that buys and inherits its way into places rather than
taking them, and is very patient about it.

## Goals

Hold the chapel, then the register, then the council.

## Structure & Notable Members

Led by a council of three, none of whom have appeared in play yet. Varen
Ashcroft is their instrument in Greymoor and does not know he is expendable.

## Standing

Respected in the countryside, distrusted in town, and nobody has yet said out
loud that they are conquering anything.

## Current Situation

Holds the chapel as of Harvest Mourn. Also now hunting Varen, who ran.

## GM Notes

They are not the villains. Do not play them as villains before e10.
```
