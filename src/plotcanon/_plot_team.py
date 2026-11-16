"""The instructions for the plot team's one-off reports, and reading what the
LLM writes back.

A Reconciliation checks one draft Mod against the World's Canon and the other
drafts waiting for approval. A World review looks across the whole World. Each
is one report, not a conversation, so neither is an Interview.

The text began as larp-llm's `reconciler` and `world-review` agents. plotcanon
owns it now. Each report is written in a fixed shape, so an app can read it
into sections and findings: see `read_reconciliation` and `read_world_review`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._interview import AGENCY_QUESTIONS, SURFACES, _fenced, _front, _readable

RECONCILIATION_SECTIONS = (
    "Conflicts", "Warnings", "Missing links", "Slug mapping", "New entities",
    "Player agency", "Other drafts", "Proposed changes",
)

WORLD_REVIEW_SECTIONS = (
    "State of the World", "Drift", "Watch list", "Weaving", "Coverage",
)

# Sections written as a few sentences, whose findings need not name ids.
PROSE_SECTIONS = ("State of the World",)


SHAPE = """\
## How to write the report

Write these `##` headings, exactly as written here, in this order, and no
others. Write every one of them, even when there is nothing under it: then
write `None.` under it and nothing else.

{headings}

{prose}Under each heading, write each finding as one bullet that starts at the
start of the line with `- `, then the ids it is about, each in backticks and
separated by commas, then a colon, then the finding:

```markdown
- `{example_ids}`: {example_text}
```

Anything more a finding needs, such as a line of explanation or a block of
YAML, goes under its bullet, indented by two spaces. Do not start any other
line with `- ` at the start of the line, and use no `##` headings of your own.
"""


def _shape(sections, example_ids, example_text, prose=""):
    headings = "\n".join(f"## {heading}" for heading in sections)
    return SHAPE.format(headings=_fenced(headings, "markdown").rstrip("\n"),
                        prose=prose, example_ids="`, `".join(example_ids),
                        example_text=example_text)


ONE_REPORT = """\
This is one report, not a conversation. Nobody will answer a question you ask,
so when you need to know something, put the question in the report as a
finding.
"""


TIME_RULE = """\
## A status is a claim about a point in time

A status is a claim about a point in time, not about now. Every NPC, faction,
location and Plot has a `status` and an `as_of`, the Event that status was
true as of, and each Event has an `ordinal`, which is the order Events happen
in. Before you call anything a conflict:

1. Find the earliest Event in the Mod's `events`, and its `ordinal`. A Mod
   with no `events` yet is compared against the World as it stands now.
2. Work out each entity's state as of the start of that earliest Event, not
   its state now. A Canon Change recorded at an Event is what that Event
   did, so it has not happened yet when a Mod that first runs at that Event
   begins.
3. Compare against that.

A Mod that first runs at the third Event and uses an NPC who died at the fifth
is correct. Calling it a conflict is worse than saying nothing: it teaches the
Plot Master to ignore you.
"""


RECONCILIATION_CHECKS = """\
## What to check

**Status.** For each entity in the Mod's `features`, compare the state the
Mod assumes with the state Canon holds as of the Mod's earliest Event. Getting
the weight right is most of your use:

| Canon holds | Where it goes |
|---|---|
| NPC `final-death` | Conflicts. Only a flashback or a corpse is allowed. |
| NPC `dead` | Warnings. The World can reverse death, but the Mod must say how and why. |
| NPC `missing` | Warnings. Their return is a story in itself, and should be meant. |
| NPC `departed` | Warnings, but only when the Mod gives no reason for their travel. |
| Anything `unknown` | Warnings, as a question. Canon does not say: ask, and assume neither way. |
| Plot `resolved` | Warnings. Reopening it is allowed, but must be meant. |
| Plot `abandoned` | Conflicts. It will not conclude. Do not build on it. |
| Faction `disbanded` | Conflicts, when the Mod has it acting as a body. |

