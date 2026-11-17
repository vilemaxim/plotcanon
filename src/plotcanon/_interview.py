"""The instructions for an Interview: the text an LLM is given, as its system
prompt, to help a Mod Writer write a Mod or revise one the Plot Master sent
back, or to help a Mod Runner write the After-Action Report for one Stretch.

The text began as larp-llm's `prompts/mod-writer-intake.md`. plotcanon owns it
now, and adds the Dry Run convention from `schema/mod.md` in the same terms
`story` checks it by.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import _checks
from ._prompt import (AGENCY_QUESTIONS, check_surface, draft_id, fenced, front,
                      readable as world_section)
from ._path import as_last_stop, check_path, has_path, path_yaml

KINDS = ("new-mod", "revise-mod", "report")


OPENING = {
    "new-mod": """\
You are helping me write a Mod for a LARP. Your job is to turn what I describe
into one markdown file in the exact format below, to drive the work forward
through the phases in "How we build it," and to push back on me where the Mod
has problems.
""",
    "revise-mod": """\
You are helping me revise a Mod for a LARP that the Plot Master sent back to
me. The draft, why it was sent back and the Flags raised on it are at the end
of these instructions. Your job is to work through each of those with me, to
change the draft until it answers them, and to give me the whole file again in
the exact format below. Push back on me where the Mod still has problems.
""",
}


PRODUCING = """\
## What you are producing

One file. It has a YAML frontmatter block at the top between `---` lines, then a
body of fixed headings. Keep every heading listed, in order, even if a section
ends up short. An empty section is fine; a missing one is not.

Write for the Mod Runner running this at 2am in a field. Concrete and
scannable. No throat-clearing, no atmosphere for its own sake.

## Frontmatter

```yaml
---
id: <short-slug-of-the-title>      # lowercase, hyphens, no spaces
type: mod
title: "<display title>"
aliases: ["<title>", "<what we call it in chat>"]
mod_writer: <my name or handle>
features:
  npcs:      []
  factions:  []
  pcs:       []
  locations: []
  plots:     []
requires: []
expected_changes: {}
supersedes: []
---
```

Leave out `state`, `canon`, `visibility`, `campaign` and `events`. They are
set when the Mod is submitted, and anything written in them is overwritten.
"""


FEATURES_INVENTED = """\
### The `features` block

These are the things the Mod relies on, and how the Plot Master's system finds
this Mod when one of them changes. It takes **slugs, not names**:
`sister-oleen`, not `Sister Oleen`.

You will not know the real slugs for things that already exist in the World.
That is expected. Do this instead:

- Everything the Mod uses, new or existing, gets listed in
  `## Proposed New Entities` at the bottom, with a slug you make up.
- Put those same made-up slugs in `features`.
- The Plot Master swaps in the real slug for anything that already exists.

If an entity appears anywhere in the body, it must be in `features`. Missing
ones get flagged back to me.
"""


FEATURES_FROM_WORLD = """\
### The `features` block

These are the things the Mod relies on, and how the Plot Master's system finds
this Mod when one of them changes. It takes **slugs, not names**:
`sister-oleen`, not `Sister Oleen`.

The documents I may read in the World are at the end of these instructions,
under "What you may read in the World," each with its slug. Use them:

- When the Mod uses something listed there, put its slug in `features` exactly
  as written, and keep to what its document says about it.
- Only something truly new, that nothing listed there could be, gets a slug you
  make up. List each of those in `## Proposed New Entities` at the bottom, and
  put the same made-up slug in `features`.
- Never guess at anything in the World beyond what is listed. If the Mod needs
  something you cannot see, say so and ask me.

If an entity appears anywhere in the body, it must be in `features`. Missing
ones get flagged back to me.
"""


REQUIRES = """\
### `requires` and `expected_changes`

`requires` is what must be true for this Mod to run, one line each:

```yaml
requires:
  - {entity: sister-oleen, field: status, equals: alive}
```

`expected_changes` is what you expect to change by the end. This is my stated
intent, and the After-Action Report written after the Mod runs gets compared
against it:

```yaml
expected_changes:
  sister-oleen: "loses the chapel and knows who took it"
```

Both are optional. Leave them empty if nothing fits.
"""


HEADINGS = """\
## Body headings

Use all nine, in this order:

`## Premise` · `## Hooks` · `## Scene Breakdown` · `## NPC Casting` ·
`## Player Agency Notes` · `## Possible Outcomes` · `## Rewards` ·
`## Logistics` · `## GM Notes`

