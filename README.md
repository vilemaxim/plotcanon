# plotcanon

The shared file format for RPG plot canon. A World — its NPCs, factions, locations, PCs, Plots, Campaigns, Events, Mods and After-Action Reports — is a set of markdown files with YAML frontmatter. This package reads those files into structured data and validates them.

Two projects use it, so that both read and write exactly the same files:

- **larp-llm**, where a git repo per World is the system and Claude Code agents keep it consistent.
- **[RPG Plot Helper](https://github.com/vilemaxim/rpg-plot-helper)**, a web app for plot teams who never open a terminal.

plotcanon owns the schema. A document type, field or vocabulary value is added here first, and both projects follow.

## Install

Pin a tagged version:

```sh
uv add "plotcanon @ git+https://github.com/vilemaxim/plotcanon@v0.13.0"
# or
pip install "plotcanon @ git+https://github.com/vilemaxim/plotcanon@v0.13.0"
```

It needs Python 3.12 or later, and PyYAML.

## Use it from Python

```python
import plotcanon

# A World is a directory, or a mapping of {relative path: text}.
report = plotcanon.load_world("path/to/world")

if report.ok:
    world = report.world
    varen = world.get("varen-ashcroft")
    varen.fields["status"]          # "missing"
    world.of_type("mod")            # every Mod
else:
    print(report.text())            # one line per problem
```

Validate one submitted file against a World without changing the World:

```python
report = plotcanon.check_file(world, "inbox/the-ashen-vigil.md", text)
report.document      # the parsed file, or None if it has errors
report.text()        # findings about that file only
```

`report.text()` is written to be pasted back into an LLM. Each line names the file, then the field and what is wrong with it:

```
ERROR  inbox/the-ashen-vigil.md: `features.npcs: no-such-npc` does not resolve to any document
```

Errors mean the file is not valid. Warnings are for a person to judge and do not stop a World from loading.

### Files from strangers

`load_world` and `check_file` are safe to hand files you did not write. Whatever a file holds, they report it as a finding and do not raise. Where the checks rely on a value's shape, a value of the wrong shape, such as a list where one id belongs, is an error naming the field.

Some things are refused as soon as they are seen, without the work they would otherwise cost:

- **A YAML alias** (`*name`). Nested, a few hundred bytes of them stand for millions of values. A World's files have no use for them. An anchor (`&name`) that nothing refers to is harmless and allowed.
- **A file over a million characters**, or **frontmatter over a hundred thousand**. Parsing YAML costs far more per character than reading text, so the block of fields has the tighter limit.
- **Frontmatter nested more than twenty levels deep.**
- **An id over 200 characters, a name over 200, or more than 100 names** for one document.
- **A whole number too large to be meant**, and **text with control characters or broken characters in it**, which could not be shown or stored.

The limits are fixed; real documents come nowhere near them.

What plotcanon does not bound is the World as a whole: how many files you hand it and how much text they hold in total. Every name is looked for in the text of every Mod, so the cost of a check grows with both. Bounding those, and unpacking an upload safely, is for the caller. A path that points outside the World (`../x.md`) raises `ValueError`, since that is a fault in what was handed over, not in a file's contents.

Should a check ever fail in a way none of this foresaw, the caller is still not handed an exception: the report carries one error against `(the World)` saying so.

| Function | What it does |
|---|---|
| `load_world(source, *, head=None, dry_run_structure=None)` | Parse and validate a whole World. Returns a `Report`; `report.world` is set when there are no errors. `dry_run_structure` overrides the World's setting. |
| `check_file(world, path, text, *, dry_run_structure=None)` | Validate one file against a World. Returns a `Report`; `report.document` is set when the file has no errors. |
| `read_directory(directory)` | Read a World's files from disk into `{path: text}`: its documents and its `world.yml`. |
| `flags(world, report)` | The Flags a report raises: one for each unfinished Mod and each canon change that names one of its Features. |
| `flagged_mods(world, report)` | The ids of those Mods, each once. |
| `references(document)` | The values in a document that name other documents, each a `Reference` with its field, the id and its place. A value in any other field (a Mod Writer's handle, a date) is never one. |
| `referrers(world, document)` | The documents in a World that refer to a document (or an id). |
| `name_of(world, document)` | What to call a document on a page: its title, its first alias, or for a report its Mod and Event. |
| `without_gm_notes(text)` | A document's whole text without its `## GM Notes`, the secret section, for anyone outside the plot team: the heading and everything under it, up to the next heading of the same or a higher level. The heading is matched on its exact text, and one in a code block is not a heading. Everything else, frontmatter and line endings included, is left as it was. |
| `vocabulary_fields(document)` | Which of a document's fields hold a value from a vocabulary, and which vocabulary. |
| `story(mod)` | A Mod's story by the Dry Run convention, as a `Story`: its start, passages, exits, Contests and endings, and why a Dry Run cannot be built from it, if it cannot. Takes a Mod's `Document` or its text. |
| `path_steps(story, choices, *, continues_from=None, start=None)` | The steps of a Path, as a report's `path` holds them, from the choices taken in a walk through a Dry Run. See [Paths](#paths). |
| `check_path(story, steps, *, continues_from=None)` | A report's `path` read against its Mod's story, as a `Path`: where play stopped, whether that finishes the Mod, and what does not fit. |
| `last_stop(world, mod, *, before=None)` | Where play stopped on a Mod before a report, or after its last one, as a `LastStop`, by the rule `load_world` checks a Path by. |
| `to_twee(text)` | A Mod's file as a Twee 3 story, to open in Twine. |
| `from_twine(source)` | A Twee file or a Twine 2 `.html` file (archive or published) back into a Mod's markdown, as `FromTwine`: the `markdown`, `warnings` about what does nothing in a Dry Run, and `problems` if the file could not be read. Takes text or bytes. |
| `world_settings(source)` | A World's settings from its `world.yml`, as `WorldSettings`. `world.settings` gives the same for a loaded World. |
| `sample_world()` | A ready-made World, as `{path: text}`. |
| `sample_script()` | Reports to submit to the sample World, each with the Mods it should flag. |
| `vocabularies()` | The allowed values for every enum field. |
| `interview_instructions(kind, surface, *, world=None, draft=None, sent_back_reason="", flags=(), mod=None, path=None, continues_from=None, event=None)` | The instructions for an Interview, as one text to give an LLM as its system prompt. `kind` is `"new-mod"`, `"revise-mod"` or `"report"`; `surface` is `"cli"` or `"web"`. See [Interviews](#interviews). |
| `interview_fix_request(errors)` | The message an app sends its LLM, in a `"web"` Interview, when the Mod file the LLM gave has errors: from the app, not the person, who has not seen the file yet, asking for the whole file again in one code block. `errors` is text the caller has already cut down to what the person may read. |
| `interview_revise_opener()` | The first message an app sends its LLM, on the person's behalf, to open a `"revise-mod"` Interview, so the LLM speaks first, beginning with the send-back reason and each Flag. |
| `interview_report_opener(path=None)` | The same for a `"report"` Interview: it begins with the Path, or with no Path asks the Mod Runner to say in words what happened and where play stopped. |
| `applied(text, field, change, *, previous=None, following=None, event_ordinal)` | An entity's file with an approved Canon Change applied. See [Applying a Canon Change](#applying-a-canon-change). |
| `unapplied(text, field, change, *, previous=None, following=None, remaining_events=(), event_ordinal)` | An entity's file with an approved Canon Change taken back out. |
| `avoided_words(text)` | Uses in a text of words the shared glossary says to avoid, each with the term to use instead. For checking docs and prompts. |
| `schema_files()` | The schema docs and `vocabularies.yml`, as shipped. |

## Applying a Canon Change

An approved Canon Change that moves a field (`status`, `location` or `factions`) is applied to the entity's file, and `load_world` warns when one is approved but not applied. `applied` and `unapplied` make that edit by the same rules, so an app holds none of them:

```python
change = plotcanon.Change(before="alive", after="dead", event="e03-storm-moon")
text = plotcanon.applied(npc_text, "status", change,
                         previous=earlier, following=later,
                         event_ordinal=ordinals.get)
```

- **`change`, `previous`, `following`** are `Change(before, after, event, replaced=None)`. `previous` and `following` are the approved changes just before and after this one to the same field of the same entity, in the order they happened, or None. Finding them is the caller's.
- **`event_ordinal(event_id)`** gives an Event's ordinal, or None if it has none.
- **A `factions` change** takes `before` out of the list and puts `after` in. Factions changes are decided in the order they happened.
- **Any other field** goes from `before` to `after`, which must follow on from `previous` and lead into `following`. When `following` is given it already decides the field, and the file comes back as it was.
- **`as_of`** moves to the change's Event, unless it stands at a later one.

`unapplied` puts the field back where `previous` left it, or to `before`. A factions list goes back to what `replaced` recorded (`{field: value, "as_of": id}`, kept by the caller when it applied the change), or, with nothing recorded, loses `after` and gets `before` back. If `as_of` stands at the change's Event, it goes back to the latest of `replaced["as_of"]` and `remaining_events`, the Events of the entity's other approved changes that move a field; with neither, it stays.

When a change does not fit, both raise `ChangeRefused`. Its `reason` is one of:

| `reason` | Meaning |
|---|---|
| `"factions-out-of-order"` | A later factions change (`following`) is already approved. |
| `"not-a-member"` | The entity is not in the faction `before` names. |
| `"contradicts-previous"` | `before` is not where `previous` left the field. |
| `"contradicts-following"` | `after` is not where `following` starts. |
| `"contradicts-current"` | `before` is not the field's current value. |
| `"followed-on"` | `unapplied` only: a later approved change (`following`) follows on from this one. |

`neighbor` is `"previous"` or `"following"` when the reason involves that change, which is `other`; `current` is the field's value now. The exception's text is only the reason, so the caller writes the message. A file whose frontmatter cannot be read or changed raises `editing.CannotEdit`.

## Editing a file

`plotcanon.editing` changes one value in a file's text and leaves the rest as it was: comments, quoting, the order of fields, one-line and down-the-page lists, and CRLF line endings. Each function takes the file's whole text and returns the new text. A new value is written in as it stands, so it must already be YAML. Nothing is checked: check the World again with `load_world` before keeping the files.

```python
from plotcanon import editing

text = editing.replace(text, ["canon_changes", 2, "decision"], "approved")
text = editing.set_key(text, ["canon_changes", 2], "note", editing.quoted(note), after="decision")
```

| Function | What it does |
|---|---|
| `replace(text, path, new)` | The value at `path`, a list of field names and list positions, replaced. |
| `find(text, path)` | The YAML node at `path`, and where the frontmatter starts in the text. |
| `set_field(text, field, new)` | A top-level field set, or added at the end of the frontmatter. |
| `set_key(text, path, key, new, after)` | A key in the mapping at `path` set, or added just after the key `after`, on one line or down the page as the mapping is written. |
| `remove_key(text, path, key)` | A key taken out of the mapping at `path`; the file as it was if the key is not there. |
| `add_to_list(text, field, item)` | An item added to the end of a top-level list, as the list is written. A missing or empty field becomes a list of the one item. |
| `quoted(words)` | Text written as one double-quoted YAML scalar on one line. |
| `flow_list(items)` | Ids written as a YAML list on one line. |

Each raises `editing.CannotEdit` when the path is not there or the value cannot be changed; `str()` says which.

## Dry Runs

A Dry Run is a playable, branching version of a Mod. Its Hooks, scenes, Contests and Possible Outcomes say where each leads, by the convention in [`schema/mod.md`](src/plotcanon/schema/mod.md), and `story` reads that into a graph, so nothing else has to parse the markdown:

```python
told = plotcanon.story(world.get("the-bell-beneath"))

if told.playable:
    here = told.start                     # the Premise; its exits are the Hooks
    here.prose                            # its text, without the links
    for choice in here.choices:           # exits, then each Contest's results
        choice.label, choice.passage      # "The sister asks them...", "The descent"
    here = told.passage(choice.passage)   # kind is "start", "scene" or "ending"
else:
    print("\n".join(told.problems))       # why not, to paste into an LLM
```

`told.sections` is the whole body section by section, exactly as written, for converting it to another format.

How strictly a World's Mods are held to the convention is its **Dry Run structure** setting, in `world.yml` at the World's root: `off`, `encouraged` (the default: the checks are warnings) or `required` (the checks are errors, and so is a Mod with no structure). `load_world`, `check_file` and `plotcanon validate` all follow it.

```python
world.settings.dry_run_structure                  # "encouraged"
plotcanon.WorldSettings(dry_run_structure="required").text()   # the file to write
```

## Paths

An After-Action Report may give the **Path** its Stretch took through the Mod's Dry Run: the Hook taken, each scene, each Contest's result, and the ending or the scene where play stopped. It is the report's `path`, described in [`schema/after-action.md`](src/plotcanon/schema/after-action.md):

```yaml
path:
  - hook: The sister asks them to close what was opened
  - The descent
  - Who rings it
  - contest: stop her before the last stroke
    result: win
  - The bell is silenced
```

A Path starts at a Hook, or where the last report's Path on the same Mod stopped. `last_stop` says where that was, and `path_steps` and `check_path` follow the same rules `load_world` checks a report by, so an app's walk and the checks agree:

```python
told = plotcanon.story(mod)
stop = plotcanon.last_stop(world, mod.id)                 # before a report not yet filed
steps = plotcanon.path_steps(told, choices, continues_from=stop,
                             start=stop.passage)          # or start=None, at a Hook
walked = plotcanon.check_path(told, steps, continues_from=stop)
walked.end         # the Passage where play stopped
walked.finished    # True when that is an ending: it proposes `finished: true`
walked.problems    # what does not fit, one sentence each
```

- **`LastStop`** is one of three: `LastStop()`, no earlier report, so a Path starts at a Hook; `LastStop("The bell")`, where the last report's Path stopped; `LastStop(known=False)`, an earlier report with no Path that fits, so a Path may start at any scene. Where `continues_from` is taken, a scene's name or None stands for the first two.
- **`last_stop(world, mod, *, before=None)`** looks at the last earlier report on the Mod that ran, by event and then id. `before` is a report's id or `Document`; with None, it is after the Mod's last report.
- **`choices`** are `Exit`s, each from the `choices` of the passage the walk has reached. From the Premise the first is a Hook; with `start`, the walk starts at that scene, which `continues_from` must allow. A Contest's result is written as the Contest and the result, and every step a Hook or a result leads to is written after it, so the last step is where play stopped. A choice that is not a way on, or a `start` the walk may not take, raises `ValueError`.

`load_world` and `check_file` check a report's `path` against its Mod when a Dry Run can be built from the Mod. A step that names nothing the Mod has, cannot be reached from the step before, or takes a result its Contest does not have is an error. A Path that ends at an ending on a report that says `finished: false`, or at a scene on one that says `finished: true`, is a warning, and so is a `path` on a Mod with no Dry Run. A report without `path` is not checked.

## Twine

A Mod can be edited in [Twine](https://twinery.org) and brought back. Markdown stays the Mod's source; Twine is only the format it travels in.

```python
twee = plotcanon.to_twee(text)              # the Mod's whole file, frontmatter included

result = plotcanon.from_twine(upload)       # .twee or Twine 2 .html, as text or bytes
if result.ok:
    report = plotcanon.check_file(world, path, result.markdown)
    result.warnings                         # show beside report.text()
else:
    result.problems                         # why the file is not a Twine story
```

Each part of the Mod is a passage, told apart by its tag:

| Tag | Passage |
|---|---|
| `frontmatter` | The YAML, exactly as written. A story with none gives markdown with no frontmatter, which fails validation like any such file. |
| `premise` | `## Premise`, with `## Hooks` when it follows. Twine starts here. |
| `scene` | A `###` under `## Scene Breakdown`. A passage with no tag is a scene too, so one added in Twine needs nothing. |
| `contest` | A Contest. The scene links to it, and its links are its results. |
| `outcome` | A `###` under `## Possible Outcomes`. |
| `mod-section` | Any other section, such as NPC Casting or GM Notes, unlinked. |

In the story passages a link `label → [[Target]]` is written `[[label->Target]]`, as Twine writes one, and comes back the same way. Going to Twee and back gives the same file. Two things are not kept: blank lines around headings come back as one, and line endings as `\n`. The sections come back in the order the passages are in the file, with scenes and outcomes under their headings; where a passage sits on Twine's map makes no difference.

Twine variables, macros, HTML and styling are kept as text, with a warning that they do nothing in a Dry Run. So is a link with no label (`[[Target]]`), which a Dry Run does not follow. A tag a Mod has no place for, and the story's JavaScript and stylesheet, are not kept, and a warning says so. Warnings and problems start `Twine: `.

`from_twine` is safe to hand an upload. It reports what is wrong and does not raise. It refuses a file over 5,000,000 characters, a story of more than 1,000 passages, a file holding more than one story, and one that would come to more markdown than a Mod file may hold.

## Interviews

An Interview is a conversation in which an LLM helps a Mod Writer write a Mod, or revise one the Plot Master sent back, or helps a Mod Runner write an After-Action Report. plotcanon owns what the LLM is told: for a Mod, the frontmatter, the nine body headings, the Dry Run convention with the checks `story` makes, the phases of the work, the agency checklist and what gets a Mod sent back; for a report, its frontmatter, `canon_changes` in the schema's terms and its body headings.

```python
text = plotcanon.interview_instructions("new-mod", "web", world=readable)

text = plotcanon.interview_instructions(
    "revise-mod", "web", world=readable,
    draft=draft_text,                                   # must have an `id`, which is kept
    sent_back_reason="It needs a second way in.",       # may be ""
    flags=[("harbour-clerk", "The clerk was arrested at the last Event.")],
)

text = plotcanon.interview_instructions(
    "report", "web", world=readable,
    mod=mod_text,                                       # the Mod's file, which must have an `id`
    path=steps,                                         # the Path walked, or None
    continues_from=stop,                                # from last_stop, or None
    event="e04-second-lantern",                         # or None, for the LLM to ask
)
```

- **`surface`**: `"cli"` is for pasting into an LLM by hand or using with Claude Code. `"web"` is for an app's own LLM, which is told to give the finished file whole, in one code block, so the app can check it.
- **`world`**: what the person may read in the World, in any form `load_world` takes. The caller decides what that is. The text holds those documents and their slugs, and nothing else from any World. With a World, the LLM uses its slugs and lists only what is truly new under `## Proposed New Entities`. With none, every Feature gets a made-up slug and is listed there.
- **`"revise-mod"`** starts the conversation with the send-back reason and each Flag, and keeps the draft's `id`.
- **`"report"`** gives the LLM the Mod, what its Mod Writer expected to change (`expected_changes`), where the last Stretch stopped, and the Path, which it copies into the report as `path`. The Path proposes `finished`, and the LLM asks the Mod Runner to confirm it. It asks `pcs` and what went off-script, and `ran` only when there is no Path, since a Path walked means the Mod ran. It writes `canon_changes` in the schema's terms. With no Path, it starts by asking the Mod Runner to say in words what happened and where play stopped. With `event`, the report's Event is filled in; with a `world`, so is its `id`, the next free one by the convention (`aa-<mod>`, `aa-<mod>-2`, …) among the reports in it.

Two more texts go with a `"web"` Interview, so an app holds no prompt text of its own:

```python
first = plotcanon.interview_revise_opener()          # sent on the person's behalf, so the LLM speaks first
first = plotcanon.interview_report_opener(steps)     # the same, for a report; None when there is no Path
fix = plotcanon.interview_fix_request(errors_text)   # when the file the LLM gave has errors
```

`interview_fix_request` tells the LLM the message is from the app, that the person has not seen the file yet, and to fix the errors and give the whole file again in one code block. Empty errors raise `ValueError`.

An unknown `kind` or `surface`, a `"revise-mod"` with no draft or a draft with no `id`, a `"report"` with no Mod, a Mod with no `id` or a Path that does not fit the Mod's Dry Run, and a kind given a parameter that only another kind takes (a draft, send-back reason or Flags; a Mod, Path, `continues_from` or `event`) raise `ValueError`. A draft, Mod or `event` that is not text, and a `continues_from` that is not a `LastStop`, a scene's name or None, raise `TypeError`. The text keeps to the shared glossary (`avoided_words` finds nothing in it), though what a World or a draft holds is passed through as written. So do the fix request and the opener, though the errors are passed through as written.

`plotcanon instructions --write FILE` writes the `"cli"` instructions for a new Mod, with no World, for larp-llm to copy in.

## Use it from the command line

```sh
plotcanon validate                   # the World in the current directory
plotcanon validate canon/npcs/x.md   # report only on these paths
plotcanon validate --strict          # treat warnings as errors
plotcanon pov varen-ashcroft         # everything canon records about one entity
plotcanon schema --write schema/     # copy the schema docs into a World
plotcanon sample --write demo/       # copy the sample World to disk
plotcanon words README.md docs/      # check wording against the shared glossary
plotcanon instructions --write prompts/mod-writer.md   # the Interview instructions for a new Mod
```

Add `--root DIR` to work on a World somewhere else. `validate` exits 0 when the World is clean, 1 when it has errors (or warnings, with `--strict`), and 2 when the command could not run.

## The schema

The document types, their fields and the fixed body headings are described in [`src/plotcanon/schema/`](src/plotcanon/schema/), one file per type. The allowed values for every enum field are in [`vocabularies.yml`](src/plotcanon/schema/vocabularies.yml), which is the single source of truth. These files ship inside the package.

## Flags

A report proposes canon changes. Each change puts in question every unfinished Mod that features the entity it changes, in any Campaign of the World. Unfinished means the Mod still has play ahead of it: a draft, an approved Mod, or one in progress. A finished or shelved Mod is never flagged.

```python
report = plotcanon.check_file(world, path, text)
plotcanon.flagged_mods(world, report.document)   # ["a-warrant-for-dunmore", ...]

for flag in plotcanon.flags(world, report.document):
    flag.mod, flag.entity, flag.change           # which Mod, which Feature, which change
```

Three points about the rule:

- The report's own Mod is flagged too when it has more to play, because what happened so far may change the rest of it. A report that says `finished: true` does not flag the Mod it just finished.
- A proposed or approved change raises Flags; a rejected one raises none, since it did not happen.
- Only the entity a change names counts. When an NPC moves, the place they moved to is not treated as changed.

## The sample World

The package ships a World to test against and to give a new user: the Brackwater coast, with two Campaigns, four Events, twelve NPCs, three factions, three Plots and eleven Mods in every state. Some play has already been reported and approved. One Mod, `the-bell-beneath`, is written for a Dry Run.

```python
world = plotcanon.load_world(plotcanon.sample_world()).world

for scripted in plotcanon.sample_script():
    report = plotcanon.check_file(world, scripted.path, scripted.text)
    assert plotcanon.flagged_mods(world, report.document) == sorted(scripted.flags)
```

`sample_script()` is five After-Action Reports to submit in order. Between them they cover the cases worth testing:

| Report | What it shows |
|---|---|
| `aa-the-tax-collectors-ledger-2` | A Mod interrupted for the second time, and a Flag that crosses into the other Campaign. |
| `aa-blood-on-the-salt-stair` | Finishes its Mod. Says an NPC died. Also flags a draft still in the inbox. |
| `aa-storm-moon-vigil` | Run at the same hour, and says the same NPC left alive. The two contradict each other. An interruption, so it flags its own Mod. |
| `aa-storm-moon-vigil-2` | The second report on that Mod at the same Event, and the one that finishes it. It flags nothing. |
| `aa-what-the-keeper-saw` | From the other Campaign. Finishes its Mod and flags nothing. |

To get the files on disk, for a larp-llm repo or to read them, run `plotcanon sample --write demo/ --script demo-script/`.

The files are in [`src/plotcanon/sample/`](src/plotcanon/sample/): the World under `world/`, the reports under `script/`, and what each report should do in [`script.yml`](src/plotcanon/sample/script.yml). Every scripted change is `proposed`, and none of the reports is in the World until you submit it.

[`examples/`](examples/) holds a much smaller World of seven files, which the rule tests change a little at a time.

## Develop

```sh
uv sync
uv run python -m unittest discover tests
```

Tests call only the package's public functions and the `plotcanon` command.

## License

Copyright (C) 2026 Jeffrey Brite

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU Affero General Public License](./LICENSE) for more details.
