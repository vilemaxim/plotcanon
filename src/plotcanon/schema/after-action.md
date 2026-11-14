# `after-action`

`after-actions/<event-id>/<id>.md`. A mod runner's account of what happened
during **one continuous stretch of playing a mod**, recorded as a list of
proposed **canon changes**.

**One is filed every time play stops**, so a mod can have several: one per
event it ran at, and more than one at the same event if it was interrupted and
picked up again. Each names the one event it covers, and that event must be in
the mod's `events` list.

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
| `mod_runner` | ● | text | Who ran this stretch of the mod and is reporting on it. |
| `pcs` | ● | id[] | The PCs who took part. Empty list if `ran: false`. The roster stays authoritative — this is presence at this mod, not a roster edit. |
| `canon_changes` | ● | list | The changes to canon this report proposes. See below. Empty list is valid. |

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

### Each change is decided on its own

A report proposes; it does not make canon. Every change starts as `proposed`,
and the Plot Master approves or rejects each one separately — one report can
hold approved, rejected and undecided changes at once. There is no flag for the report as
a whole.

Only an approved change is canon. A proposed or rejected one is kept in the
file for the record and is never applied to an entity, so the validator does
not expect the entity's file to agree with it. A rejected change is not
deleted: that it was reported and turned down is itself information.

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
  `expected_changes`. This is the section the master-plot pass reads.
- **`## Loose Ends`** — hooks the game generated that nobody has written yet.

## Example

```markdown
---
id: aa-the-ashen-vigil
type: after-action
mod: the-ashen-vigil
event: e08-harvest-mourn
ran: true
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