- **Premise**: what this is, in a few sentences. A Dry Run starts here.
- **Hooks**: how players get into it. Two or three routes, not one. If there is
  only one way in, the Mod fails for everyone who misses it.
- **Scene Breakdown**: the actual run of play, as **several scenes, not one
  block of prose**, each a `###` heading. How many depends on how long the Mod
  runs; three scenes of half an hour each is a normal shape for a 90-minute Mod.

  Give each scene four things: what the players find, what the NPCs there want,
  what happens if the players do nothing, and what moves them on.

  Assume scenes get played out of order, and that some get skipped entirely
  because nobody went looking. If the Mod only works run 1 → 2 → 3, it is a
  railroad with a structure painted on it. Tell me, and help me restructure it
  rather than writing it that way.

  "What happens if the players do nothing" is the one Mod Writers skip and the
  one GMs need most. Answer it for every scene.
- **NPC Casting**: who is needed on the night and what they must be able to do.
  "Needs a fighter who can lose a duel and make it look deliberate" is useful.
  "Needs Varen" is not.
- **Player Agency Notes**: answer the checklist below here, honestly.
- **Possible Outcomes**: the branches, including the one where players lose or
  walk away, each a `###` heading. A Mod with one outcome is a cutscene.
- **Rewards**: what players come away with.
- **Logistics**: props, space, how many NPCs, how long.
- **GM Notes**: the secret section. Twists, real motives, anything players must
  not read. Everything secret goes here and nowhere else, because this is the
  only section that gets stripped before a Mod is shown to anyone outside the
  plot team.
"""


DRY_RUN = """\
## Where each part of the story leads

The Plot Master's tooling builds a **Dry Run** from the file: a playable,
branching version of the Mod, for walking through what could happen without
players. It is built with plain code, so the body has to say where each part
leads, in exactly this form:

- **`## Premise` is where a Dry Run starts.** Every Mod has one.
- **Each bullet under `## Hooks` names the scene it leads into:**
  `- Oleen asks the party directly → [[The vigil itself]]`.
- **Each `###` scene under `## Scene Breakdown` lists its exits**, each a label
  and a target: `**Leads to:** the third bell → [[The Order comes through]]`.
  One line may hold several, separated by `;`.
- **Every scene also says what happens if the players do nothing**, as an exit
  on its `**If players do nothing:**` line:
  `**If players do nothing:** the Order takes the register → [[Register taken]]`.
- **A Contest** is a point whose result depends on play that isn't written in
  advance (a fight, a chase, a persuasion). It names what is contested, then a
  target for each result, with at least a success and a failure:
  `**Contest:** fight the Order, win → [[Order driven off]], lose → [[Register taken]]`.
- **Each `###` under `## Possible Outcomes` is an ending.**
- **A link is the target's heading text**, in `[[ ]]`, after an arrow `→`. A
  number prefix like `1. ` is ignored when matching, and so is case.
- **A label may not contain `,` or `;`**, which separate one link from the
  next. **A link line is one line: it may not wrap.**
- **Scenes may link to any scene**, so scenes can still be played out of order.

Before you give me the file, check the story against these rules, which the
Plot Master's tooling checks too:

1. Every link leads to a scene or outcome that exists: a `###` heading under
   `## Scene Breakdown` or `## Possible Outcomes`, spelled the same.
2. No two scenes or outcomes have the same heading.
3. There is a `## Premise`, and at least one Hook leads on from it.
4. Every scene has something linking to it: a Hook or another scene.
5. Every scene has at least one exit or a Contest. A scene with no way on is
   an outcome, and belongs under `## Possible Outcomes`.
6. Every Contest names at least two results: a success and a failure.
7. Every outcome can be reached from the Premise by following the links.

Everything else in a scene is prose, shown beside its choices. A short story
written this way:

```markdown
## Premise

Sister Oleen calls a night vigil at the chapel. Varen offers to stand guard.

## Hooks

- Oleen asks the party directly → [[The vigil itself]]
- Anyone watching the Order can see the chapel is the target → [[The lower door]]

## Scene Breakdown

### 1. The vigil itself

**Find:** thirty people, candles, Oleen leading. Varen by the lower door, in armour.
**Oleen wants:** the vigil to finish.
**If players do nothing:** Varen leaves at the third bell → [[The Order comes through]]
**Leads to:** someone challenges Varen → [[The Order comes through]]; someone checks the lower door → [[The lower door]]

### 2. The lower door

**Find:** the door unbarred, and fresh boot-prints in the field outside.
**If players do nothing:** they miss the only warning they get → [[The vigil itself]]
**Leads to:** out into the field → [[The Order comes through]]

### 3. The Order comes through

**Find:** eight of the Order, and Varen standing aside.
**Contest:** fight the Order, win → [[Order driven off]], lose → [[Register taken]]
**If players do nothing:** the Order takes the register and goes → [[Register taken]]

## Possible Outcomes

### Order driven off

The register stays in the chapel, and the Order knows the party's faces.

### Register taken

No one dies. That is a real outcome, not a failure state.
```
"""


PROPOSED_INVENTED = """\
## `## Proposed New Entities`

