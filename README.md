# plotcanon

The shared file format for RPG plot canon. A World — its NPCs, factions, locations, PCs, Plots, Campaigns, Events, Mods and After-Action Reports — is a set of markdown files with YAML frontmatter. This package reads those files into structured data and validates them.

Two projects use it, so that both read and write exactly the same files:

- **larp-llm**, where a git repo per World is the system and Claude Code agents keep it consistent.
- **[RPG Plot Helper](https://github.com/vilemaxim/rpg-plot-helper)**, a web app for plot teams who never open a terminal.

plotcanon owns the schema. A document type, field or vocabulary value is added here first, and both projects follow.

## Install

Pin a tagged version:

```sh
uv add "plotcanon @ git+https://github.com/vilemaxim/plotcanon@v0.7.0"
# or
pip install "plotcanon @ git+https://github.com/vilemaxim/plotcanon@v0.7.0"
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
| `vocabulary_fields(document)` | Which of a document's fields hold a value from a vocabulary, and which vocabulary. |
| `story(mod)` | A Mod's story by the Dry Run convention, as a `Story`: its start, passages, exits, Contests and endings, and why a Dry Run cannot be built from it, if it cannot. Takes a Mod's `Document` or its text. |
| `world_settings(source)` | A World's settings from its `world.yml`, as `WorldSettings`. `world.settings` gives the same for a loaded World. |
| `sample_world()` | A ready-made World, as `{path: text}`. |
| `sample_script()` | Reports to submit to the sample World, each with the Mods it should flag. |
| `vocabularies()` | The allowed values for every enum field. |
| `avoided_words(text)` | Uses in a text of words the shared glossary says to avoid, each with the term to use instead. For checking docs and prompts. |
| `schema_files()` | The schema docs and `vocabularies.yml`, as shipped. |

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

## Use it from the command line

```sh
plotcanon validate                   # the World in the current directory
plotcanon validate canon/npcs/x.md   # report only on these paths
plotcanon validate --strict          # treat warnings as errors
plotcanon pov varen-ashcroft         # everything canon records about one entity
plotcanon schema --write schema/     # copy the schema docs into a World
plotcanon sample --write demo/       # copy the sample World to disk
plotcanon words README.md docs/      # check wording against the shared glossary
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
