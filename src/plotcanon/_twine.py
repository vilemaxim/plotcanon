"""A Mod exchanged with Twine (Twee 3), in both directions, with nothing lost.

Markdown stays a Mod's source; Twine is an exchange format, so a Mod can be
edited in Twine's map and brought back (rpg-plot-helper ADR-0007).

    passage            tag            holds
    Frontmatter        frontmatter    the YAML, exactly as written
    Premise            premise        `## Premise`, and `## Hooks` after it
    a scene            scene          a `###` under `## Scene Breakdown`
    a Contest          contest        its results, each a link
    an outcome         outcome        a `###` under `## Possible Outcomes`
    any other section  mod-section    the section, unlinked

In the story passages a link `label → [[Target]]` is written as Twine writes
one, `[[label->Target]]`, and read back the same way. A line that would not
come back exactly as written is left as it is: `[[Target]]` is a link in
Twine as well.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from html.parser import HTMLParser

import yaml

from ._checks import MAX_FILE_CHARACTERS, split_frontmatter
from ._story import (BULLET_RE, FENCE_RE, HEADING_RE, LINK_RE, MARKER_RE, CONTEST,
                     _lines, _split, display, key)

FRONTMATTER, PREMISE, SCENE, CONTEST_TAG, OUTCOME, SECTION = (
    "frontmatter", "premise", "scene", "contest", "outcome", "mod-section")
PREAMBLE = "preamble"
KINDS = (FRONTMATTER, PREMISE, SCENE, CONTEST_TAG, OUTCOME, SECTION)

# Twine's own bookkeeping passages in a Twee file. They hold no part of a Mod.
STORY_TITLE, STORY_DATA = "StoryTitle", "StoryData"
# Twee passages that are a story's JavaScript or stylesheet.
CODE_TAGS = ("script", "stylesheet")

STORY_FORMAT, STORY_FORMAT_VERSION = "Harlowe", "3.3.9"

# A Twine file larger than this is refused unread. A published story carries
# its story format's code, which is about a megabyte at most; a Mod's own
# passages are a few thousand characters.
MAX_TWINE_CHARACTERS = 5_000_000
MAX_PASSAGES = 1_000
# The markdown a Twine file may come to. A Mod's file larger than this is
# refused by the validator anyway (`MAX_FILE_CHARACTERS`).
MAX_MARKDOWN_CHARACTERS = MAX_FILE_CHARACTERS
# Past this many warnings, the rest are counted, not listed.
MAX_WARNINGS = 50

SCENES_KEY, OUTCOMES_KEY, PREMISE_KEY, HOOKS_KEY = (
    "scene breakdown", "possible outcomes", "premise", "hooks")

# `[[label->Target]]`, `[[Target<-label]]`, `[[label|Target]]` and `[[Target]]`.
TWINE_LINK_RE = re.compile(r"\[\[([^\[\]\n]*)\]\]")
SUFFIX_RE = re.compile(r" \(\d+\)$")


@dataclass(frozen=True)
class FromTwine:
    """A Twine file read back into a Mod.

    `markdown` is the Mod's file, to validate like any other (with
    `check_file`); it is "" when the file could not be read at all, and then
    `problems` says why, one sentence each. `warnings` name what was kept as
    text but does nothing in a Dry Run, and anything else a person should
    look at. Messages start `Twine: ` and are ready to paste into an LLM.
    """

    markdown: str
    warnings: tuple = ()
    problems: tuple = ()

    @property
    def ok(self):
        return not self.problems


@dataclass
class _Passage:
    name: str
    tags: list
    text: str


# --- markdown to Twee ------------------------------------------------------


def to_twee(mod):
    """A Mod's file (its whole text, frontmatter included) as a Twee 3 story,
    to open in Twine. `from_twine` turns the result back into the same text.
    Never raises on what the text holds; raises `TypeError` for anything that
    is not a `str`."""
    if not isinstance(mod, str):
        raise TypeError(f"a Mod is the text of its file, not {type(mod).__name__}")
    text = mod.removeprefix("\ufeff").replace("\r\n", "\n")
    raw, body = split_frontmatter(text)
    passages = _Names()
    if raw is not None:
        passages.add("Frontmatter", [FRONTMATTER], raw)
    else:
        body = text

    parts = _split(body, 2)
    i = 0
    while i < len(parts):
        heading, source, content = parts[i]
        if heading is None:
            if content.strip():
                passages.add("Before the first heading", [SECTION, PREAMBLE], _trim(content))
            i += 1
            continue
        line = source[:len(source) - len(content)]
        k = key(heading)
        if k == PREMISE_KEY and not passages.has_kind(PREMISE):
            text_ = _trim(content)
            if i + 1 < len(parts) and parts[i + 1][0] is not None \
                    and key(parts[i + 1][0]) == HOOKS_KEY:
                text_ = _join(text_, _trim(parts[i + 1][1]))
                i += 1
            passages.add("Premise", [PREMISE], text_, line, story=True)
        elif k in (SCENES_KEY, OUTCOMES_KEY) and k not in passages.containers:
            tag = SCENE if k == SCENES_KEY else OUTCOME
            subs = _split(content, 3)
            intro = subs[0][2] if subs and subs[0][0] is None else ""
            passages.containers.add(k)
            passages.add(_name(heading), [SECTION], _trim(intro), line)
            for sub_heading, sub_source, sub_content in subs:
                if sub_heading is not None:
                    sub_line = sub_source[:len(sub_source) - len(sub_content)]
                    passages.add(display(sub_heading) or "Untitled", [tag], _trim(sub_content),
                                 sub_line, story=True)
        else:
            passages.add(_name(heading), [SECTION], _trim(content), line)
        i += 1
    return _write_twee(_title(raw), _ifid(raw, text), passages.list)


class _Names:
    """The passages being written, each with a name no other has."""

    def __init__(self):
        self.list, self.taken, self.containers, self.counts = [], set(), set(), {}

    def unique(self, name):
        candidate, n = name, self.counts.get(name.casefold(), 1)
        while candidate.casefold() in self.taken or candidate in (STORY_TITLE, STORY_DATA):
            n += 1
            candidate = f"{name} ({n})"
        self.counts[name.casefold()] = n
        self.taken.add(candidate.casefold())
        return candidate

    def add(self, name, tags, text, line=None, story=False):
        """A passage. `line` is the heading line it was under, kept in its text
        when the passage's name cannot stand for it. A premise, scene or
        outcome (`story`) has its links written as Twine's, and each of its
        Contests becomes a passage of its own, after it."""
        p = _Passage(self.unique(name), tags, "")
        self.list.append(p)
        if line is not None:
            text = _join(_head_if_needed(line, 3 if tags[0] in (SCENE, OUTCOME) else 2,
                                         p.name), text)
        if story:
            text = _links_to_twine(text, lambda label, results: self.add(
                f"{p.name}: {label}", [CONTEST_TAG], results).name)
        p.text = text
        return p

    def has_kind(self, tag):
        return any(tag in p.tags for p in self.list)



# What a label or a target may not hold to be written in a Twine link.
NOT_IN_LABEL = ("[", "]", "|", "->", "<-")


def _links_to_twine(text, add_contest):
    """Each `label → [[Target]]` as `[[label->Target]]`, and each Contest as
    a link to a passage holding its results. A part of a line that would not
    come back exactly as written is left alone."""
    out, fenced = [], False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            fenced = not fenced
            out.append(line)
            continue
        out.append(line if fenced else _line_to_twine(line, add_contest))
    return "\n".join(out)


def _line_to_twine(line, add_contest):
    if "[[" not in line:
        return line
    marks = list(MARKER_RE.finditer(line))
    pieces = [line[:marks[0].start()] if marks else line]
    for n, m in enumerate(marks):
        end = marks[n + 1].start() if n + 1 < len(marks) else len(line)
        pieces.append((m, line[m.end():end]))
    out = [_chunk_to_twine(pieces[0], first=True)]
    for m, chunk in pieces[1:]:
        out.append(m.group(0))
        if m.group(1).strip().casefold() == CONTEST:
            out.append(_contest_to_twine(chunk, add_contest))
        else:
            out.append(_chunk_to_twine(chunk))
    return "".join(out)


def _chunk_to_twine(chunk, first=False):
    out, last = [], 0
    for m in LINK_RE.finditer(chunk):
        region = chunk[last:m.start()]
        lead = (BULLET_RE.match(region) if first and last == 0 else None) \
            or re.match(r"[ \t]*[;,]?[ \t]*", region)
        label, target = region[lead.end():].rstrip(), m.group(1)
        if label and not any(c in label or c in target for c in NOT_IN_LABEL):
            out.append(f"{region[:lead.end()]}[[{label}->{target}]]")
        else:
            out.append(region + m.group(0))
        last = m.end()
    out.append(chunk[last:])
    made = "".join(out)
    return made if _links_to_markdown(made, {}) == chunk else chunk


def _contest_to_twine(chunk, add_contest):
    """` fight, win → [[A]], lose → [[B]]` as ` [[fight->Contest]]`, with a
    passage `Contest` holding `[[win->A]], [[lose->B]]`."""
    m = LINK_RE.search(chunk)
    if m is None:
        return chunk
    before = chunk[:m.start()]
    cut = max(before.rfind(","), before.rfind(";"))
    lead = re.match(r"[ \t]*", chunk).end()
    label = chunk[lead:cut].strip() if cut >= 0 else ""
    results = chunk[cut + 1:].strip()
    trail = chunk[len(chunk.rstrip()):]
    twine_results = _chunk_to_twine(results)
    if not label or any(c in label for c in NOT_IN_LABEL) or \
            chunk[:lead] + _contest_text(label, twine_results) + trail != chunk:
        return chunk
    return f"{chunk[:lead]}[[{label}->{add_contest(label, twine_results)}]]{trail}"


def _contest_text(label, results):
    """A Contest's label and its passage's text as the markdown they stand
    for: `fight, win → [[A]], lose → [[B]]`."""
    lines = [line.strip() for line in results.split("\n") if line.strip()]
    return f"{label}, " + _links_to_markdown(", ".join(lines), {})


def _links_to_markdown(text, contests, warn=None):
    """Each Twine link `[[label->Target]]` (or `[[Target<-label]]` or
    `[[label|Target]]`) as `label → [[Target]]`, and a link to a Contest's
    passage as the Contest. `contests` is `{name: passage text}`."""
    out, fenced = [], False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            fenced = not fenced
            out.append(line)
            continue
        out.append(line if fenced else _line_to_markdown(line, contests, warn))
    return "\n".join(out)


def _line_to_markdown(line, contests, warn):
    out, last = [], 0
    for m in TWINE_LINK_RE.finditer(line):
        inner = m.group(1)
        if "->" in inner:
            label, target = inner.rsplit("->", 1)
        elif "<-" in inner:
            target, label = inner.split("<-", 1)
        elif "|" in inner:
            label, target = inner.split("|", 1)
        else:
            if warn and not re.search(r"(?:→|->)[ \t]*$", line[:m.start()]):
                warn(inner)
            continue
        label, target = label.strip(), target.strip()
        out.append(line[last:m.start()])
        if target in contests:
            if not re.search(r"\*\*[ \t]*Contest[ \t]*:\*\*", line[:m.start()], re.I):
                out.append("**Contest:** ")
            out.append(_contest_text(label, contests[target]))
        else:
            out.append(f"{label} → [[{target}]]" if label else f"→ [[{target}]]")
        last = m.end()
    out.append(line[last:])
    return "".join(out)


def _name(heading):
    return heading.strip() or "Untitled"


def _head_if_needed(line, level, name):
    """The heading line as written, when it is not just `## name`: the
    passage's name cannot carry it."""
    line = line.rstrip("\n")
    return "" if line == "#" * level + " " + name else line