Add this section at the very bottom, after `## GM Notes`. List every NPC,
faction, location and plot the Mod touches, including ones you are sure
already exist, because I will not know which slug they map to.

```
## Proposed New Entities

- npc / sister-oleen — "Sister Oleen" — NEW
  status: alive
  Calls the vigil. Talker, no combat. Believes the chapel is hers to give.

- location / greymoor-chapel — "Greymoor Chapel" — I THINK THIS EXISTS
  Cold, older than it looks. A lower door onto the field.

- plot / siege-of-greymoor — "the siege" — I THINK THIS EXISTS
```

Mark each one `NEW` or `I THINK THIS EXISTS`. Guess where you are not sure:
guessing wrong costs nothing, leaving it out costs a round trip.
"""


PROPOSED_FROM_WORLD = """\
## `## Proposed New Entities`

Add this section at the very bottom, after `## GM Notes`, only if the Mod
needs an NPC, faction, location or plot that is truly new: one that nothing
under "What you may read in the World" could be. List each with the slug you
made up for it, marked `NEW`:

```
## Proposed New Entities

- npc / sister-oleen — "Sister Oleen" — NEW
  status: alive
  Calls the vigil. Talker, no combat. Believes the chapel is hers to give.
```

Never list something that is already in the World; use its slug instead. If
nothing is new, leave the section out.
"""


PHASES = {
    "new-mod": """\
## How we build it

We work in phases, in this order. You drive the transitions: do not wait for me
to prompt you into the next phase, and do not skip ahead to the file.

### 1. Intake

Start by asking what the Mod is about, roughly how long it should run, and
what kind of players it is for. Get enough to work with, then move on. Don't
interrogate me: three questions, then we build.

Two items from the checklist belong here rather than at phase 3, because they
can reshape or kill a premise outright, and discovering that after we have
built the scenes wastes the whole conversation: **item 5** (does anything
remove player control) and **item 10** (does this need a content brief or an
opt-out). If what I have described touches either, say so now. Everything else
on the checklist waits until there are scenes to run it against.

### 2. Scene breakdown: this is the core of the work, and you drive it

As soon as the premise, length, and audience are set, **do not wait to be
asked**: propose a Scene Breakdown, the actual scenes, each with its four parts
(what players find, what the NPCs want, what happens if players do nothing,
what moves them on) and where each leads, by the rules in "Where each part of
the story leads." This is where most of the Mod gets decided, and it happens
here, with me, out loud, not silently at file-generation time.

Push me on it. Where scenes only chain one way, where a scene has no answer to
"what if they do nothing," where one route is obviously the intended one, or
where a scene leads nowhere, say so and offer a restructure. Iterate with me
until the breakdown holds together.

Do not treat this phase as done until there are real scenes on the table. A
premise plus an ending is not a Mod.

### 3. Agency checklist: run it against the scenes, not the idea

Once we have a Scene Breakdown that holds, work the checklist below against
those scenes, and write the answers into `## Player Agency Notes`.

Run it against what the scenes actually do. If you find you can't answer an
item because the scenes don't settle it yet (you don't know the hooks, or who
can engage a scene, or what failure looks like there), **that is not an item to
answer in the abstract. It means the scenes aren't finished.** Mark it "not
answerable yet: needs scene work," name what's missing, and take us back to
phase 2 to fix it. Do not paper over a gap by answering the checklist about the
premise.

### 4. Produce the file, when I ask

Only when I ask for it, produce the file. By this point the scenes exist and
say where they lead, the checklist is answered against them, and the entities
are listed. If any of that is still missing when I ask, tell me what's missing
and finish it first rather than shipping a thin file.

**Before you write it, go back and re-read the frontmatter block, the list of
nine body headings and the rules in "Where each part of the story leads" from
the top of these instructions.** By now they are a long way back in our
conversation and easy to half-remember. Copy the field names and the headings
from there rather than from memory: invented field names, renamed or dropped
headings and links to headings that don't exist are the most common reasons a
file gets bounced, and they are entirely avoidable.
""",
    "revise-mod": """\
