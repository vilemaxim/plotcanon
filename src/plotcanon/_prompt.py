"""What the instructions for an LLM share, whether for an Interview or for
one of the plot team's reports: the surfaces, a file in a code block, a file's
`id`, the World as given to the LLM, and the player agency questions."""

from __future__ import annotations

import re

from . import _checks

SURFACES = ("web", "cli")


def check_surface(surface, what):
    """Raise ValueError when `surface` is not one of SURFACES. `what` names
    the instructions, such as "an Interview"."""
    if surface not in SURFACES:
        raise ValueError(f"{what}'s surface is one of {', '.join(SURFACES)}, "
                         f"not {surface!r}")


AGENCY_QUESTIONS = """\
1. Can the players fail, and is failure interesting? One outcome is a cutscene.
2. Is there more than one way in? Two or three hooks, not one.
3. Does the outcome turn on player choices, or is it decided in the writeup?
4. Are the PCs the protagonists, or the audience for something NPCs are doing?
5. Does anything remove player control: capture, compulsion, forced loss? If
   so, is it bounded, brief, and flagged for a safety brief?
6. Is engagement gated on one build, skill, or item that only one player has?
7. Does it need a specific player to turn up? What happens if they do not?
8. Does it invalidate something a player already earned or established in
   play? Flag this every time: it is the one that does lasting damage.
9. Is any NPC unbeatable by fiat? If so, can players tell before they commit?
10. Does it need a content brief or an opt-out?
"""


def fenced(text, info=""):
    """`text` in a code block whose fence no run of backticks in it can close."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{info}\n{text.rstrip(chr(10))}\n{fence}\n"


def _name(fields, doc_id):
    aliases = fields.get("aliases")
    for value in (fields.get("title"), *(aliases[:1] if isinstance(aliases, list) else ())):
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return doc_id


def readable(world, intro, *, leave_out=()):
    """A section of instructions giving the World: `intro`, an index of
    slugs, then each document's file exactly as given. Documents whose `id`
    is in `leave_out` are not given."""
    from ._api import _files_of

    files = {path: text for path, text in _files_of(world).items()
             if _checks.is_scanned(path)}
    docs, _by_id, _generated = _checks.collect_docs(files, _checks.Findings())
    left_out = {d.rel for d in docs if d.id in leave_out}
    docs = [d for d in docs if d.rel not in left_out]
    index = [f"| `{d.id}` | {d.type} | {_name(d.fm, d.id).replace('|', '/')} |"
             for d in docs if isinstance(d.id, str)]
    parts = [intro]
    if index:
        parts.append("| Slug | Type | Name |\n|---|---|---|\n" + "\n".join(index) + "\n")
    else:
        parts.append("There are none.\n")
    for path in sorted(set(files) - left_out, key=_checks.scan_order):
        parts.append(f"### {path}\n\n" + fenced(files[path], "markdown"))
    return "\n".join(parts)


def front(text, what):
    """The `id` in a file's frontmatter, and its fields. Raises ValueError
    when there is no `id` to read, and TypeError when `text` is not text."""
    if not isinstance(text, str):
        raise TypeError(f"{what} is the text of its file, not {type(text).__name__}")
    raw, _body = _checks.split_frontmatter(text)
    try:
        fields = None if raw is None else _checks.yaml.load(raw, Loader=_checks.Loader)  # noqa: S506
    except Exception:  # noqa: BLE001 - any YAML that cannot be read
        fields = None
    doc_id = fields.get("id") if isinstance(fields, dict) else None
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError(f"{what} has no `id` in its frontmatter")
    return doc_id.strip(), fields


def draft_id(draft, what="the draft"):
    """The `id` in a draft's frontmatter. Raises ValueError when there is
    none to read."""
    return front(draft, what)[0]
