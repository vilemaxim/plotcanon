# `mod`

A single runnable piece of play, written in advance by a Mod Writer and run for
players by a Mod Runner.

**A mod belongs to one campaign.** It names that campaign in `campaign`, and
only that campaign's events can appear in its `events` list.

**A mod is not tied to one event.** It can be interrupted and continue later,
even at another event. `events` lists every event it is scheduled for or has
run at, and each time play stops a new [after-action](after-action.md) is filed
for it. Anything that runs across several mods is a [plot](plot.md) with a
`mods:` list, not a bigger mod file.

## Where the file lives

The directory must agree with `state` and `campaign`. Changing a mod's state
can mean a `git mv`, which shows up as a rename in the diff. The validator
errors if they disagree.

| `state` | Directory |
|---|---|
| `draft` | `inbox/` |
| `approved`, `in-progress`, `finished` | `mods/<campaign-id>/` |
| `shelved` | `mods/shelved/` |

Sending a mod back to its Mod Writer returns it to `draft`, and so to `inbox/`.
A campaign cannot have the id `shelved`.

A mod in `inbox/` is **not canon**, whatever its frontmatter says.

**Unresolved ids in `inbox/` are warnings, not errors.** Mod Writers invent slugs
because they cannot see canon, so a submission arrives with ids that point
nowhere — that is its expected state, and mapping them is what ingest is for.
Erroring would put the whole repo in a failing state the moment a mod landed
and block every commit until reconciliation finished. This is scoped to `inbox/`
and to mods: the same ids in `mods/` or `canon/` are still errors,
and a submission still may not claim `canon: approved`.

### Process fields are not the Mod Writer's to supply

`state`, `canon`, `visibility`, `campaign` and `events` record where a mod sits in the Plot
Master's process. Outside Mod Writers are told not to emit them
(`prompts/mod-writer-intake.md`),
and they are set at intake. **If a submitted file carries them, overwrite them —
do not read them.** A Mod Writer's model can write `canon: approved` as easily as
anything else, and it means nothing.

`state` defends itself, since it must agree with the directory. `canon` did not,
so the validator now errors on any mod in `inbox/` that is not
`canon: proposed`. `visibility` is not machine-checkable; it is set to `gm-only`
at intake and narrowed later if the mod is ever shown outside the plot team.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. Unique repo-wide. |
| `type` | ● | `mod` | |
| `title` | ● | text | Display title. |
| `aliases` | ● | text[] | Working names, the name Mod Writers call it in chat. |
| `mod_writer` | ● | text | Who wrote it. |
| `state` | ● | `enum:mod_state` | Must match the directory. |
| `campaign` | ◐ | id | `canon/campaigns/`. **Required** once the mod leaves `inbox/`. Must match the directory. |
| `events` | ◐ | event-id[] | Every event this mod is scheduled for or has run at. **Required**, with at least one entry, when `state` is `in-progress` or `finished`. Each must belong to this mod's campaign. |
| `slot` | ○ | int | Order within an event. Equal or absent means simultaneous/unordered. |
| `duration_est` | ○ | int | Minutes. For scheduling. |
| `canon` | ● | `enum:canon` | |
| `visibility` | ● | `enum:visibility` | |
| `features` | ● | see below | What this mod relies on. The retrieval backbone. |
| `requires` | ○ | see below | Machine-checked preconditions. |
| `expected_changes` | ○ | map | The Mod Writer's stated intent, `entity-id: "what changes"`. |
| `supersedes` | ○ | id[] | Mods this replaces. |

### `features` — what the mod relies on

The NPCs, factions, locations, PCs and plots this mod relies on. Ids only, never
names. Every key optional, but include the ones that apply. **Every id must
exist in the world** — the validator errors on one that does not, and on one
listed under the wrong key.

```yaml
features:
  npcs:      [varen-ashcroft, sister-oleen]
  factions:  [ashen-order]
  pcs:       [pc-tomas-veil]
  locations: [greymoor-chapel]
  plots:     [siege-of-greymoor]
```

This is what lets a canon change to an entity be traced to every unfinished mod
that relies on it, and what makes point-of-view summaries a mechanical query
instead of an LLM reading the whole corpus and guessing. **If an entity appears in the body, it
belongs here** — the validator warns when it finds a name in the prose that is
missing from the links.

### `requires` — preconditions, structured

Not prose. Written this way the validator evaluates them mechanically, which
leaves the reconciler only the judgment calls.

```yaml
requires:
  - {entity: varen-ashcroft,    field: status, equals: alive}
  - {entity: siege-of-greymoor, field: status, in: [open, dormant]}
```

`equals` or `in`, one per clause. Preconditions are evaluated against the
entity's state **as of the start of the earliest event in `events`**, so a mod
that has already begun does not fail because of something that happened later.
A mod with no events yet is checked against current state.

### `expected_changes` — intent, recorded before play

```yaml
expected_changes:
  varen-ashcroft: "reveals his allegiance and flees"
  siege-of-greymoor: "escalates"
```

