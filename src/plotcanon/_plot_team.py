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

from ._api import Finding
from ._prompt import AGENCY_QUESTIONS, check_surface, draft_id, fenced, readable
from ._story import _lines

RECONCILIATION_SECTIONS = (
    "Conflicts", "Warnings", "Missing links", "Slug mapping", "New entities",
    "Player agency", "Other drafts", "Proposed changes",
)

WORLD_REVIEW_SECTIONS = (
    "State of the World", "Drift", "Watch list", "Weaving", "Coverage",
)

RECONCILIATION_VERDICTS = ("clean", "clean with warnings", "conflicts, do not approve yet")

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
    return SHAPE.format(headings=fenced(headings, "markdown").rstrip("\n"),
                        prose=prose, example_ids="`, `".join(example_ids),
                        example_text=example_text)


START_HERE = """\
## Start here

Write the report now, in the shape above, and nothing else.
"""


DONT_REPEAT = ("Do not repeat the check findings in the report: the plot team has "
               "them already. Report only what they miss.")


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
the `title` and `aliases` of everything in the World, not by the guessed id.
An entity exists only if a document under "The World" has it: a draft that
proposes it, this one or another, does not make it exist.

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
- {dont_repeat}
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


RECONCILIATION_SHAPE = """\
Start the report with one line, before the first heading, giving the
verdict, which is one of these:

- `Verdict: conflicts, do not approve yet`, when Conflicts has any finding.
- `Verdict: clean with warnings`, when Conflicts has none but another section
  has.
- `Verdict: clean`, when every section is `None.`

Under Conflicts, give each finding two more lines under its bullet: `Source:`
and the file and field that hold what Canon says, and `Options:` and the ways
out, in a line each:

```markdown
- `ysolde-marr`, `the-salt-ledger`: the Mod has her give an order at the
  third Event, but she is `final-death` as of the second.
  Source: `canon/npcs/ysolde-marr.md`: `status`
  Options: a flashback; another captain gives the order.
```

Under Slug mapping, start each bullet with the Mod Writer's guessed id alone,
then say what it is:

```markdown
- `greymoor-chapel`: is `the-greymoor-chapel`, by its alias "Greymoor Chapel".
- `sister-oleen`: NEW. Nothing in the World is called "Sister Oleen".
- `the-captain`: AMBIGUOUS. Could be `ysolde-marr` or `harrow-dunmore`.
```

Under Other drafts, start each bullet with the other draft's id, exactly as
it is under "The other drafts", then the ids of what the two drafts both
touch.
"""


def _check_findings(findings, surface):
    if findings is None and surface == "cli":
        return ("## The checks\n\nRun plotcanon's checks on the World first "
                "(`plotcanon validate`), and read\nwhat they find. " + DONT_REPEAT + "\n")
    if isinstance(findings, str):
        raise TypeError("the check findings are a list, each a Finding or text")
    lines = []
    for finding in findings or ():
        if not isinstance(finding, (str, Finding)):
            raise TypeError("each check finding is a Finding or text")
        lines.append(f"- {' '.join(str(finding).split())}")
    found = ("They found:\n\n" + "\n".join(lines) + "\n") if lines else "They found nothing.\n"
    return ("## The checks\n\nplotcanon's checks have already run. " + DONT_REPEAT
            + "\n\n" + found)


WORLD_GIVEN = """\
## The World

These are the World's documents, as the plot team reads them. Use
nothing else from the World, and do not guess at what is not here. Each is
listed by its id, then given in full.{left_out}
"""

DRAFTS_LEFT_OUT = """ The draft and the other drafts are
left out of the World here, and given in their own sections below, as they
stand now."""

WORLD_FROM_FILES = """\
## The World

Read the World from the files here: `canon/`, `mods/` and `after-actions/`,
with `schema/` for what each field means and the values each may take.{left_out}
"""

INBOX_LEFT_OUT = """ The
drafts in `inbox/` are not part of the World for this: they are under "The
draft" and "The other drafts"."""