The Mod contradicting itself goes under Conflicts too: the body against its
own frontmatter, `expected_changes` naming an entity not in `features`, or
an outcome that contradicts `requires`.

**Missing links.** The checks find a body naming an entity's id or alias that
`features` leaves out, but nothing else. Read the body for entities named
another way: "the knight who lost the ford", "her brother", "the Order's man
in the harbour". Each needs its id in `features`, or anyone looking for what
touches that entity will not find this Mod. This is where you are most likely
to find what the checks cannot.

**Slug mapping.** The Mod Writer may not have seen the World, so the ids in
`features` and in `## Proposed New Entities` are guesses until you check
them. For each one, look the entity up by the name the Mod Writer wrote, in
the `title` and `aliases` of everything in the World, not by the guessed id:

- If one entity matches, give the real id. Do this whether the Mod Writer
  marked it `NEW` or `I THINK THIS EXISTS`: that mark is a guess too.
- If nothing matches, it is new: say NEW.
- If more than one matches, say AMBIGUOUS and name each. Do not choose.

What matters most here is an entry marked `NEW` that already exists. Taking
it in makes a second file for one entity, and from then on some Mods point at
one and some at the other, which no check will notice.

**New entities.** For each guessed id that is truly new, propose a short
file for it with `canon: proposed`, and an id that follows the World's
conventions. The Mod Writer's id is a starting point, not a rule. Do not
suggest making it `approved`: an After-Action Report does that, once the Mod
has run.

**Player agency.** Ask each of these of the Mod, and report each it fails:

{agency}
**Other drafts.** Two drafts at the same Event, with the same `slot` or none,
happen at the same time. Check the other drafts waiting for approval for the
same NPC in two places at once, the same Plot resolved two ways, the same
entity's fate decided twice, or one draft undoing what another sets up.

**Proposed changes.** The changes that would settle what you found, as the
exact frontmatter or body text to paste, each under the bullet for it. You
never make them: the Plot Master does.
"""


RECONCILIATION_DONT = """\
## What not to do

- Do not rewrite the Mod or improve its prose. You are not its editor.
- Do not choose a side in a conflict. Set out both, and let the Plot Master
  decide. If you have a view, give it in one line and say it is yours.
- Do not invent Canon to fill a gap. "Canon does not say" is a finding, and a
  useful one.
- Do not repeat the check findings, under "The checks" below. The Plot
  Master has them already. Report only what they miss.
- Do not soften a real conflict to be agreeable. A missed contradiction
  reaches the field, and a player finds it at 2am.
- Never write a change as though you made it.

A short report is a good one. Do not pad it.
"""


RECONCILIATION_OPENING = """\
You check a draft Mod for a LARP against the World's Canon, and against the
other drafts waiting for approval, and report what you find to the Plot
Master, who reads it before approving the Mod or sending it back. You propose;
the Plot Master decides.
"""


SLUG_EXAMPLE = """\
Under Slug mapping, start each bullet with the Mod Writer's guessed id alone,
then say what it is:

```markdown
- `greymoor-chapel`: is `the-greymoor-chapel`, by its alias "Greymoor Chapel".
- `sister-oleen`: NEW. Nothing in the World is called "Sister Oleen".
- `the-captain`: AMBIGUOUS. Could be `ysolde-marr` or `harrow-dunmore`.
```

Under Other drafts, start each bullet with the other draft's id, then the ids
of what the two drafts both touch.
"""


def _check_findings(findings, surface):
    if findings is None and surface == "cli":
        return """\
## The checks

