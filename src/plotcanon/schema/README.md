# Document schemas

One doc per document type. Each lists required and optional frontmatter, the
fixed body headings, and a worked example.

| Type | Doc | Lives in |
|---|---|---|
| `campaign` | [campaign.md](campaign.md) | `canon/campaigns/` |
| `event` | [event.md](event.md) | `canon/events/` |
| `npc` | [npc.md](npc.md) | `canon/npcs/` |
| `faction` | [faction.md](faction.md) | `canon/factions/` |
| `location` | [location.md](location.md) | `canon/locations/` |
| `plot` | [plot.md](plot.md) | `canon/plots/` |
| `pc` | [pc.md](pc.md) | `canon/pcs/` |
| `timeline` | [timeline.md](timeline.md) | `canon/timeline/` |
| `mod` | [mod.md](mod.md) | `inbox/`, `mods/<campaign-id>/`, `mods/shelved/` |
| `after-action` | [after-action.md](after-action.md) | `after-actions/<event-id>/` |
| `interlude-changes` | [interlude-changes.md](interlude-changes.md) | `interludes/<event-id>/` |

Allowed values for every enum field are in [vocabularies.yml](vocabularies.yml),
which is the single source of truth. These docs deliberately do not restate them.

**The repo is one world.** Events and mods belong to a campaign; every other
type belongs to the world and is shared by all its campaigns.

## The World's settings: `world.yml`

A World's settings live in one YAML file, `world.yml`, at its root. It is
optional; every setting has a default, used when the file or that entry in it is
absent. It is part of the World's files, so it is exported and imported with
them.

```yaml
dry_run_structure: "encouraged"   # off | encouraged | required
```

| Setting | Values | Default | Meaning |
|---|---|---|---|
| `dry_run_structure` | `enum:dry_run_structure` | `encouraged` | How strictly mods are held to the Dry Run convention. See [mod.md](mod.md#the-dry-run-convention--where-each-part-of-the-story-leads). |

Quote `"off"`: YAML reads a bare `off` as false. The validator takes false to
mean `off` all the same. An unknown setting, or a value not in the vocabulary,
is an error on `world.yml`.

Only what belongs to the World goes here. Who may do what, and anything about
an Organization, lives in the app that hosts the World and never in its files.

---

## Conventions that apply to every document

**`id` is the filename stem, and it never changes.** `canon/npcs/varen-ashcroft.md`
has `id: varen-ashcroft`. Ids are lowercase, hyphen-separated, and unique across
the whole repo — not just within a directory. Renaming an entity means changing
its `aliases`, never its id.

**Names are never identity.** Every human-readable name goes in `aliases`, which
is a list. Every reference from one document to another uses the id. This is what
lets the reconciler recognise the same NPC across mods written months apart,
after the name has been corrected, revealed, or spelled three ways.

**`as_of` stamps state in time.** Any entity with a `status` also carries
`as_of: <event-id>`. Together they mean "this was true as of that event" — not
"this is true now". A mod set at an earlier event that contradicts the current
status is *not* a conflict, and the reconciler relies on `as_of` to tell the
difference. `as_of` advances only when an approved after-action canon change moves it.

**Ordering is `(event.ordinal, slot)` and nothing else.** In-world time is free
text and lives only on event files. Never write an in-world date on an NPC, a
mod, or an after-action — it will drift out of agreement with the event registry.

**After-action reports on one mod are read by event, then id.** That order says
which report follows which, and in what order their canon changes are decided.
When a mod's players split into **Groups** at one event, each Group's report
says which it covers in `group`. Groups are parallel only at that event: each
has its own line of play, and they have come back together by the next report
with no `group`, or the next event. Between parallel Groups, id order is only a
tie-break, and the validator warns where it decides a field. See
[after-action.md](after-action.md#group).

**Body headings are fixed.** Agents and the validator locate content by heading.
Add sections if you need them; do not rename or drop the listed ones. Empty is
fine, missing is not.

**`## GM Notes` is the secret section.** By convention it is stripped from
anything handed to a player or to a Mod Writer outside the plot team. Do not put
secrets anywhere else in the body.

## Field types used below

| Notation | Meaning |
|---|---|
| `id` | A slug referencing another document. The validator checks it resolves. |
| `id[]` | A list of such slugs. Empty list is valid; omitting the key is not, where required. |
| `enum:<name>` | A value from that vocabulary in `vocabularies.yml`. |
| `event-id` | An id from `canon/events/`, or the literal `pre-campaign` where noted. |
| `text` | Free text. Not validated. |
| `date` | `YYYY-MM-DD`. Real-world dates only. |