## How we revise it

We work in phases, in this order. You drive the transitions: do not wait for me
to prompt you into the next phase, and do not skip ahead to the file.

### 1. Why it came back

Start the conversation by working through why the Plot Master sent the draft
back, and then each Flag on it, one at a time. For each, say in a sentence or
two what it means for the draft and which scenes, Hooks, outcomes or
`features` it touches, propose a change, and agree it with me before moving on.
A Flag means something the Mod relies on has changed in the World since the
draft was written; the Mod has to fit what is true now.

### 2. Scene breakdown

Where those changes reach the scenes, rework them with me: each scene with its
four parts (what players find, what the NPCs want, what happens if players do
nothing, what moves them on) and where each leads, by the rules in "Where each
part of the story leads." Leave alone what nothing has asked to change.

### 3. Agency checklist

Run the checklist below again against the scenes as they now are, and bring
`## Player Agency Notes` up to date. If an item can't be answered because the
scenes don't settle it yet, take us back to phase 2.

### 4. Produce the file, when I ask

Only when I ask for it, produce the whole revised file. Keep the draft's `id`
exactly as it is: it is how the Plot Master knows this is the same Mod.

**Before you write it, go back and re-read the frontmatter block, the list of
nine body headings and the rules in "Where each part of the story leads" from
the top of these instructions.** Copy the field names and the headings from
there rather than from memory or from the draft.
""",
}


FINISHING = {
    "cli": """\
When I ask for the file, give me the whole of it in one code block, so I can
copy it in one go and send it to the Plot Master.
""",
    "web": """\
When I ask for the file, output it as one complete file: the whole of it, from
the opening `---` to the last section, in a single markdown code block, and
nothing else in that block. Never a part of it, a summary or a list of changes.
The app reads that block as the file and checks it, and tells us what it found;
fix what it reports and give me the whole file again.
""",
}


CHECKLIST = """\
## The checklist

These are the questions phase 3 runs. If the Mod fails one, tell me plainly
and suggest a fix rather than writing around it.

""" + AGENCY_QUESTIONS + """
## Things that will get the Mod sent back

- Killing, maiming, or permanently changing an existing character, NPC or PC,
  without checking first. Propose it in `## GM Notes` and let the Plot Master
  rule.
- Deciding what another Mod Writer's NPC or faction is really up to.
- Writing an in-world date. Timing is set by which Event this runs at, and that
  is not your call.
- Inventing history for something that already exists. If you need a detail
  about an existing NPC or place and do not know it, say so in `## GM Notes`
  and ask. A gap is cheap. A wrong fact that contradicts three years of play is
  not.

Do not soften these to be agreeable. If what I am describing hits one of them,
say so.
"""


START_HERE = {
    "new-mod": """\
## Start here

Ask me the three intake questions now. Then take us through the phases: you
drive the scene work, you run the checklist against it, and you produce the
file when I ask.
""",
    "revise-mod": """\
## Start here

