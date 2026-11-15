"""A Mod's story: the branching its body describes by the Dry Run convention
(`schema/mod.md`), read into a graph with plain code.

    ## Premise                 where a Dry Run starts
    ## Hooks                   - Oleen asks the party → [[The vigil itself]]
    ## Scene Breakdown
    ### 1. The vigil itself    a scene
    **Leads to:** the third bell → [[The Order comes through]]
    **Contest:** fight the Order, win → [[Order driven off]], lose → [[Register taken]]
    ## Possible Outcomes
    ### Order driven off       an ending

Nothing here raises on what a body holds. What is wrong with the story is
returned on it, as `problems` (no Dry Run can be built) and `gaps` (one can,
but part of the Mod cannot be reached or leads nowhere).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

START, SCENE, ENDING = "start", "scene", "ending"

PREMISE = "premise"
HOOKS = "hooks"
SCENES = "scene breakdown"
OUTCOMES = "possible outcomes"

HEADING_RE = re.compile(r"^(#{2,3})[ \t]+(.*?)[ \t]*#*[ \t]*$")
FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")
NUMBER_RE = re.compile(r"^\d+[.)][ \t]+")
# `**Leads to:**`, `**Contest:**`, `**If players do nothing:**` and the like.
MARKER_RE = re.compile(r"\*\*([^*\n]+?):\*\*")
# `label → [[Target]]`, with `->` accepted for the arrow.
LINK_RE = re.compile(r"(?:→|->)[ \t]*\[\[([^\[\]\n]+)\]\]")
BULLET_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+")

CONTEST = "contest"
LEADS_TO = "leads to"
DO_NOTHING = "if players do nothing"


def key(name):
    """What a link and a heading are matched on: the text, without a number
    prefix like `1. `, with runs of spaces as one, in any case."""
    return " ".join(NUMBER_RE.sub("", name.strip()).split()).casefold()


def display(heading):
    """A heading's text as a passage's name: without its number prefix."""
    return " ".join(NUMBER_RE.sub("", heading.strip()).split())


@dataclass(frozen=True)
class Exit:
    """One way on from a passage, or one result of a Contest.

    `label` is the text written before the arrow, such as "the third bell" or
    "win". `target` is the link as written, such as "3. The Order comes
    through". `passage` is the name of the passage it leads to, or None when
    no scene or outcome has that heading. `players_do_nothing` is true for an
    exit written on the `**If players do nothing:**` line.
    """

    label: str
    target: str
    passage: str | None
    players_do_nothing: bool = False


@dataclass(frozen=True)
class Contest:
    """A point whose result depends on play not written in advance, such as a
    fight. `label` is what is contested ("fight the Order"); each of `results`
    is an `Exit` whose label names the result ("win", "lose")."""

    label: str
    results: tuple


@dataclass(frozen=True)
class Passage:
    """One place a Dry Run can be: the Premise (`kind` "start"), a scene
    ("scene") or a Possible Outcome ("ending").

    `name` is the heading without its number prefix, and is what `Exit.passage`
    holds. `heading` is the heading as written. `text` is everything under the
    heading, exactly as written, and `prose` is that text without the
    `**Leads to:**` and `**Contest:**` lines and without the `→ [[...]]` links,
    for showing beside the choices. The Premise's exits are the Hooks.
    """

    name: str
    heading: str
    kind: str
    text: str
    prose: str
    exits: tuple = ()
    contests: tuple = ()

    @property
    def choices(self):
        """Every way on from here, exits first and then each Contest's
        results, as `Exit`s."""
        return self.exits + tuple(r for c in self.contests for r in c.results)


@dataclass(frozen=True)
class Section:
    """One `## ` section of a body. `heading` is its text, or "" for whatever
    comes before the first heading. `source` is the section exactly as written,
    heading line included, so the sources joined are the body."""

    heading: str
    source: str


@dataclass(frozen=True)
class Story:
    """A Mod's story, as a graph.

    `start` is the Premise passage, or None. `passages` are the start, the
    scenes and the endings, in the order the body has them. `sections` are the
    whole body, section by section. `structured` is true when the body uses the
    convention at all: a link or a Contest anywhere in the story.

    `problems` say why a Dry Run cannot be built, one sentence each; `gaps`
    say what in it cannot be reached or leads nowhere. A story is `playable`
    when it has no problems.
    """

    start: Passage | None
    passages: tuple
    sections: tuple
    structured: bool
    problems: tuple = ()
    gaps: tuple = ()

    @property
    def playable(self):
        return not self.problems

    @property
    def endings(self):
        return tuple(p for p in self.passages if p.kind == ENDING)

    @property
    def scenes(self):
        return tuple(p for p in self.passages if p.kind == SCENE)

    def passage(self, name):
        """The passage a link or a name leads to, matched as links are, or
        None."""
        wanted = key(name)
        return next((p for p in self.passages if key(p.name) == wanted), None)


def _lines(text):
    """Each line of a text with its line break, and whether it is inside a
    fenced code block (or is a fence line itself)."""
    fenced = False
    for line in text.splitlines(keepends=True):
        if FENCE_RE.match(line):
            fenced = not fenced
            yield line, True
            continue
        yield line, fenced


def _split(text, level):
    """Split text at headings of exactly `level` `#`s, outside code blocks.
    Returns `[(heading or None, heading line + content, content)]`."""
    parts, heading, head_line, content = [], None, "", []
    for line, fenced in _lines(text):
        m = None if fenced else HEADING_RE.match(line.rstrip("\r\n"))
        if m and len(m.group(1)) == level:
            if heading is not None or content:
                parts.append((heading, head_line + "".join(content), "".join(content)))
            heading, head_line, content = m.group(2), line, []
        else:
            content.append(line)
    if heading is not None or content:
        parts.append((heading, head_line + "".join(content), "".join(content)))
    return parts


def _label(text):
    text = BULLET_RE.sub("", text)
    return " ".join(text.strip().strip(",;").split())


def _parse(text):
    """The exits and Contests written in a passage's text, as unresolved
    `(label, target, players_do_nothing)` and `(label, [(label, target)])`,
    and its prose."""
    exits, contests, prose = [], [], []
    for line, fenced in _lines(text):
        if fenced or not LINK_RE.search(line) and not _is_contest_line(line):
            prose.append(line)
            continue
        # The line in chunks, each led by the `**Marker:**` before it.
        chunks, marker, last = [], None, 0
        for m in MARKER_RE.finditer(line):
            chunks.append((marker, line[last:m.start()]))
            marker, last = m.group(1).strip().casefold(), m.end()
        chunks.append((marker, line[last:]))
        kept = []
        for marker, chunk in chunks:
            if marker == CONTEST:
                contests.append(_contest(chunk))
                continue
            links, rest, last = [], [], 0
            for m in LINK_RE.finditer(chunk):
                links.append((_label(chunk[last:m.start()]), m.group(1).strip()))
                rest.append(chunk[last:m.start()])
                last = m.end()
            rest.append(chunk[last:])
            for label, target in links:
                exits.append((label, target, marker == DO_NOTHING))
            if marker == LEADS_TO:
                continue
            leftover = "".join(rest)
            if marker is not None:
                leftover = f"**{_marker_text(line, marker)}:**{leftover}"
            kept.append(leftover)
        tidy = re.sub(r"[ \t]+([,;.]?)[ \t]*(?=\r?\n|$)", r"\1", "".join(kept)).rstrip()
        if tidy.strip() and BULLET_RE.sub("", tidy).strip(" ,;"):
            prose.append(tidy + ("\n" if line.endswith("\n") else ""))
    return exits, contests, "".join(prose)


def _is_contest_line(line):
    return any(m.group(1).strip().casefold() == CONTEST for m in MARKER_RE.finditer(line))


def _marker_text(line, marker):
    for m in MARKER_RE.finditer(line):
        if m.group(1).strip().casefold() == marker:
            return m.group(1).strip()
    return marker


def _contest(chunk):
    """`fight the Order, win → [[A]], lose → [[B]]` as
    `("fight the Order", [("win", "A"), ("lose", "B")])`."""
    results, last, label = [], 0, None
    for m in LINK_RE.finditer(chunk):
        before = chunk[last:m.start()]
        if label is None:
            cut = max(before.rfind(","), before.rfind(";"))
            label = _label(before[:cut]) if cut >= 0 else ""
            before = before[cut + 1:]
        results.append((_label(before), m.group(1).strip()))
        last = m.end()
    if label is None:
        label = _label(chunk)
    return label, results


def story(mod):
    """The story in a Mod's body, by the Dry Run convention in
    `schema/mod.md`.

    `mod` is a Mod's `Document`, or the text of its body (or of its whole file:
    frontmatter, if any, is ignored). Returns a `Story`. It never raises on
    what the body holds; what is wrong is in `story.problems` and
    `story.gaps`.
    """
    body = mod if isinstance(mod, str) else getattr(mod, "body", None)
    if not isinstance(body, str):
        raise TypeError(f"a Mod is a Document or the text of its body, not {type(mod).__name__}")
    if body.removeprefix("﻿").startswith("---"):
        from ._checks import split_frontmatter
        raw, rest = split_frontmatter(body)
        if raw is not None:
            body = rest

    sections = tuple(Section(h or "", source) for h, source, _ in _split(body, 2))
    by_heading = {}
    for heading, _source, content in _split(body, 2):
        if heading is not None:
            by_heading.setdefault(key(heading), (heading, content))

    drafts = []  # (name, heading, kind, text, exits, contests, prose)
    premise = by_heading.get(PREMISE)
    if premise is not None:
        exits, contests, prose = _parse(premise[1])
        hooks = by_heading.get(HOOKS)
        if hooks is not None:
            exits = exits + _parse(hooks[1])[0]
        drafts.append(("Premise", premise[0], START, premise[1], exits, contests, prose))
    for section, kind in ((SCENES, SCENE), (OUTCOMES, ENDING)):
        if section not in by_heading:
            continue
        for heading, _source, content in _split(by_heading[section][1], 3):
            if heading is None:
                continue
            exits, contests, prose = _parse(content)
            drafts.append((display(heading), heading, kind, content, exits, contests, prose))

    if premise is None and by_heading.get(HOOKS) is not None:
        hook_links = _parse(by_heading[HOOKS][1])[0]
    else:
        hook_links = []
    structured = bool(hook_links) or any(d[4] or d[5] for d in drafts)

    problems, gaps = [], []
    names = {}
    for d in drafts:
        names.setdefault(key(d[0]), []).append(d)
    for name_key, same in names.items():
        if len(same) > 1:
            problems.append(f"Dry Run: {len(same)} passages are headed `{same[0][0]}`, so a "
                            f"link to it is ambiguous — give each scene and outcome its own "
                            f"heading")

    def resolve(target):
        same = names.get(key(target))
        return same[0][0] if same and same[0][2] != START else None

    def where(d):
        return {START: "the Hooks", SCENE: f"scene `{d[0]}`", ENDING: f"outcome `{d[0]}`"}[d[2]]

    passages = []
    for d in drafts:
        name, heading, kind, text, exits, contests, prose = d
        made_exits = []
        for label, target, idle in exits:
            passage = resolve(target)
            if passage is None:
                problems.append(f"Dry Run: `[[{target}]]` in {where(d)} links to no scene or "
                                f"outcome — a link is the heading of a `###` under "
                                f"`## Scene Breakdown` or `## Possible Outcomes`")
            made_exits.append(Exit(label, target, passage, idle))
        made_contests = []
        for label, results in contests:
            made = []
            for result, target in results:
                passage = resolve(target)
                if passage is None:
                    problems.append(f"Dry Run: `[[{target}]]` in {where(d)} links to no "
                                    f"scene or outcome — a link is the heading of a `###` "
                                    f"under `## Scene Breakdown` or `## Possible Outcomes`")
                made.append(Exit(result, target, passage))
            if len(made) < 2:
                gaps.append(f"Dry Run: the Contest `{label}` in {where(d)} names "
                            f"{len(made) or 'no'} result{'' if len(made) == 1 else 's'} — "
                            f"give it at least a success and a failure, each "
                            f"`result → [[Where it leads]]`")
            made_contests.append(Contest(label, tuple(made)))
        passages.append(Passage(name, heading, kind, text, prose, tuple(made_exits),
                                tuple(made_contests)))

    start = next((p for p in passages if p.kind == START), None)
    if not structured:
        problems.insert(0, "Dry Run: the body has no Dry Run structure — no Hook, scene or "
                           "Contest links to a scene or outcome. See the Dry Run convention "
                           "in schema/mod.md")
    elif start is None:
        problems.insert(0, "Dry Run: there is no `## Premise` for a Dry Run to start from")
    if structured:
        gaps.extend(_gaps(start, passages))
    return Story(start, tuple(passages), sections, structured, tuple(problems), tuple(gaps))


def _gaps(start, passages):
    gaps = []
    if start is not None and not start.choices:
        gaps.append("Dry Run: the Premise leads nowhere — no Hook links to a scene "
                    "(`- how the party gets in → [[Scene]]`)")
    linked = set()
    for p in passages:
        linked.update(c.passage for c in p.choices if c.passage and c.passage != p.name)
    for p in passages:
        if p.kind != SCENE:
            continue
        if p.name not in linked:
            gaps.append(f"Dry Run: nothing links to scene `{p.name}` — link to it from a "
                        f"Hook or another scene")
        if not p.choices:
            gaps.append(f"Dry Run: scene `{p.name}` has no exits — add `**Leads to:** "
                        f"label → [[Scene or outcome]]` or a Contest, or make it an outcome "
                        f"under `## Possible Outcomes`")
    by_name = {p.name: p for p in passages}
    reached, todo = set(), [start] if start is not None else []
    while todo:
        p = todo.pop()
        if p.name in reached:
            continue
        reached.add(p.name)
        todo.extend(by_name[c.passage] for c in p.choices if c.passage in by_name)
    for p in passages:
        if p.kind == ENDING and p.name not in reached:
            gaps.append(f"Dry Run: outcome `{p.name}` can never be reached from the Premise")
    return gaps

