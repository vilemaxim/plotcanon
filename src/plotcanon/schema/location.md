# `location`

`canon/locations/<id>.md`. Anywhere play happens or that a mod is about. Create
one when somewhere gets referenced by more than one mod, or when who controls
it can change.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. |
| `type` | ● | `location` | |
| `aliases` | ● | text[] | |
| `status` | ● | `enum:location_status` | |
| `as_of` | ● | event-id | |
| `region` | ○ | text | Free text, or a location id if you keep a place hierarchy. |
| `controlled_by` | ○ | id \| null | `canon/factions/`. `null` when nobody holds it. |
| `plots` | ○ | id[] | |
| `canon` | ● | `enum:canon` | |
| `visibility` | ● | `enum:visibility` | |
| `owner` | ○ | text | |
| `tags` | ○ | text[] | |

`contested` is the value that does real work — it says control is actively
disputed right now, which is exactly the state a Mod Writer needs to know about
before setting a mod there.

`ruined` is still somewhere you can go. `lost` is not.

## Body

`## Summary` · `## Description` · `## Who Holds It` · `## Current Situation` · `## GM Notes`

`## Description` is written for whoever has to dress the space or describe it on
the night. `## Current Situation` is true as of `as_of`.

## Example

```markdown
---
id: greymoor-chapel
type: location
aliases: ["Greymoor Chapel", "the chapel", "St Aelin's"]
status: contested
as_of: e08-harvest-mourn
region: Greymoor
controlled_by: ashen-order
plots: [siege-of-greymoor]
canon: approved
visibility: public
owner: alex
tags: [religious, greymoor]
---

## Summary

The oldest building in Greymoor and the only one the town never got around to
putting in writing.

## Description

Low, cold, older than it looks. Candles rather than windows. A nave that holds
maybe thirty, and a lower door onto the field that everyone had forgotten about.

## Who Holds It

Held by the Ashen Order since Harvest Mourn. The council has not acknowledged
this out loud, which is why the status is `contested` rather than settled.

## Current Situation

Order banners up, town using the side entrance, nobody talking about it.

## GM Notes

The chapel register is still inside and lists which councillors already signed
with the Order. Sara Korr took a copy at e08 and has not read it.
```