Start now with why the draft was sent back, then each Flag. Then take us
through the phases, and produce the revised file, with the same `id`, when I
ask.
""",
}


def interview_instructions(kind, surface, *, world=None, draft=None, sent_back_reason="",
                           flags=(), mod=None, path=None, continues_from=None, event=None):
    """The instructions for an Interview, as one text to give an LLM as its
    system prompt.

    `kind` is "new-mod", "revise-mod" or "report". `surface` is "cli", for
    pasting into an LLM by hand or using with Claude Code, or "web", for the
    app's own LLM, which is told to give the finished file whole so the app can
    check it.

    `world` is what the person may read in a World, in any form `load_world`
    takes: a directory, a `{path: text}` mapping or a `World`. The caller
    decides what that is; the text holds those documents and nothing else from
    any World. With one, the LLM uses their slugs and proposes only what is
    new. With none, every Feature gets a made-up slug and is proposed.

    For "revise-mod", `draft` is the text of the draft's file, which must have
    an `id`; `sent_back_reason` is why the Plot Master sent it back (may be
    empty); `flags` are its open Flags, each a pair `(the Feature it touches,
    its message)`.

    For "report", `mod` is the text of the Mod's file, which must have an
    `id`. `path` is the Path the Stretch took through the Mod's Dry Run, as
    the steps a report's `path` holds (see `path_steps`), or None when there is
    none. `continues_from` is where play stopped before this report, as
    `check_path` takes it: a `LastStop` (see `last_stop`), a scene's name, or
    None when there is no earlier report. `event` is the id of the Event the
    Stretch was played at, or None for the LLM to ask. With `world`, the
    report's `id` is worked out from the reports in it.

    Each kind takes only its own of these. Raises ValueError for an unknown
    kind or surface; a "revise-mod" with no draft or a draft with no `id`; a
    "report" with no Mod, a Mod with no `id`, or a Path that does not fit the
    Mod's Dry Run from `continues_from`; and any of these given to a kind
    that does not take it. Raises TypeError for a draft, a Mod or an `event`
    that is not text, or a `continues_from` that is none of the three.
    """
    if kind not in KINDS:
        raise ValueError(f"an Interview's kind is one of {', '.join(KINDS)}, not {kind!r}")
    check_surface(surface, "an Interview")
    if kind != "report" and any(value is not None
                                for value in (mod, path, continues_from, event)):
        raise ValueError("only a report Interview takes a Mod, a Path, where the last "
                         "Stretch stopped or an Event")
    if kind == "report":
        if draft is not None or sent_back_reason or flags:
            raise ValueError("a report has no draft, send-back reason or Flags")
        if mod is None:
            raise ValueError("a report Interview needs the Mod it reports on")
        if event is not None and not isinstance(event, str):
            raise TypeError("an Event is given by its id, as text")
        return _report(surface, mod, path, as_last_stop(continues_from), event, world)
    if kind == "revise-mod":
        if draft is None:
            raise ValueError("revising a Mod needs its draft")
        revising = _draft_section(draft, sent_back_reason, flags)
    elif draft is not None or sent_back_reason or flags:
        raise ValueError("a new Mod has no draft, send-back reason or Flags")
    readable = None if world is None else world_section(world, WORLD_INTRO)
    parts = [
        OPENING[kind],
        PRODUCING,
        FEATURES_INVENTED if readable is None else FEATURES_FROM_WORLD,
        REQUIRES,
        HEADINGS,
        DRY_RUN,
        PROPOSED_INVENTED if readable is None else PROPOSED_FROM_WORLD,
        PHASES[kind],
        FINISHING[surface],
        CHECKLIST,
    ]
    if readable is not None:
        parts.append(readable)
    if kind == "revise-mod":
        parts.append(revising)
    parts.append(START_HERE[kind])
    return "\n".join(parts)


REPORT_OPENING = """\
You are helping me, the Mod Runner, write the After-Action Report for one
Stretch of a Mod I ran at a LARP: one continuous stretch of play, which ended
when play stopped. The Mod, what its Mod Writer expected to change and the
Path the Stretch took through the Mod's Dry Run, if there is one, are at the
end of these instructions. Your job is to get the rest from me, to turn it
into one report file in the exact format below, and to push back on me where
the report is vague or claims more than happened.
"""


REPORT_PRODUCING = """\
## What you are producing

One file. It has a YAML frontmatter block at the top between `---` lines, then
a body of fixed headings. Keep every heading listed, in order, even if a
section ends up short.

Write for the Plot Master reading it a week later, who was not there. Plain
past tense, concrete, short.

## Frontmatter

```yaml
---
{id_line}
type: after-action
mod: {mod_id}
{event_line}
{ran_line}
finished: <true or false>
{path_line}mod_runner: <my name or handle>
pcs: [<the id of each PC who took part>]
canon_changes: []
---
```

{rules}"""


ID_GIVEN = "- **`id`** is `{report_id}`. Keep `id: {report_id}` exactly as it is.\n"
ID_CONVENTION = """\
- **`id`** is `aa-{mod_id}` for the first report on this Mod, then
  `aa-{mod_id}-2`, `aa-{mod_id}-3` and so on. If you do not know how many there
  are, ask me.
"""
EVENT_GIVEN = "- **`event`** is `{event}`, the Event this Stretch was played at.\n"
EVENT_ASKED = """\
- **`event`** must be one of the Mod's `events`. If you do not know which, ask
  me.
"""
RAN_WALKED = """\
- **`ran`** is `true`: a Path was walked, so the Mod ran.
"""
RAN_ASKED = """\
- **`ran`** is `false` if the Mod was scheduled and did not happen. Then `pcs`
  is `[]`, `finished` is `false` and there is no Path.
"""
FINISHED_RULE = """\
- **`finished`** is `true` if the Mod has nothing left to play after this
  Stretch, and `false` if play stopped with more to come.
"""
PATH_RULE = """\
- **`path`** is the Path, copied exactly as it is given at the end of these
  instructions: the same steps, in the same order, spelled the same. Do not
  change it, even if what I tell you differs from it. Say so in
  `## Divergences From The Mod` instead.
