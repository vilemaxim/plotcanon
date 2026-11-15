# `interlude-changes`

`interludes/<event-id>/<id>.md`. A record of **changes to canon made during an
Interlude**: the period between two events, in which canon changes with no mod
run. Backstories settled, off-screen moves, letters, the winter that killed an
old man. The event it names must be an Interlude, an event with
`period_type: interlude`.

Ids are unique repo-wide and equal to the filename stem. Convention:
`ic-<interlude-id>`, then `ic-<interlude-id>-2` and so on for more records in
the same Interlude. Records in the same Interlude are applied in id order, as
reports at one event are.

## Frontmatter

| Field | Req | Type | Notes |
|---|---|---|---|
| `id` | ● | slug | Filename stem. Convention: `ic-<interlude-id>`. |
| `type` | ● | `interlude-changes` | |
| `event` | ● | event-id | The Interlude these changes were made in. Must have `period_type: interlude`; changes at a gathering of play are reported by its mods' [after-action](after-action.md) reports. |
| `recorded_by` | ● | text | Who recorded these changes, usually a Plot Master. A handle, as `mod_runner` is in a report. |
| `canon_changes` | ● | list | The changes to canon, exactly as in an [after-action report](after-action.md#canon_changes). Empty list is valid. |

## `canon_changes`

Each change is written, checked and decided exactly as in an after-action
report: `entity`, `kind`, `decision`, `from`/`to` for the transition kinds, and
a one-line `summary`. A Plot Master recording a change they are making writes
it as `approved`; one recorded for someone else to decide is `proposed`.

An approved change counts in the chain of changes to its entity's field like
any other, at the Interlude's place in the order. The entity's file is then
expected to agree with it, and its `as_of` to have advanced to the Interlude.
A change flags every unfinished mod that features the entity it changes, as a
report's does.

## Body

Free prose about the Interlude, if any. No fixed headings.

## Example

```markdown
---
id: ic-the-long-frost
type: interlude-changes
event: e08b-the-long-frost
recorded_by: mira
canon_changes:
  - entity: varen-ashcroft
    kind: status
    decision: approved
    from: missing
    to: dead
    summary: "Found frozen on the moor road."
---

The thaw turned up more than anyone wanted.
```
