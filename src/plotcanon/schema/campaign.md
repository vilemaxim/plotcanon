# `campaign`

`canon/campaigns/<id>.md`. One run of play inside the world, with its own GM or
plot team and its own players. **This repo is one world, and a world has one or
more campaigns.**

A campaign owns its events and its mods: every [event](event.md) and every
[mod](mod.md) names the campaign it belongs to. Everything else — NPCs,
factions, locations, PCs, plots and the timeline — belongs to the world and is
shared by every campaign in it. Those files carry no `campaign` field.

A world with a single GM still has one campaign. Create it before the first
event.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. Also the name of this campaign's folder under `mods/`, so it cannot be `shelved`. |
| `type` | ● | `campaign` | |
| `aliases` | ● | text[] | What people call this campaign. |
| `owner` | ○ | text | Who runs it. |
| `tags` | ○ | text[] | |

## Body

`## Summary` · `## GM Notes`

Short. A campaign file says which run of play this is and who runs it — what
happens in it lives in its events, mods and after-actions.

## Example

```markdown
---
id: greymoor
type: campaign
aliases: ["Greymoor", "the Greymoor campaign"]
owner: alex
---

## Summary

The weekend events set in and around Greymoor.

## GM Notes
```