def _trim(text):
    """Text without the blank lines around it or the spaces at its end."""
    lines = text.rstrip().split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines)


def _join(*parts):
    return "\n\n".join(p for p in parts if p)


def _title(raw):
    found = _field(raw, "title")
    return found if found else "Untitled Mod"


def _field(raw, name):
    """One top-level text field of the frontmatter, read from its own line,
    or None. The rest of the YAML is not parsed."""
    if raw is None:
        return None
    m = re.search(rf"^{name}:[ \t]*(.+)$", raw, re.M)
    if not m:
        return None
    try:
        value = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return " ".join(value.split()) if isinstance(value, str) and value.strip() else None


def _ifid(raw, text):
    seed = _field(raw, "id") or text
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "plotcanon:mod:" + seed)).upper()


def _escape_name(name):
    return re.sub(r"([\\\[\]{}])", r"\\\1", name)


def _write_twee(title, ifid, passages):
    data = {"ifid": ifid, "format": STORY_FORMAT, "format-version": STORY_FORMAT_VERSION,
            "start": "Premise" if any(PREMISE in p.tags for p in passages) else
            (passages[0].name if passages else ""), "zoom": 1}
    out = [f":: {STORY_TITLE}\n{title}\n", f":: {STORY_DATA}\n{json.dumps(data, indent=2)}\n"]
    for n, p in enumerate(passages):
        meta = json.dumps({"position": _position(p, n), "size": "100,100"},
                          separators=(",", ":"))
        head = f":: {_escape_name(p.name)} [{' '.join(p.tags)}] {meta}"
        body = re.sub(r"^::", r"\\::", p.text, flags=re.M)
        out.append(f"{head}\n{body}\n")
    return "\n".join(out)