def _world(world, surface, what, *, drafts=None):
    """The World section. `drafts` is the ids of the drafts given in their own
    sections, for a Reconciliation, which are left out of the World."""
    if world is not None:
        left_out = "" if drafts is None else DRAFTS_LEFT_OUT
        return readable(world, WORLD_GIVEN.format(left_out=left_out), leave_out=drafts or ())
    if surface == "web":
        raise ValueError(f"{what} on the web needs the World")
    return WORLD_FROM_FILES.format(left_out="" if drafts is None else INBOX_LEFT_OUT)


def _draft(draft, surface):
    if draft is None:
        if surface == "web":
            raise ValueError("a Reconciliation needs the draft it checks")
        return ("## The draft\n\nThe draft to check is the one named in the request. "
                "Read it in `inbox/`.\n")
    return f"## The draft: `{draft_id(draft)}`\n\n" + fenced(draft, "markdown")


def _other_drafts(drafts, surface):
    if drafts is None and surface == "cli":
        return ("## The other drafts\n\nThe other drafts waiting for approval are "
                "the other Mods in `inbox/`.\n")
    if isinstance(drafts, str):
        raise TypeError("the other drafts are a list of texts, one per draft")
    parts = ["## The other drafts\n\nThese are the other drafts waiting for "
             "approval.\n"]
    for draft in drafts or ():
        parts.append(f"### `{draft_id(draft, 'another draft')}`\n\n"
                     + fenced(draft, "markdown"))
    if len(parts) == 1:
        parts = ["## The other drafts\n\nNo other drafts are waiting for approval.\n"]
    return "\n".join(parts)


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
    out: the LLM then reads the World from the files, the draft named in the
    request and the other drafts from `inbox/`, and runs the checks itself.
    The draft and the other drafts are left out of the World as given, since
    the plot team's World holds `inbox/`: they are given once, in their own
    sections.

    Raises ValueError for an unknown surface, a "web" call missing the draft
    or the World, or a draft with no `id`. Raises TypeError for a draft that
    is not text, or other drafts or findings given as one text rather than a
    list.
    """
    check_surface(surface, "a Reconciliation")
    drafts = _other_drafts(other_drafts, surface)
    given = _draft(draft, surface)
    ids = ([] if draft is None else [draft_id(draft)]) + [
        draft_id(other, "another draft") for other in other_drafts or ()]
    parts = [
        RECONCILIATION_OPENING,
        ONE_REPORT,
        TIME_RULE,
        RECONCILIATION_CHECKS.format(agency=AGENCY_QUESTIONS),
        RECONCILIATION_DONT.format(dont_repeat=DONT_REPEAT),
        _shape(RECONCILIATION_SECTIONS, ("tobren-vale",),
               '"her brother" in the second scene is Tobren, and `features` '
               "leaves him out."),
        RECONCILIATION_SHAPE,
        _check_findings(findings, surface),
        _world(world, surface, "a Reconciliation", drafts=ids),
        given,
        drafts,
        START_HERE,
    ]
    return "\n".join(parts)


WORLD_REVIEW_OPENING = """\
You take the long view of a LARP's World, across all its Campaigns, and report
to the plot team. Everything else checks one document at a time; you are the
only pass that looks at the whole World. You report; the Plot Master decides.

Do not repeat what a Reconciliation does, which checks one draft Mod against
Canon at one moment. Look for what no check of a single document can see.
"""


WORLD_REVIEW_CLOCK = """\
## The clock

Put the Events in order by `ordinal`, and mark which have run (`complete`),
which are to come (`planned`), and which were `cancelled`. Interludes sit
between Events in the same order. A status is a claim about a point in time:
read every `status` together with its `as_of`.
"""


WORLD_REVIEW_CHECKS = """\
## What drift looks like

**Slow contradictions.** Compare Canon against itself over time: an NPC in two
places at one Event; a faction `active` while every Mod for four Events has
treated it as broken; a location `controlled_by` a faction that disbanded two
Events ago.

**Plots that lost their way.** A Plot marked `open` whose last Mod was six
Events ago is not open but dormant, and misleads a Mod Writer looking for
something to pick up. A `dormant` Plot that three recent Mods have moved on is
open, and nobody said so.

**Undecided and unapplied history.** Canon Changes still at `decision:
proposed` long after their Event, and entities whose `as_of` is far behind the
latest Event that ran. Canon that lags play by two Events makes every
Reconciliation after it wrong. Report the worst first, by how far behind they
are.