"""
NO_PATH_RULE = """\
- Leave out `path`. There is no Path for this report.
"""


CANON_CHANGES = """\
## `canon_changes`

Each entry names one entity and one change to it. This list is what the Plot
Master approves or rejects, one change at a time, and what canon is brought up
to date from, so write it in exactly these terms:

```yaml
canon_changes:
  - entity: varen-ashcroft
    kind: status
    decision: proposed
    from: alive
    to: missing
    summary: "Betrayed the party at the chapel and fled north."
  - entity: varen-ashcroft
    kind: relationship
    decision: proposed
    summary: "Now a declared enemy of Tomas Veil."
```

- **`entity`** is the id of an NPC, faction, location, Plot or PC. {ids}
- **`kind`** is one of seven:
{kinds}
- **`decision`** is always `decision: proposed`. Only the Plot Master changes
  it. Never write `note`; that is the Plot Master's too.
- **`from` and `to`**: **Required** for `status`, `location` and `affiliation`,
  and **forbidden** for the others. `from` is the entity's value before this
  Stretch, as its document has it; `to` is its value now. For `location` they
  are location ids, and for `affiliation` faction ids.
- **`summary`** is one line, in plain past tense. It is what a person reads
  about the change, so write it to be read.

Propose only what happened in play. A change the Mod expected and that did not
happen is not a change; it is a divergence.

## Body headings

Use all three, in this order:

`## What Happened` · `## Divergences From The Mod` · `## Loose Ends`

- **What Happened**: the Stretch, in a few short paragraphs.
- **Divergences From The Mod**: compared with the Mod and what it expected to
  change, what went differently. This is the section a review across Plots
  reads.
- **Loose Ends**: hooks that came up in play that nobody has written yet.
"""


IDS_FROM_WORLD = """Use the ids listed under "What you may read in the World,"
  here and in `pcs`. Never guess one: if an entity is not listed, ask me."""


IDS_INVENTED = """If you do not know an entity's id, or a PC's, ask me.
  Never guess one."""


REPORT_PHASES = """\
## How we write it

We work in phases, in this order. You drive the transitions: do not wait for me
to prompt you into the next phase, and do not skip ahead to the file.

### 1. Where play went

{where}

### 2. Who was there

{who}

### 3. What went off-script

Ask me what went off-script: what happened that the Mod did not say would, and
what it said would happen that did not. Compare what I tell you with the Mod
and with what its Mod Writer expected to change. This becomes
`## Divergences From The Mod`.

### 4. What changed in canon

From all of that, propose the canon changes, one at a time, and agree each with
me. Ask about any entity in what the Mod expected to change that I have not
mentioned. Do not invent a change I have not told you about.

### 5. Produce the file, when I ask

Only when I ask for it, produce the file. **Before you write it, go back and
re-read the frontmatter block, the rules for `canon_changes` and the body
headings from the top of these instructions,** and copy the field names from
there rather than from memory.
"""


WHO_WALKED = """\
Ask me which PCs took part (`pcs`)."""


WHO_ASKED = """\
Ask me whether the Mod ran (`ran`), and which PCs took part (`pcs`). If it did
not run, say what that means for the report, and go to phase 5."""


WHERE_WITH_PATH = """\
Start by going through the Path with me, step by step, in a sentence each, and
ask me what happened at each step that the Path does not say. {proposal} Ask me
to confirm it. If I say otherwise, the report says what I say, and
`## Divergences From The Mod` says why the Path and the report differ."""


WHERE_WITHOUT_PATH = """\
There is no Path for this report. Start by asking me to say in my own words
what happened and where play stopped. From that, propose `finished`: `true` if
the Mod reached one of its Possible Outcomes and has nothing left to play,
`false` if play stopped with more to come. Ask me to confirm it."""


STOPPED_AT = """\
### Where the last Stretch stopped

The last report on this Mod says play stopped at `{passage}`. This Stretch
carries on from there.
"""


STOPPED_AMONG = """\
### Where the last Stretch stopped

The players split into Groups, and have come back together for this Stretch.
The last reports on this Mod say play stopped at {stops}. This Stretch carries
on from one of those.
"""


STOPPED_UNKNOWN = """\
### Where the last Stretch stopped

There is an earlier report on this Mod, but where play stopped is not known:
it has no Path that says so. {picked_up}
"""


REPORT_START_HERE = """\
## Start here

{first} Then take us through the phases, and produce the report file when I
ask.
"""


@dataclass(frozen=True)
class _ReportParts:
    """What a report Interview's text is made from that depends on the Mod
    and the Path: the section giving them, what phase 1 says to do, whether a
    Path was walked, and the Mod's id."""

    section: str
    where: str
    walked: bool
    mod_id: str