def _position(p, n):
    return f"{100 + 150 * (n % 8)},{100 + 150 * (n // 8)}"


# --- Twine to markdown -----------------------------------------------------


def from_twine(source):
    """A Twee 3 file or a Twine 2 `.html` file (an archive or a published
    story) read back into a Mod's markdown, as `FromTwine`.

    `source` is the file's text or its bytes (UTF-8). A file holding a
    `<tw-storydata>` element is read as Twine 2 HTML; anything else as Twee.
    Never raises on what the file holds: what is wrong with it is in
    `problems`, and what was kept but does nothing in a Dry Run is in
    `warnings`. Raises `TypeError` for anything but `str` or `bytes`."""
    if isinstance(source, (bytes, bytearray)):
        if len(source) > MAX_TWINE_CHARACTERS:
            return _refused(f"the file is larger than {MAX_TWINE_CHARACTERS:,} bytes, which "
                            f"is more than a Mod needs")
        try:
            source = bytes(source).decode("utf-8-sig")
        except UnicodeDecodeError:
            return _refused("the file is not UTF-8 text")
    elif not isinstance(source, str):
        raise TypeError(f"a Twine file is text or bytes, not {type(source).__name__}")
    if len(source) > MAX_TWINE_CHARACTERS:
        return _refused(f"the file is larger than {MAX_TWINE_CHARACTERS:,} characters, which "
                        f"is more than a Mod needs")
    source = source.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    warnings = _Warnings()
    if re.search(r"<tw-storydata\b", source, re.I):
        passages, problem = _read_html(source, warnings)
    elif source.lstrip().startswith("<"):
        return _refused("the file is HTML but holds no Twine 2 story (no `<tw-storydata>`); "
                        "publish or archive the story from Twine 2, or export it as Twee")
    else:
        passages, problem = _read_twee(source, warnings)
    if problem:
        return _refused(problem)
    if len(passages) > MAX_PASSAGES:
        return _refused(f"the story has more than {MAX_PASSAGES:,} passages, which is more "
                        f"than a Mod needs")
    try:
        markdown = _markdown(passages, warnings)
    except _TooLarge:
        return _refused(f"the Mod written out would be larger than "
                        f"{MAX_MARKDOWN_CHARACTERS:,} characters, which is more than a Mod "
                        f"needs")
    except Exception as e:  # never hand the caller an exception for a file
        return _refused(f"the file could not be converted ({type(e).__name__}); this is a "
                        f"fault in plotcanon, not in the file")
    if len(markdown) > MAX_MARKDOWN_CHARACTERS:
        return _refused(f"the Mod written out would be larger than "
                        f"{MAX_MARKDOWN_CHARACTERS:,} characters, which is more than a Mod "
                        f"needs")
    return FromTwine(markdown, warnings.result())


