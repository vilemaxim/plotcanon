"""The words not to use, and what to say instead.

Both projects share one vocabulary: the glossary in the rpg-plot-helper repo
(GLOSSARY.md). Each term there lists words to avoid for it. This is that list
in a form a test can use, so that docs, prompts and messages can be checked.
Nothing reads the glossary itself, so keep this in step with it by hand.

It holds only words that are safe to search for. Some avoided words have an
ordinary meaning that is fine ("character" in "character sheet", "update",
"group", "conflict", "owner", "account"), and those are left to a reader.
"""

import re

# A pattern for a word to avoid, and the term to use for that idea instead.
# A space in a pattern stands for any run of spaces, line breaks or hyphens,
# so a phrase is still found when it wraps onto the next line.
AVOID = {
    "plot leads?": "Plot Master",
    "canon keepers?": "Plot Master",
    "authors?": "Mod Writer",
    "plot writers?": "Mod Writer",
    "aars?": "After-Action Report",
    "mod reports?": "After-Action Report",
    "arcs?": "Plot",
    "storylines?": "Plot",
    "threads?": "Plot",
    "adventures?": "Mod",
    "modules?": "Mod",
    "sessions?": "Event",
    "games?": "Event or Campaign",
    "chronicles?": "Campaign",
    "downtime": "Interlude",
    "between-games?": "Interlude",
    "deltas?": "Canon Change",
    r"(?:your|the|this|our) setting(?:'s)?": "World",
    "setting-specific": "World",
    "universes?": "World",
    "tenants?": "Organization",
    "superusers?": "Organization Admin",
}


# Phrases in which a word above is being used in its ordinary sense.
ORDINARY = re.compile(r"role-playing[\s-]+games?|games?[\s-]+masters?", re.I)


def find_avoided(text):
    """Each use in `text` of a word to avoid, in the order they appear, as
    `(where it starts, the word as written, the term to use instead)`."""
    ordinary = [match.span() for match in ORDINARY.finditer(text)]
    found = []
    for pattern, use in AVOID.items():
        pattern = pattern.replace(" ", r"[\s-]+")
        for match in re.finditer(rf"(?<![\w-])(?:{pattern})(?![\w-])", text, re.I):
            if any(start <= match.start() < end for start, end in ordinary):
                continue
            found.append((match.start(), " ".join(match.group(0).split()), use))
    return sorted(found)


def avoided_words(text):
    """Every use in `text` of a word the glossary says to avoid, each as a
    string naming the word and the term to use instead, in the order they
    appear. Empty if there are none.

    Whole words only, in any capitalisation. A phrase is found even when it
    wraps onto another line. A word that is part of a hyphenated one, such as
    "session-wide", is not counted.
    """
    return [f"{word!r} (use {use})" for _start, word, use in find_avoided(text)]