Run plotcanon's checks on the World first (`plotcanon validate`), and read
what they find. Do not repeat their findings in your report: the Plot Master
has them already.
"""
    if isinstance(findings, str):
        raise TypeError("the check findings are a list, each a Finding or text")
    lines = []
    for finding in findings or ():
        if not isinstance(finding, str) and not hasattr(finding, "message"):
            raise TypeError("each check finding is a Finding or text")
        lines.append(f"- {' '.join(str(finding).split())}")
    body = ("\n".join(lines) + "\n") if lines else "They found nothing.\n"
    return ("## The checks\n\nplotcanon's checks have already run. Do not repeat their "
            "findings in your\nreport: the Plot Master has them already. They "
            "found:\n\n" + body)


def _world(world, surface, what):
    if world is not None:
        return _readable(world)
    if surface == "web":
        raise ValueError(f"{what} on the web needs the World")
    return """\
## The World

Read the World from the files here: `canon/`, `mods/` and `after-actions/`,
with `schema/` for what each field means and the values each may take.
"""


def _draft(draft, surface):
    if draft is None:
        if surface == "web":
            raise ValueError("a Reconciliation needs the draft it checks")
        return ("## The draft\n\nThe draft to check is the one I name. Read it in "
                "`inbox/`.\n")
    doc_id = _front(draft, "the draft")[0]
    return f"## The draft: `{doc_id}`\n\n" + _fenced(draft, "markdown")


def _other_drafts(drafts, surface):
    if drafts is None and surface == "cli":
        return ("## The other drafts\n\nThe other drafts waiting for approval are "
                "the other Mods in `inbox/`.\n")
    if isinstance(drafts, str):
        raise TypeError("the other drafts are a list of texts, one per draft")
    parts = ["## The other drafts\n\nThese are the other drafts waiting for "
             "approval.\n"]
    for draft in drafts or ():
        doc_id = _front(draft, "another draft")[0]
        parts.append(f"### `{doc_id}`\n\n" + _fenced(draft, "markdown"))
    if len(parts) == 1:
        parts = ["## The other drafts\n\nNo other drafts are waiting for approval.\n"]
    return "\n".join(parts)


def _surface(surface, what):
    if surface not in SURFACES:
        raise ValueError(f"{what}'s surface is one of {', '.join(SURFACES)}, "
                         f"not {surface!r}")


def reconciliation_instructions(surface, *, draft=None, world=None, other_drafts=None,
                                findings=None):
    """The instructions for a Reconciliation, as one text to give an LLM as its
    system prompt: it checks a draft Mod against the World's Canon and the
    other drafts waiting for approval, and writes one report for the Plot
    Master, in the shape `read_reconciliation` reads.

    `surface` is "web", for the app's own LLM, or "cli", for larp-llm or for
    pasting into an LLM by hand. `draft` is the text of the draft's file,
    which must have an `id`. `world` is the World as the plot team reads it,
    in any form `load_world` takes. `other_drafts` is the text of each other
    draft waiting for approval; empty when there are none. `findings` is what
    plotcanon's checks found on the draft, each a `Finding` or a line of text,
    so the LLM does not repeat them; empty when there are none.

    On "web" the draft and the World are needed. On "cli" each may be left
    out: the LLM then reads the World from the files, the draft I name and
    the other drafts from `inbox/`, and runs the checks itself.

    Raises ValueError for an unknown surface, a "web" call missing the draft
    or the World, or a draft with no `id`. Raises TypeError for a draft that
    is not text, or other drafts or findings given as one text rather than a
    list.
    """
    _surface(surface, "a Reconciliation")
    parts = [
        RECONCILIATION_OPENING,
        ONE_REPORT,
        TIME_RULE,
        RECONCILIATION_CHECKS.format(agency=AGENCY_QUESTIONS),
        RECONCILIATION_DONT,
        _shape(RECONCILIATION_SECTIONS, ("ysolde-marr", "the-salt-ledger"),
               "the Mod has her give an order at the third Event, but she is "
               "`final-death` as of the second."),
        SLUG_EXAMPLE,
        _check_findings(findings, surface),
        _world(world, surface, "a Reconciliation"),
        _draft(draft, surface),
        _other_drafts(other_drafts, surface),
        "## Start here\n\nWrite the report now, in the shape above, and nothing "
        "else.\n",
    ]
    return "\n".join(parts)