class _TooLarge(Exception):
    pass


def _refused(why):
    return FromTwine("", (), (f"Twine: {why}",))


class _Warnings:
    def __init__(self):
        self.items, self.seen = [], set()

    def add(self, message):
        message = f"Twine: {message}"
        if message not in self.seen:
            self.seen.add(message)
            self.items.append(message)

    def result(self):
        if len(self.items) <= MAX_WARNINGS:
            return tuple(self.items)
        rest = len(self.items) - MAX_WARNINGS
        return tuple(self.items[:MAX_WARNINGS]) + (f"Twine: and {rest} more warnings",)


def _read_twee(text, warnings):
    passages, current, lines, before = [], None, [], []
    for line in text.split("\n"):
        if line.startswith("::"):
            if current is not None:
                current.text = "\n".join(lines)
                passages.append(current)
            current, lines = _header(line[2:]), []
        elif current is None:
            before.append(line)
        else:
            lines.append(line[1:] if line.startswith("\\::") else line)
    if current is not None:
        current.text = "\n".join(lines)
        passages.append(current)
    if not passages:
        return [], ("the file holds no passages: a Twee file is passages, each starting "
                    "with a `:: Name [tags]` line")
    if any(line.strip() for line in before):
        warnings.add("the text before the first passage is not part of any passage, "
                     "so it is not kept")
    kept = []
    for p in passages:
        if p.name in (STORY_TITLE, STORY_DATA) and not p.tags:
            continue
        kept.append(p)
    return kept, None


