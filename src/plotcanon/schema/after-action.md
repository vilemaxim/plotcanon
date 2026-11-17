# `after-action`

`after-actions/<event-id>/<id>.md`. A Mod Runner's account of what happened
during **one continuous stretch of playing a mod**, recorded as a list of
proposed **canon changes**.

**One is filed every time play stops**, so a mod can have several: one per
event it ran at, and more than one at the same event if it was interrupted and
picked up again. Each names the one event it covers, and that event must be in
the mod's `events` list. When a mod splits its players into **Groups** that
play side by side, each Group's Mod Runner files their own report, and says
which Group it covers in `group`.

Ids are unique repo-wide and equal to the filename stem, and the bare mod id
already belongs to the mod. The first report on a mod is `aa-<mod-id>`; later
ones are `aa-<mod-id>-2`, `aa-<mod-id>-3`. Reports at the same event are applied
in id order.

The canon change list does two jobs at once, which is why it is structured
rather than prose: the reconciler and the registry maintainer consume it to
update canon, and the POV summary consumes it for per-mod detail. One capture,
two payoffs.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. Convention: `aa-<mod-id>`, then `aa-<mod-id>-2` and so on. |
| `type` | ● | `after-action` | |
| `mod` | ● | id | The mod this reports on. |
| `event` | ● | event-id | The event this stretch of play happened at. Must be in the mod's `events`. |
| `ran` | ● | bool | `false` = scheduled but did not happen. Record it anyway; a mod that did not run is information. |
| `group` | ○ | text | The Group this stretch of play covers, when the mod's players split up to play side by side. A short label the Mod Runner chooses, on one line, of at most 60 characters. See below. |
| `finished` | ● | bool | `true` if the mod, or this report's Group, has nothing left to play after this stretch; `false` if play stopped with more to come. See below. |
| `path` | ○ | list | The way this stretch of play went through the mod's Dry Run, ending where play stopped. See below. |
| `mod_runner` | ● | text | Who ran this stretch of the mod and is reporting on it. |
| `pcs` | ● | id[] | The PCs who took part. Empty list if `ran: false`. The roster stays authoritative — this is presence at this mod, not a roster edit. |
| `canon_changes` | ● | list | The changes to canon this report proposes. See below. Empty list is valid. |

## `finished`

A report is filed every time play stops, so on its own it does not say whether
the mod is over. `finished` does. `false` means this was an interruption: the
mod is in progress and another report will follow. `true` means this is the
last report on the mod.