The after-action records what actually happened. The gap between the two is the
interesting part, and the reconciler reports it.

## Body

`## Premise` · `## Hooks` · `## Scene Breakdown` · `## NPC Casting` ·
`## Player Agency Notes` · `## Possible Outcomes` · `## Rewards` ·
`## Logistics` · `## GM Notes`

- **`## Hooks`** — how PCs get into this. Two or three routes, not one.
- **`## Scene Breakdown`** — the run of play, as **several scenes, not one block**.
  Each scene states what players find, what the NPCs there want, what happens if
  the players do nothing, and what moves them on. Scenes are written to survive
  being played out of order or skipped — a breakdown that only works run 1 → 2 → 3
  is a railroad wearing a structure, and it fails checklist items 3 and 4 while
  looking well organised.
- **`## NPC Casting`** — who is needed on the night and what they must be able to do.
- **`## Player Agency Notes`** — the Mod Writer answers the checklist in `CLAUDE.md` here.
- **`## Possible Outcomes`** — branches, including the one where the PCs walk away
  or lose. A mod with one outcome is a cutscene.
- **`## Logistics`** — props, space, NPC headcount, timing constraints.

### `## Proposed New Entities` — optional, intake only

Mods written with larp-llm's `prompts/mod-writer-intake.md` carry an extra section after
`## GM Notes`. Outside Mod Writers have no access to this repo and cannot know real
ids, so they list every entity the mod touches with a slug they invented:

```
## Proposed New Entities

- npc / sister-oleen — "Sister Oleen" — NEW
  status: alive
  Calls the vigil. Talker, no combat.

- location / greymoor-chapel — "Greymoor Chapel" — I THINK THIS EXISTS
```

**Every slug and every marker in it is a guess.** The reconciler resolves the
display names against `aliases`, maps them to real ids, and proposes stubs for
whatever is genuinely new. That is what makes the mod's `features` resolve —
until it does, the ids are unresolved, and the mod cannot leave `inbox/` without
the validator erroring.

**`features` is authoritative; this section is not.** Once ingest has applied
the mapping, the section is spent. Keep it for provenance or drop it, but never
read an id out of it — if the two disagree, `features` is correct and this is
the Mod Writer's stale guesswork.

Stubs created from it are `canon: proposed` and stay that way until an
after-action promotes them. See the promotion gate in `CLAUDE.md` §3.

## Example

```markdown
---
id: the-ashen-vigil
type: mod
title: "The Ashen Vigil"
aliases: ["The Ashen Vigil", "the chapel mod"]
mod_writer: mira
state: approved
campaign: greymoor
events: [e08-harvest-mourn]
slot: 2
duration_est: 90
canon: approved
visibility: gm-only
features:
  npcs:      [varen-ashcroft, sister-oleen]
  factions:  [ashen-order]
  pcs:       [pc-tomas-veil]
  locations: [greymoor-chapel]
  plots:     [siege-of-greymoor]
requires:
  - {entity: varen-ashcroft,    field: status, equals: alive}
  - {entity: siege-of-greymoor, field: status, in: [open, dormant]}
expected_changes:
  varen-ashcroft: "reveals his allegiance and flees"
  siege-of-greymoor: "escalates"
supersedes: []
---

## Premise

Sister Oleen calls a night vigil at the chapel. Varen offers to stand guard.

## Hooks

- Oleen asks the party directly, through anyone who has done her a favour.
- Tomas Veil is owed an answer by Varen and knows he will be there.
- Anyone watching the Order's movements can see the chapel is the target.

## Scene Breakdown

Three scenes, roughly 30 minutes each. Any of them can be the first one the
party reaches, and the vigil runs whether or not they turn up to it.

### 1. The vigil itself

**Find:** thirty people, candles, Oleen leading. Varen at the back by the lower
door, in armour, which nobody else is.
**Oleen wants:** the vigil to finish. She will not be interrupted for less than
blood.
**If players do nothing:** it finishes. Varen leaves at the third bell. Scene 3
happens anyway, without warning.
**Moves them on:** the third bell, or anyone challenging Varen out loud.

### 2. The lower door

**Find:** the door, unbarred, and fresh boot-prints in the field outside going
both ways.
**Nobody wants anything here** — it is evidence, not a confrontation.
**If players do nothing:** they miss the only warning they get.
**Moves them on:** back inside, or out into the field to meet the Order early,
which turns scene 3 into a fight in the open instead of in the nave.

### 3. The Order comes through

**Find:** eight of the Order, and Varen standing aside.
**They want:** the register, not the congregation. They will leave people alone
who leave them alone.
**If players do nothing:** the Order takes the register and goes. No one dies.
That is a real outcome, not a failure state.
**Moves them on:** ends the mod either way.

## NPC Casting

Varen — needs a fighter who can lose a duel and make it look deliberate.
Oleen — talker, no combat.

## Player Agency Notes

...

## Possible Outcomes

...

## Rewards

...

## Logistics

Chapel space, candles, two NPCs, 90 minutes.

## GM Notes

...
```