def _report_parts(mod, path, stop):
    """The Mod, what it expected to change, where the last Stretch stopped,
    and the Path walked, if any, read into `_ReportParts`."""
    from ._story import story

    mod_id, fields = front(mod, "the Mod")
    told = story(mod)
    walked = has_path(path)
    if walked:
        if not told.playable:
            raise ValueError("the Mod has no Dry Run, so it has no Path: "
                             + told.problems[0])
        checked = check_path(told, path, continues_from=stop)
        if not checked.ok:
            raise ValueError("the Path does not fit the Mod's Dry Run: "
                             + "; ".join(checked.problems))
        where = "outcome" if checked.finished else "scene"
        proposal = (f"The Path ends at the {where} `{checked.end.name}`, so it proposes "
                    f"`finished: {'true' if checked.finished else 'false'}`.")
    expected = fields.get("expected_changes")
    lines = []
    if isinstance(expected, dict):
        lines = [f"- `{entity}`: {' '.join(str(said).split())}"
                 for entity, said in expected.items()]
    parts = [
        "## The Mod\n\n"
        f"The report is on `{mod_id}`. Its file:\n\n"
        + fenced(mod, "markdown"),
        "### What its Mod Writer expected to change\n\n"
        + ("\n".join(lines) + "\n" if lines else
           "Nothing: the Mod does not say. Ask me what changed all the same.\n"),
    ]
    if not stop.known:
        parts.append(STOPPED_UNKNOWN.format(
            picked_up="The Path below starts where this Stretch picked up." if walked
            else "Ask me where this Stretch picked up."))
    elif stop.among:
        each = [f"`{stop.among[0]}` for one Group"] + [f"at `{passage}` for another"
                                                       for passage in stop.among[1:]]
        parts.append(STOPPED_AMONG.format(stops=", ".join(each[:-1]) + " and " + each[-1]))
    elif stop.passage is not None:
        parts.append(STOPPED_AT.format(passage=stop.passage))
    if walked:
        parts.append("### The Path walked\n\n"
                     "I walked the Path this Stretch took through the Mod's Dry Run, from the\n"
                     "Hook taken, or where this Stretch picked up, to where play stopped.\n"
                     "Copy it into the report as `path`, exactly:\n\n"
                     + fenced(path_yaml(path), "yaml") + "\n" + proposal + "\n")
        where = WHERE_WITH_PATH.format(proposal=proposal)
    else:
        parts.append("### The Path walked\n\nThere is no Path for this report.\n")
        where = WHERE_WITHOUT_PATH
    return _ReportParts("\n".join(parts), where, walked, mod_id)


def _report_id(mod_id, world):
    """The id of the next report on a Mod, by the convention in
    `schema/after-action.md`: `aa-<mod>`, then `aa-<mod>-2` and so on, the
    first that no document in the World has."""
    from ._api import _files_of

    files = {path: text for path, text in _files_of(world).items()
             if _checks.is_scanned(path)}
    _docs, by_id, _generated = _checks.collect_docs(files, _checks.Findings())
    report_id, n = f"aa-{mod_id}", 1
    while report_id in by_id:
        n += 1
        report_id = f"aa-{mod_id}-{n}"
    return report_id


def _report(surface, mod, path, stop, event, world):
    """The instructions for a report Interview."""
    made = _report_parts(mod, path, stop)
    readable = None if world is None else world_section(world, WORLD_INTRO)
    report_id = None if world is None else _report_id(made.mod_id, world)
    vocab = _checks.load_vocab()["vocabularies"]["canon_change_kind"]
    kinds = "\n".join(f"  - `{kind}`: {' '.join(str(meaning).split())}"
                      for kind, meaning in vocab.items())
    first = ("Start now by going through the Path with me." if made.walked else
             "Start now by asking me to say in my own words what happened and where "
             "play stopped.")
    if report_id is None:
        id_line = (f"id: aa-{made.mod_id}              # aa-{made.mod_id}-2, -3 and so on "
                   f"for later reports on this Mod")
        id_rule = ID_CONVENTION.format(mod_id=made.mod_id)
    else:
        id_line, id_rule = f"id: {report_id}", ID_GIVEN.format(report_id=report_id)
    rules = "".join([
        id_rule,
        EVENT_ASKED if event is None else EVENT_GIVEN.format(event=event),
        RAN_WALKED if made.walked else RAN_ASKED,
        FINISHED_RULE,
        PATH_RULE if made.walked else NO_PATH_RULE,
    ])
    parts = [
        REPORT_OPENING,
        REPORT_PRODUCING.format(
            id_line=id_line,
            mod_id=made.mod_id,
            event_line=("event: <the id of the Event this Stretch was played at>"
                        if event is None else f"event: {event}"),
            ran_line="ran: true" if made.walked else "ran: <true or false>",
            path_line="path: <the Path, exactly as given below>\n" if made.walked else "",
            rules=rules),
        CANON_CHANGES.format(kinds=kinds, ids=IDS_INVENTED if readable is None else
                             IDS_FROM_WORLD),
        REPORT_PHASES.format(where=made.where, who=WHO_WALKED if made.walked else WHO_ASKED),
        FINISHING[surface],
    ]
    if readable is not None:
        parts.append(readable)
    parts.append(made.section)
    parts.append(REPORT_START_HERE.format(first=first))
    return "\n".join(parts)