- **The report that finishes a mod is its last.** A later report on the same
  mod is an error, reported on both: either could be the one that is wrong.
  If more was played after all, the earlier report was not the end, and
  should say `finished: false`. Reports are read in order of event, then id.
  When the mod has split into Groups, this holds for each Group: see
  [`group`](#group).
- **The mod's own `state` is still set by a person.** Filing a report does not
  change it. The validator warns on the mod when its state and its latest
  report disagree (after a split, its latest report in each Group at its
  latest event): the report says the mod is finished and the state does not;
  the state says finished and the report says there is more to play; or the
  report says the mod has been run and the state says it has not begun. A
  shelved mod is left alone, whatever its reports say.
- **A mod that did not run is not finished by saying so.** `ran: false` with
  `finished: true` is an error.

## `path`

The **Path**: the way this stretch of play went through the mod's Dry Run
(the Dry Run convention is in `mod.md`). It runs from the Hook taken, through
each scene and each Contest's result, to the ending reached or the scene where
play stopped. **The last step is where play stopped.** A report without one is
valid; a mod with no Dry Run has nothing to give it.

Each step is one of three things, one per line:

| Step | Written | Names |
|---|---|---|
| A Hook | `- hook: <the Hook>` | The Hook taken, as its label is written under `## Hooks`. |
| A scene or ending | `- <its heading>` | A `###` under `## Scene Breakdown` or `## Possible Outcomes`, matched as a Dry Run link is: a number prefix like `1. ` and case are ignored. |
| A Contest | `- contest: <what is contested>`<br>`  result: <the result>` | A Contest in the scene before it, and the result taken. |

A step that a Hook or a Contest's result leads to is written as its own step
after it, so every Path ends at a scene or an ending.

```yaml
path:
  - hook: Oleen asks the party directly, through anyone who has done her a favour
  - The vigil itself
  - The lower door
```

Play stopped at the lower door, with more to come, so this report says
`finished: false`. **A report that continues an earlier stretch** may start
where the Path of the report before it on the same mod stopped, instead of at
a Hook:

```yaml
path:
  - The lower door
  - The Order comes through
  - contest: fight the Order
    result: win
  - Order driven off
```

The validator checks a Path against the mod's Dry Run, when one can be built
from it:

- **Errors**: a step that names no Hook, scene, ending or Contest the mod has;
  a step that cannot be reached from the one before it, by a scene's exits, a
  Hook's link or a Contest's result; a result the Contest does not have; a
  first step that is neither a Hook nor where the last report's Path stopped;
  a Path that ends at a Hook or a Contest. The report before is the last one
  on the same mod that ran, by event and then id, on the same line of play:
  after a split, in the same Group (see [`group`](#group)). If that report
  has no Path, or one that does not fit, where it stopped is not known, and
  the Path may start at any scene.
- **Warnings**: a Path that ends at an ending under `## Possible Outcomes` on a
  report that says `finished: false`, or at a scene on one that says
  `finished: true`; a Path on a mod with no Dry Run, which cannot be checked.

## `group`

Sometimes a mod splits its players: some hold the nave while others go down to
the lower door, each with their own Mod Runner. Each Mod Runner files a report
on their own **Group**, and labels it in `group`. The label is theirs to
choose; it only has to be the same on every report from the same Group. A
report with no `group` covers the whole mod, as every report did before Groups.

**Groups are parallel at one event.** For one mod at one event, reports with
different labels ran side by side, and reports with the same label, or none,
follow each other in id order. Each Group has its own line of play:

- **Its Path** starts where its own last report stopped. A Group's first
  report starts where the whole mod stopped before the players split, or at a
  Hook.
- **`finished: true`** says the Group has nothing more to play. Nothing may
  follow it in that Group; a later report with the same label at that event
  is an error, on both. Two Groups may each finish. **The mod is finished
  when every Group at its latest event has**, and the validator compares the
  mod's `state` with that.
- **A later report with no `group` brings the Groups back together.** It
  continues from where the Group that had not finished stopped. If several
  had not, its Path's first step says which: it must be where one of them
  stopped. If every Group had finished, the mod was finished, and a later
  report is an error, as above. The next report with a `group` starts a new
  split, from there.
- **The Groups of one event have come back together by the next.** A split
  lasts no longer than its event, so the first report at a later event, with
  a `group` or without one, continues from the Groups that had not finished,
  as a report with no `group` would. A label used again at a later event names
  a new Group there: it does not pick up where the Group of that name stopped,
  and a Group that finished at an earlier event does not stop it.

At the vigil, the party splits. One Group holds the nave and drives the Order
off; it has nothing more to play:

```yaml
id: aa-the-ashen-vigil
event: e08-harvest-mourn
group: nave
finished: true
path:
  - hook: Oleen asks the party directly, through anyone who has done her a favour
  - The vigil itself
  - The Order comes through
  - contest: fight the Order
    result: win
  - Order driven off
```

At the same event, the other goes down to the lower door, and play stops
there:

```yaml
id: aa-the-ashen-vigil-2
event: e08-harvest-mourn
group: lower door
finished: false
path:
  - hook: Anyone watching the Order's movements can see the chapel is the target
  - The lower door
```

The mod is not finished: the lower door Group has more to play. The mod is
scheduled again at a later event, `e09-midwinter-vigil`, where the party plays
on together, in a report with no `group`, from where the lower door Group
stopped:

```yaml
id: aa-the-ashen-vigil-3
event: e09-midwinter-vigil
finished: true
path:
  - The lower door
  - The Order comes through
  - Register taken
```

**Canon changes from parallel Groups** are still decided in one order, by
event, report id and place in the report, so the result is always the same.
But between Groups that played side by side, at the same event, that order is
only a tie-break: when two of them change the same field of the same entity (a `status`,
`location` or `affiliation` change that is not rejected), the validator warns
on both reports, so a Plot Master checks which is right.

## `canon_changes`

Each entry names one entity and one change, of one of the seven kinds in
`canon_change_kind`.

```yaml
canon_changes:
  - entity: varen-ashcroft
    kind: status
    decision: proposed
    from: alive
    to: missing
    summary: "Betrayed the party at the chapel and fled north."
```

| Field | Req | Notes |
|---|---|---|
| `entity` | ● | Any entity id — npc, faction, plot, location, or pc. |
| `kind` | ● | `enum:canon_change_kind`. |
| `decision` | ● | `enum:canon_change_decision`. Whether this change is canon. Written as `proposed`; only the Plot Master changes it. |
| `from` / `to` | ◐ | **Required** for `status`, `location`, `affiliation`. **Forbidden** for the others. |
| `summary` | ● | One line, plain past tense. This is the text POV summaries are built from — write it to be read. |
| `note` | ○ | Text. Why the Plot Master approved or rejected the change, in a line or two. Written only by the Plot Master, with the decision. Plain text: it is shown as typed, never as markup. |

### Each change is decided on its own

A report proposes; it does not make canon. Every change starts as `proposed`,
and the Plot Master approves or rejects each one separately — one report can
hold approved, rejected and undecided changes at once. There is no flag for the report as
a whole.

Only an approved change is canon. A proposed or rejected one is kept in the
file for the record and is never applied to an entity, so the validator does
not expect the entity's file to agree with it. A rejected change is not
deleted: that it was reported and turned down is itself information.

The Plot Master may say why in a `note` beside the decision. A note is most
useful on a rejection, so that a Mod Runner reading back can tell a mistake from
a deliberate ruling, but an approval can carry one too.

```yaml
  - entity: varen-ashcroft
    kind: relationship
    decision: rejected
    note: "Varen was never named at the vigil; see the mod notes."
    summary: "Publicly named an oathbreaker by the clerk he had been avoiding."
```

### Changes to one field in one report

A report may change the same field more than once — a status from `alive` to
`missing` and then to `dead`. The changes are taken in the order the report
lists them, so the last approved one is the field's latest value.

### Two classes of canon change

**Transition canon changes** — `status`, `location`, `affiliation` — assert a field
change with `from` and `to`. Their values are checked against the target
entity's own vocabulary. This makes them *mechanically appliable*: the registry
maintainer applies them once approved, and the validator then verifies that the
entity's current field equals the `to` of the latest approved canon change
touching it (by event `ordinal`, then report id), and that its `as_of` has
advanced to that canon change's event.

That check is what turns the canon change list into a **verifiable changelog of the
registries** rather than a second, drifting account of them. If a canon change
is approved and never applied, the validator says so.

**Prose canon changes** — `relationship`, `knowledge`, `narrative`, `created` — carry
`summary` only. They change no field, so nothing can be checked mechanically,
and they are where most of the texture of a POV summary comes from. Use them
freely; one line each.

## Body

`## What Happened` · `## Divergences From The Mod` · `## Loose Ends`

- **`## Divergences From The Mod`** — compare against the mod's
  `expected_changes`. This is the section a review across plots reads.
- **`## Loose Ends`** — hooks that came up in play and that nobody has written yet.

## Example

```markdown
---
id: aa-the-ashen-vigil
type: after-action
mod: the-ashen-vigil
event: e08-harvest-mourn
ran: true
finished: true
path:
  - hook: Tomas Veil is owed an answer by Varen and knows he will be there
  - The vigil itself
  - The Order comes through
  - contest: fight the Order
    result: lose
  - Register taken
mod_runner: alex
pcs: [pc-tomas-veil, pc-sara-korr]
canon_changes:
  - entity: varen-ashcroft
    kind: status
    decision: approved
    from: alive
    to: missing
    summary: "Betrayed the party at the chapel and fled north."
  - entity: varen-ashcroft
    kind: relationship
    decision: approved
    summary: "Now a declared enemy of Tomas Veil."
  - entity: siege-of-greymoor
    kind: narrative
    decision: approved
    summary: "Escalated; the Ashen Order holds the chapel."
  - entity: pc-tomas-veil
    kind: narrative
    decision: approved
    summary: "Swore a public oath to hunt Varen."
---

## What Happened

Oleen's vigil ran about forty minutes before Varen opened the lower door. The
party held the nave and lost it. Tomas got close enough to be recognised, which
was the point.

## Divergences From The Mod

The mod expected Varen to reveal his allegiance to the Order. He did not —
he let the party assume it. Mira's `expected_changes` said "reveals his
allegiance"; what actually happened is closer to "allowed a conclusion".
Left `varen-ashcroft`'s faction unchanged as a result.

## Loose Ends

- Nobody has asked why the lower door was unsealed.
- Sara Korr took the chapel register and no one has read it yet.
```
