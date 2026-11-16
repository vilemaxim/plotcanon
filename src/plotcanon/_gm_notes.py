"""A document's text without its secret section, `## GM Notes`."""

import re

from ._checks import FM_RE
from ._story import _lines

GM_NOTES = "GM Notes"
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")


def without_gm_notes(text):
    """A document's whole text, frontmatter and body, without its
    `## GM Notes` section: the heading and everything up to the next heading
    of the same or a higher level, or the end. The heading is matched on its
    exact text, as the schema's fixed headings are, and a heading inside a
    fenced code block is not one. Everything else is left byte for byte; a
    text with no GM Notes comes back as it was."""
    bom = "﻿" if text.startswith("﻿") else ""
    m = FM_RE.match(text[len(bom):])
    start = len(bom) + (m.start(2) if m else 0)
    kept, removing = [], False
    for line, fenced in _lines(text[start:]):
        heading = None if fenced else _HEADING_RE.match(line.rstrip("\r\n"))
        if heading:
            level = len(heading.group(1))
            if removing and level <= 2:
                removing = False
            if not removing and level == 2 and heading.group(2) == GM_NOTES:
                removing = True
        if not removing:
            kept.append(line)
    return text[:start] + "".join(kept)