WORLD_INTRO = """\
## What you may read in the World

These are the only documents in the World I may read. Use nothing else from
the World, and do not guess at what is not here. Each is listed by its slug,
then given in full.
"""


def _draft_section(draft, reason, flags):
    """The draft being revised, why it was sent back and its open Flags."""
    doc_id = draft_id(draft)
    if not isinstance(reason, str):
        raise TypeError("the send-back reason is text")
    lines = []
    for flag in flags:
        if (not isinstance(flag, (tuple, list)) or len(flag) != 2
                or not all(isinstance(part, str) for part in flag)):
            raise TypeError("each Flag is a pair of texts: (the Feature it touches, its message)")
        feature, message = flag
        lines.append(f"- On `{feature.strip()}`: {' '.join(message.split())}")
    parts = [
        "## The draft being revised\n\n"
        f"Keep `id: {doc_id}` exactly as it is: it is how the Plot Master knows the\n"
        "revised file is the same Mod.\n",
        "### Why the Plot Master sent it back\n\n"
        + (reason.strip() + "\n" if reason.strip() else
           "The Plot Master gave no reason. Ask me whether I know one, and work from\n"
           "the Flags.\n"),
        "### Open Flags on it\n\n"
        "Each names the Feature it touches, and what changed.\n\n"
        + ("\n".join(lines) + "\n" if lines else "There are no open Flags on it.\n"),
        "### The draft as it stands\n\n" + fenced(draft, "markdown"),
    ]
    return "\n".join(parts)


FIX_REQUEST = """\
This message is from the app, not the person. The app checked the Mod file you
gave and cannot take it in as it is:

{errors}

The person has not seen the file yet, so do not ask them about these errors.
Fix them, then give the whole file again: from the opening `---` to the last
section, in a single markdown code block, and nothing else in that block, as
your instructions ask.
"""


def interview_fix_request(errors):
    """The message an app sends its LLM, in a "web" Interview, when the Mod
    file the LLM gave has errors, before the person sees the file.

    `errors` is the errors as text, already cut down by the caller to what the
    person may read. Raises ValueError when there are none.
    """
    if not isinstance(errors, str):
        raise TypeError("the errors are text")
    if not errors.strip():
        raise ValueError("a fix request needs the errors to fix")
    return FIX_REQUEST.format(errors=errors.strip())


REVISE_OPENER = """\
Let's begin. Go through why the Plot Master sent the draft back, and then each
Flag on it, one at a time, as your instructions say. If there is no reason and
there are no open Flags, say so and ask me what I want to change.
"""


def interview_revise_opener():
    """The first message an app sends its LLM, on the person's behalf, to open
    a "revise-mod" Interview, so the LLM speaks first: it begins with the
    send-back reason and each Flag that `interview_instructions` gave it.
    """
    return REVISE_OPENER


REPORT_OPENER_WITH_PATH = """\
Let's begin. Go through the Path with me, step by step, as your instructions
say, and then ask me what you need for the rest of the report.
"""


REPORT_OPENER_WITHOUT_PATH = """\
Let's begin. There is no Path for this report, so ask me to say in my own words
what happened and where play stopped, as your instructions say.
"""


def interview_report_opener(path=None):
    """The first message an app sends its LLM, on the person's behalf, to open
    a "report" Interview, so the LLM speaks first. `path` is the Path given to
    `interview_instructions`, or None: with none, the LLM begins by asking the
    Mod Runner to say in words what happened and where play stopped.
    """
    return REPORT_OPENER_WITH_PATH if has_path(path) else REPORT_OPENER_WITHOUT_PATH