def _header(rest):
    """`Name [tags] {metadata}`, with `\\` escaping a character in the name
    and tags."""
    name, tags, i, n = [], [], 0, len(rest)
    while i < n and rest[i] not in "[{":
        if rest[i] == "\\" and i + 1 < n:
            i += 1
        name.append(rest[i])
        i += 1
    if i < n and rest[i] == "[":
        i += 1
        tag = []
        while i < n and rest[i] != "]":
            if rest[i] == "\\" and i + 1 < n:
                i += 1
            tag.append(rest[i])
            i += 1
        tags = "".join(tag).split()
    return _Passage("".join(name).strip(), tags, "")


class _StoryParser(HTMLParser):
    """The `<tw-storydata>` elements of a Twine 2 file and the passages,
    script and stylesheet in each."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stories, self.current, self.capture = [], None, None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tw-storydata":
            self.current = {"passages": [], "script": [], "stylesheet": []}
            self.stories.append(self.current)
        elif self.current is None:
            return
        elif tag == "tw-passagedata":
            p = _Passage((attrs.get("name") or "").strip(), (attrs.get("tags") or "").split(), "")
            self.current["passages"].append(p)
            self.capture = p
        elif tag == "script":
            self.capture = "script"
        elif tag == "style":
            self.capture = "stylesheet"

    def handle_endtag(self, tag):
        if tag == "tw-storydata":
            self.current = None
        if tag in ("tw-passagedata", "script", "style"):
            self.capture = None

    def handle_data(self, data):
        if self.current is None or self.capture is None:
            return
        if isinstance(self.capture, _Passage):
            self.capture.text += data
        else:
            self.current[self.capture].append(data)


def _read_html(text, warnings):
    parser = _StoryParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception:  # html.parser is lenient; this is for what it is not.
        return [], "the HTML could not be read"
    if len(parser.stories) != 1:
        return [], (f"the file holds {len(parser.stories)} Twine stories; a Mod is one — "
                    f"publish or archive just that story")
    story = parser.stories[0]
    for kind in CODE_TAGS:
        if "".join(story[kind]).strip():
            warnings.add(f"the story's {'JavaScript' if kind == 'script' else 'stylesheet'} "
                         f"is not part of a Mod, so it is not kept")
    return story["passages"], None


def _markdown(passages, warnings):
    """The Mod's markdown, from passages in the order the file has them."""
    frontmatter, preamble, blocks = None, [], []
    for p in passages:
        p.text = _trim(p.text)
        if not p.name:
            p.name = "Untitled"
    kinds = [(p, _kind(p, warnings)) for p in passages]
    contests = {p.name: p.text for p, kind in kinds if kind == CONTEST_TAG}
    used = set()

    class Seen(dict):
        """The Contests, each counted as it is written out, so that a Contest
        linked over and over cannot make the markdown huge."""
        written = sum(len(p.text) for p in passages)

        def __contains__(self, name):
            found = dict.__contains__(self, name)
            if found:
                used.add(name)
            return found

        def __getitem__(self, name):
            text = dict.__getitem__(self, name)
            Seen.written += len(text)
            if Seen.written > MAX_MARKDOWN_CHARACTERS:
                raise _TooLarge
            return text

    seen = Seen(contests)
    for p, kind in kinds:
        if kind in (PREMISE, SCENE, OUTCOME):
            p.text = _links_to_markdown(p.text, seen, lambda target, p=p: warnings.add(
                f"`[[{target}]]` in passage `{p.name}` has no label, so a Dry Run does not "
                f"follow it — write it `[[what the players do->{target}]]`"))
    under = {SCENE: [], OUTCOME: []}
    for p, kind in kinds:
        if kind in under:
            under[kind].append(p)
    # Where each container section goes: at its own passage, or else where
    # the first passage that belongs under it is.
    containers = {}
    for p, kind in kinds:
        if kind == SECTION and key(SUFFIX_RE.sub("", p.name)) in (SCENES_KEY, OUTCOMES_KEY):
            containers.setdefault(key(SUFFIX_RE.sub("", p.name)), p)
    placed = set()

    def container(k, p=None):
        placed.add(k)
        tag = SCENE if k == SCENES_KEY else OUTCOME
        if p is None:
            head = "## Scene Breakdown" if k == SCENES_KEY else "## Possible Outcomes"
        else:
            head = _block(p, 2, warnings)
        return _join(head, *(_block(s, 3, warnings) for s in under[tag]))

    for p, kind in kinds:
        if kind == FRONTMATTER:
            if frontmatter is None:
                frontmatter = p.text
                continue
            warnings.add(f"only the first passage tagged `frontmatter` is the frontmatter; "
                         f"`{p.name}` is kept as a section")
            kind = SECTION
        if kind == PREAMBLE:
            preamble.append(p.text)
        elif kind == CONTEST_TAG:
            if p.name not in used:
                warnings.add(f"no passage links to the Contest `{p.name}`, so it is kept as a "
                             f"section of its own")
                blocks.append(_block(_Passage(p.name, [], _links_to_markdown(p.text, {})), 2))
        elif kind in (SCENE, OUTCOME):
            k = SCENES_KEY if kind == SCENE else OUTCOMES_KEY
            if k not in placed and k not in containers:
                blocks.append(container(k))
        elif kind == SECTION and containers.get(key(SUFFIX_RE.sub("", p.name))) is p:
            blocks.append(container(key(SUFFIX_RE.sub("", p.name)), p))
        else:
            blocks.append(_block(p, 2, warnings))
    out = []
    if frontmatter is not None:
        out.append(f"---\n{frontmatter}\n---\n")
    else:
        warnings.add("no passage is tagged `frontmatter`, so the Mod has no frontmatter")
    body = "\n\n".join(preamble + blocks)
    if body:
        out.append(("\n" if frontmatter is not None else "") + body + "\n")
    return "".join(out)