**What was written against what was played.** Read the `## Divergences From
The Mod` sections of recent After-Action Reports together. One divergence is
one night's play. The same divergence three times is a pattern: an NPC nobody
plays as written, a Plot the players keep turning down, a faction that reads
as villains when it should not. This is the most useful thing in the report,
and the only place it can be seen.

## What to weave

Find chances to connect what is already being written. **Do not disturb what
Mod Writers are already writing.** A good suggestion adds to what exists: an
NPC who could be in a Mod already written, a Plot two Mods could both touch, a
consequence from one Event that would land well in a Mod already planned for a
later one. A bad suggestion asks a Mod Writer to change their premise.

Look first for:

- **Recurring NPCs with nothing planned.** Known to players, and idle. The
  cheapest story there is.
- **Dormant Plots with a live hook.** Read each Plot's `## Where It Could Go`:
  Mod Writers wrote it for this.
- **Loose ends.** The `## Loose Ends` of After-Action Reports are hooks play
  made and nobody took up. Check them against what is planned.
- **Consequences nobody used.** Something Canon says happened that no Mod has
  answered yet.

For each, say what to connect, which document it attaches to, why it fits,
and how much it disturbs: none, a small addition, or needs the Mod Writer to
agree. Put the least disturbing first.

## What coverage means

Which NPCs, factions and locations carry everything, and which have not
appeared in ten Events. Which Mod Writers are all writing into the same corner
of the World. Which Event to come has nothing planned.

## How to judge

- **Be specific or say nothing.** "Consider deepening the factions" is noise.
  "The Order has been in six Mods and no PC has met anyone above its captain;
  a scene in a Mod already planned could change that" is a suggestion.
- **Do not invent Canon.** Everything you suggest must attach to something
  that exists, named by its id.
- **Say when the World is fine.** A short report is allowed, and believed
  more than a long one padded to look thorough.
- **Rank hard.** Five findings the plot team acts on beat thirty they skim.
  Put the worst drift first.
"""


WORLD_REVIEW_SECTION_NOTES = """\
Under State of the World, write three or four sentences, not bullets: the
Events run, the Mods finished, the Plots open, and where things stand. Under
Drift, what needs the plot team now, worst first. Under Watch list, what is
not wrong yet but is heading that way. Under Weaving, the suggestions, least
disturbing first. Under Coverage, what is used too much and too little, and
the Events to come with nothing planned.

Every claim cites the ids it is about and the files that show it, so the plot
team can check it in ten seconds. Under each bullet outside State of the
World, give a line `Files:` and the path of each of those files, in
backticks:

```markdown
- `feud-of-vale-and-marr`: marked `open`, but no Mod has touched it in five
  Events.
  Files: `canon/plots/feud-of-vale-and-marr.md`, `mods/tideward/the-low-tide-market.md`
```
"""


def world_review_instructions(surface, *, world=None, findings=None):
    """The instructions for a World review, as one text to give an LLM as
    its system prompt: it looks across the whole World for drift, Plots that
    lost their way, undecided and unapplied history, and chances to bring
    back recurring NPCs and dormant Plots, and writes one report for the plot
    team, in the shape `read_world_review` reads.

    `surface` is "web", for the app's own LLM, or "cli", for larp-llm or for
    pasting into an LLM by hand. `world` is the whole World as the plot team
    reads it, in any form `load_world` takes. `findings` is what plotcanon's
    checks found on the World, each a `Finding` or a line of text, so the LLM
    does not repeat them; empty when there are none.

    On "web" the World is needed. On "cli" either may be left out: the LLM
    then reads the World from the files and runs the checks itself.

    Raises ValueError for an unknown surface or a "web" call with no World.
    Raises TypeError for findings given as one text rather than a list.
    """
    check_surface(surface, "a World review")
    parts = [
        WORLD_REVIEW_OPENING,
        ONE_REPORT,
        WORLD_REVIEW_CLOCK,
        WORLD_REVIEW_CHECKS,
        _shape(WORLD_REVIEW_SECTIONS, ("feud-of-vale-and-marr",),
               "marked `open`, but no Mod has touched it in five Events.",
               prose="State of the World is the one section written as "
               "sentences rather than bullets. "),
        WORLD_REVIEW_SECTION_NOTES,
        _check_findings(findings, surface),
        _world(world, surface, "a World review"),
        START_HERE,
    ]
    return "\n".join(parts)


@dataclass(frozen=True)
class ReportFinding:
    """One finding in a Reconciliation or a World review: the `ids` it starts
    with, in the order written, and the rest of its `text`, with any lines
    under its bullet."""

    ids: tuple
    text: str


@dataclass(frozen=True)
class ReportSection:
    """One `##` section of a Reconciliation or a World review: its `heading`,
    everything under it as `text`, and its `findings`, one per bullet."""

    heading: str
    text: str
    findings: tuple


@dataclass(frozen=True)
class ReadReport:
    """A Reconciliation or a World review, read: its `sections` in the order
    written, and the `problems` with its shape, each as a sentence. Text
    before the first heading is not kept, but for a Reconciliation's
    verdict."""

    sections: tuple
    problems: tuple

    def section(self, heading):
        """The section with this heading, or None when there is none."""
        return next((s for s in self.sections if s.heading == heading), None)


@dataclass(frozen=True)
class ReadReconciliation(ReadReport):
    """A Reconciliation, read. As well as its sections and problems:
    `verdict`, one of RECONCILIATION_VERDICTS, or None when it gives none of
    them; and `other_drafts`, the id of each other draft its Other drafts
    section names, in order, once each."""

    verdict: str | None = None
    other_drafts: tuple = ()


_HEADING = re.compile(r"^##\s+(?!#)(.*?)\s*#*\s*$")
_IDS = re.compile(r"^((?:`[^`\s]+`\s*,\s*)*`[^`\s]+`)\s*:\s*")
_VERDICT = re.compile(r"^[\W_]*verdict[\W_]*:(.*)$", re.I)


def _plain(text):
    """Text as lowercase words, for comparing what an LLM wrote."""
    return " ".join(re.findall(r"[a-z]+", text.lower()))


def _finding(lines):
    first, rest = lines[0][2:].strip(), lines[1:]
    matched = _IDS.match(first)
    ids = tuple(re.findall(r"`([^`]+)`", matched.group(1))) if matched else ()
    body = [first[matched.end():] if matched else first]
    body += [line[2:] if line.startswith("  ") else line for line in rest]
    return ReportFinding(ids, "\n".join(body).strip())


def _section(heading, lines):
    findings, current = [], None
    for line, fenced_line in lines:
        if not fenced_line and line.startswith("- "):
            current = [line]
            findings.append(current)
        elif current is not None:
            current.append(line)
    text = "\n".join(line for line, _fenced in lines).strip()
    return ReportSection(heading, text, tuple(_finding(f) for f in findings))


def _read(text, expected, what):
    """The sections and problems of a report, and the lines before its first
    heading."""
    if not isinstance(text, str):
        raise TypeError(f"{what} is text, not {type(text).__name__}")
    before, headed = [], []
    for line, fenced_line in _lines(text):
        line = line.rstrip("\r\n")
        heading = None if fenced_line else _HEADING.match(line)
        if heading:
            headed.append((heading.group(1), []))
        elif headed:
            headed[-1][1].append((line, fenced_line))
        elif not fenced_line:
            before.append(line)
    problems, sections, seen = [], [], []
    for heading, lines in headed:
        if heading not in expected:
            problems.append(f"`## {heading}` is not one of the headings {what} has")
        elif heading in seen:
            problems.append(f"`## {heading}` is written twice")
        else:
            seen.append(heading)
            sections.append(_section(heading, lines))
    if seen != [h for h in expected if h in seen]:
        problems.append(f"the headings are not in order: {', '.join(expected)}")
    for heading in expected:
        if heading not in seen:
            problems.append(f"there is no `## {heading}`")
    for section in sections:
        if section.heading in PROSE_SECTIONS:
            continue
        for finding in section.findings:
            if not finding.ids:
                problems.append(f"a finding under `## {section.heading}` does not start "
                                f"with the ids it is about: {finding.text.splitlines()[0]!r}")
    return ReadReport(tuple(sections), tuple(problems)), before


def _verdict(before, read):
    """The verdict in the lines before the first heading, and its problems.
    It is checked against the findings only when every heading is as asked."""
    written = next((m.group(1) for m in map(_VERDICT.match, before) if m), None)
    if written is None:
        return None, ["there is no verdict: a line `Verdict: ...` before the first heading"]
    verdict = next((v for v in RECONCILIATION_VERDICTS if _plain(v) == _plain(written)), None)
    if verdict is None:
        return None, [f"the verdict {written.strip()!r} is not one of "
                      f"{', '.join(RECONCILIATION_VERDICTS)}"]
    if read.problems and any(p.startswith(("there is no", "the headings", "`##"))
                             for p in read.problems):
        return verdict, []
    if read.section("Conflicts").findings:
        due = RECONCILIATION_VERDICTS[2]
    elif any(section.findings for section in read.sections):
        due = RECONCILIATION_VERDICTS[1]
    else:
        due = RECONCILIATION_VERDICTS[0]
    if verdict != due:
        return verdict, [f"the verdict is {verdict!r}, but the findings make it {due!r}"]
    return verdict, []


def _conflicts_problems(read):
    conflicts = read.section("Conflicts")
    problems = []
    for finding in conflicts.findings if conflicts else ():
        starts = {line.split(":", 1)[0].strip().lower() for line in finding.text.splitlines()}
        if not {"source", "options"} <= starts:
            problems.append(f"a conflict does not give both `Source:` and `Options:`: "
                            f"{finding.text.splitlines()[0]!r}")
    return problems


def _named_drafts(read, draft_ids):
    section = read.section("Other drafts")
    named, problems = [], []
    for finding in section.findings if section else ():
        if not finding.ids:
            continue
        first = finding.ids[0]
        if draft_ids is not None and first not in draft_ids:
            problems.append(f"a finding under `## Other drafts` starts with `{first}`, "
                            f"which is not one of the other drafts given")
        elif first not in named:
            named.append(first)
    return tuple(named), problems


def read_reconciliation(text, *, draft_ids=None):
    """Read what an LLM wrote for a Reconciliation, as a ReadReconciliation:
    its verdict, its sections and findings, the other drafts it names, and
    `problems` where the text strays from the shape the instructions ask for.
    Each section is one of RECONCILIATION_SECTIONS. A section headed as asked
    is read even when there are problems elsewhere.

    The shape: first a line `Verdict: <one of RECONCILIATION_VERDICTS>`. Then
    each heading is a line `## <heading>`. Under it, each finding is a bullet
    at the start of a line, `- `, then its ids, each in backticks and
    separated by commas, then `:` and the finding. Lines under a bullet,
    indented by two spaces, belong to it. Each Conflict has a `Source:` line
    and an `Options:` line. Under Other drafts, the first id is the other
    draft's. `None.` means a section has no findings. Headings and bullets
    inside a code block are not read.

    The problems: no verdict, or one that is not one of the verdicts or that
    the findings do not bear out (checked only when the headings are as
    asked); a heading missing, written twice, out of order or not one of
    them; a finding that does not start with ids; a Conflict with no Source
    or Options; and, given `draft_ids`, the ids of the other drafts given to
    the instructions, an Other drafts finding that starts with another id,
    which is then left out of `other_drafts`. Raises TypeError when `text` is
    not text.
    """
    read, before = _read(text, RECONCILIATION_SECTIONS, "a Reconciliation")
    if isinstance(draft_ids, str):
        raise TypeError("draft_ids is a list of ids")
    verdict, verdict_problems = _verdict(before, read)
    named, named_problems = _named_drafts(
        read, None if draft_ids is None else frozenset(draft_ids))
    problems = (*verdict_problems, *read.problems, *_conflicts_problems(read), *named_problems)
    return ReadReconciliation(read.sections, problems, verdict, named)


def read_world_review(text):
    """Read what an LLM wrote for a World review into its sections and
    findings, as `read_reconciliation` does, with WORLD_REVIEW_SECTIONS and
    no verdict. State of the World is written as sentences, so a bullet
    under it need not start with ids. Raises TypeError when `text` is not
    text.
    """
    return _read(text, WORLD_REVIEW_SECTIONS, "a World review")[0]
