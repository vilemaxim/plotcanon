# plotcanon

The shared file format for RPG plot canon. A World — its NPCs, factions, locations, PCs, Plots, Campaigns, Events, Mods and After-Action Reports — is a set of markdown files with YAML frontmatter. This package reads those files into structured data and validates them.

Two projects use it, so that both read and write exactly the same files:

- **larp-llm**, where a git repo per World is the system and Claude Code agents keep it consistent.
- **[RPG Plot Helper](https://github.com/vilemaxim/rpg-plot-helper)**, a web app for plot teams who never open a terminal.

plotcanon owns the schema. A document type, field or vocabulary value is added here first, and both projects follow.

## Install

Pin a tagged version:

```sh
uv add "plotcanon @ git+https://github.com/vilemaxim/plotcanon@v0.1.0"
# or
pip install "plotcanon @ git+https://github.com/vilemaxim/plotcanon@v0.1.0"
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

| Function | What it does |
|---|---|
| `load_world(source, *, head=None)` | Parse and validate a whole World. Returns a `Report`; `report.world` is set when there are no errors. |
| `check_file(world, path, text)` | Validate one file against a World. Returns a `Report`; `report.document` is set when the file has no errors. |
| `read_directory(directory)` | Read a World's files from disk into `{path: text}`. |
| `vocabularies()` | The allowed values for every enum field. |
| `schema_files()` | The schema docs and `vocabularies.yml`, as shipped. |

## Use it from the command line

```sh
plotcanon validate                   # the World in the current directory
plotcanon validate canon/npcs/x.md   # report only on these paths
plotcanon validate --strict          # treat warnings as errors
plotcanon pov varen-ashcroft         # everything canon records about one entity
plotcanon schema --write schema/     # copy the schema docs into a World
```

Add `--root DIR` to work on a World somewhere else. `validate` exits 0 when the World is clean, 1 when it has errors (or warnings, with `--strict`), and 2 when the command could not run.

## The schema

The document types, their fields and the fixed body headings are described in [`src/plotcanon/schema/`](src/plotcanon/schema/), one file per type. The allowed values for every enum field are in [`vocabularies.yml`](src/plotcanon/schema/vocabularies.yml), which is the single source of truth. These files ship inside the package.

[`examples/`](examples/) holds a small sample World that the tests validate.

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