def _kind(p, warnings):
    """What a passage is, by its tags. A passage with none is a scene."""
    tags = p.tags
    for tag in tags:
        if tag not in KINDS and tag != PREAMBLE:
            warnings.add(f"passage `{p.name}` has the tag `{tag}`, which a Mod has no place "
                         f"for, so it is not kept")
    if FRONTMATTER not in tags:
        _twine_code(p, warnings)
    if PREAMBLE in tags:
        return PREAMBLE
    for kind in KINDS:
        if kind in tags:
            return kind
    return SCENE


# Harlowe's macros, as `(name:`. Only these names count, so that prose such
# as "(Note: ...)" is not taken for one.
HARLOWE_MACROS = frozenset("""
a after align alert append append-with array background before border box button
change checkbox click click-append click-goto click-prepend click-replace colour color
confirm count cond css cycling-link datamap dataset dialog display dm dropdown ds either
else else-if elseif enchant enchant-in event font for force-input go-to goto hidden hide
history hook hover-style if input link link-goto link-repeat link-rerun link-reveal
link-reveal-goto link-show link-undo live load-game loop meter mouseover move nth num
number opacity prepend print prompt put random range redirect reload replace rerun
restart save-game seq-link set show sidebar size str string stop t8n text-colour
text-color text-indent text-rotate text-size text-style transition undo unless v6m
verbatim visited
""".split())

TWINE_CODE = (
    ("macro", re.compile(r"<<[^<>\n]*>>|\(([A-Za-z][\w-]*):")),
    ("variable", re.compile(r"(?<![\w$])\$[A-Za-z_]\w*")),
    ("HTML tag", re.compile(r"(?<!<)</?[A-Za-z][\w-]*(?:\s[^<>\n]*)?/?>")),
    ("styling", re.compile(r"@@[^@\n]*@@|\|[A-Za-z_]\w*>\[|\]<[A-Za-z_]\w*\|")),
)


def _twine_code(p, warnings):
    """Warn about Twine code in a passage: it is kept as text, and a Dry Run
    does nothing with it."""
    for kind, pattern in TWINE_CODE:
        for line, fenced in _lines(p.text):
            if fenced:
                continue
            found = next((m for m in pattern.finditer(line) if kind != "macro"
                          or m.group(1) is None or m.group(1).casefold() in HARLOWE_MACROS),
                         None)
            if found:
                warnings.add(f"passage `{p.name}` has a Twine {kind} "
                             f"(`{found.group(0)[:60]}`), which is kept as text but does "
                             f"nothing in a Dry Run")
                break


def _block(p, level, warnings=None):
    """A passage as a markdown section: its heading, then its text."""
    first, _, rest = p.text.partition("\n")
    m = HEADING_RE.match(first)
    if m and len(m.group(1)) == level and _same(m.group(2), p.name):
        head, text = first, _trim(rest)
    else:
        head, text = "#" * level + " " + p.name, p.text
    if warnings is not None:
        _stray_headings(p, level, text, warnings)
    return _join(head, text)


def _stray_headings(p, level, text, warnings):
    """Warn about a heading in a passage's text that starts a section, scene
    or outcome of its own in the markdown."""
    for line, fenced in _lines(text):
        m = None if fenced else HEADING_RE.match(line.rstrip("\n"))
        if m is None or len(m.group(1)) > level:
            continue
        if PREMISE in p.tags and len(m.group(1)) == 2 and key(m.group(2)) == HOOKS_KEY:
            continue
        what = "section" if len(m.group(1)) == 2 else "scene or outcome"
        warnings.add(f"passage `{p.name}` has the heading `{line.strip()}` in its text, "
                     f"which starts a new {what} in the Mod")


def _same(heading, name):
    """Whether a heading is the one a passage was named after: the name may
    have lost a number prefix, and gained ` (2)` to tell it from another."""
    return key(heading or "Untitled") == key(SUFFIX_RE.sub("", name))
