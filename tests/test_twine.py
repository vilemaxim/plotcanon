"""A Mod exchanged with Twine: `to_twee` writes a Mod as a Twee 3 story, and
`from_twine` reads a Twee file or a Twine 2 `.html` file back into a Mod's
markdown, with warnings about what does nothing in a Dry Run.
"""

import html
import re
import time
import unittest
from pathlib import Path

import plotcanon

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def sample_mods():
    return {path: text for path, text in plotcanon.sample_world().items()
            if path.startswith(("mods/", "inbox/"))}


FRONT = """\
---
id: odd-one
type: mod
title: "Odd: [one] {two}"
---
"""

# Everything a body may hold that the plain sample Mods do not.
ODD_BODY = """
Text before any heading.

## Premise ##

Starts here.
:: not a passage header

## Scene Breakdown

### 1. Arrival

**Find:** a fence.
**Leads to:** typed arrow -> [[Gate]]; → [[2. Gate]]; a|pipe → [[Gate]];  spaced  →  [[ Gate ]]
**Contest:** climb it; up → [[Gate]], down → [[Arrival]]
**Contest:** no label → [[Gate]]
plain [[Gate]] with no arrow

```
**Leads to:** in code → [[Gate]]
```

### Gate

**Leads to:** back → [[Arrival]] (and some trailing words)
**If players do nothing:** waits → [[Done]]

## Hooks

- Not after the Premise → [[Arrival]]

## Rewards

Twice.

## Rewards

Two sections with one heading.

### A subheading inside a section

Kept.

## Possible Outcomes

### Done

Over.
"""


class RoundTrip(unittest.TestCase):
    def assertComesBack(self, text):
        back = plotcanon.from_twine(plotcanon.to_twee(text))
        self.assertEqual(back.markdown, text)
        self.assertEqual(back.problems, ())

    def test_the_example_mod_comes_back_as_the_same_file(self):
        self.assertComesBack((EXAMPLES / "mods/greymoor/the-ashen-vigil.md").read_text())

    def test_the_example_in_the_mod_schema_comes_back_as_the_same_file(self):
        schema = plotcanon.schema_files()["mod.md"]
        example = schema.split("```markdown\n", 1)[1].split("\n```\n")[0] + "\n"
        self.assertComesBack(example)

    def test_a_body_with_every_oddity_comes_back_as_the_same_file(self):
        self.assertComesBack(FRONT + ODD_BODY)

    def test_a_mod_with_no_frontmatter_comes_back_without_one(self):
        self.assertComesBack(ODD_BODY.lstrip("\n"))

    def test_every_sample_mod_comes_back_as_the_same_file(self):
        for path, text in sample_mods().items():
            with self.subTest(path):
                back = plotcanon.from_twine(plotcanon.to_twee(text))

                self.assertEqual(back.markdown, text)
                self.assertEqual(back.problems, ())


BELL = "mods/lanternlight/the-bell-beneath.md"


def passages(twee):
    """`{name: (tags, text)}` of a Twee file, read plainly."""
    found, name = {}, None
    for line in twee.split("\n"):
        if line.startswith(":: "):
            head = line[3:]
            name = head.split(" [")[0].split(" {")[0]
            tags = head.split(" [", 1)[1].split("]")[0].split() if " [" in head else []
            found[name] = (tags, [])
        elif name is not None:
            found[name][1].append(line)
    return {n: (tags, "\n".join(lines).strip()) for n, (tags, lines) in found.items()}


class ToTwee(unittest.TestCase):
    def setUp(self):
        self.twee = plotcanon.to_twee(plotcanon.sample_world()[BELL])
        self.passages = passages(self.twee)

    def test_the_story_passages_are_tagged_by_kind(self):
        tags = {name: t for name, (t, _) in self.passages.items()}

        self.assertEqual(tags["Premise"], ["premise"])
        self.assertEqual(tags["The descent"], ["scene"])
        self.assertEqual(tags["The bell is rung"], ["outcome"])
        self.assertEqual(tags["NPC Casting"], ["mod-section"])
        self.assertEqual(tags["Frontmatter"], ["frontmatter"])

    def test_the_frontmatter_passage_holds_the_yaml_as_written(self):
        text = self.passages["Frontmatter"][1]

        self.assertTrue(text.startswith("id: the-bell-beneath\ntype: mod\n"))
        self.assertIn("features:\n  npcs: [sister-ane, the-tidemother]\n", text)

    def test_hooks_and_exits_are_twine_links(self):
        premise = self.passages["Premise"][1]
        descent = self.passages["The descent"][1]

        self.assertIn("- [[The sister asks them to close what was opened->The descent]]",
                      premise)
        self.assertIn("**Leads to:** [[down the rope->The bell]]", descent)
        self.assertIn("**If players do nothing:** [[the tide gives them an hour, then the "
                      "steps flood->The crypt floods]]", descent)
        self.assertIn("**Leads to:** [[cut it down->The bell is taken]]; [[follow the sound "
                      "inward->Who rings it]]", self.passages["The bell"][1])

    def test_a_contest_is_its_own_passage_whose_links_are_its_results(self):
        [(name, (tags, text))] = [(n, v) for n, v in self.passages.items()
                                  if v[0] == ["contest"]]

        self.assertEqual(text, "[[win->The bell is silenced]], [[lose->The bell is rung]]")
        self.assertIn(f"**Contest:** [[stop her before the last stroke->{name}]]",
                      self.passages["Who rings it"][1])

    def test_twine_starts_at_the_premise(self):
        self.assertIn('"start": "Premise"', self.twee)
        self.assertIn(":: StoryTitle\nThe Bell Beneath\n", self.twee)


def archive(twee, script="", stylesheet=""):
    """A Twee story as Twine 2 writes it to its archive: one `<tw-storydata>`
    whose passages are `<tw-passagedata>` elements with escaped text."""
    found = passages(twee)
    rows = []
    for pid, (name, (tags, text)) in enumerate(
            ((n, v) for n, v in found.items() if n not in ("StoryTitle", "StoryData")), 1):
        rows.append(f'<tw-passagedata pid="{pid}" name="{html.escape(name)}" '
                    f'tags="{" ".join(tags)}" position="{100 * pid},100" size="100,100">'
                    f'{html.escape(text, quote=False)}</tw-passagedata>')
    return ('<tw-storydata name="The Bell Beneath" startnode="2" creator="Twine" '
            'creator-version="2.10.0" format="Harlowe" format-version="3.3.9" '
            'ifid="2D3D4C1E-6A43-4B8F-9E3B-0E6F1D9C2A11" options="" tags="" zoom="1" hidden>'
            '<style role="stylesheet" id="twine-user-stylesheet" type="text/twine-css">'
            f'{stylesheet}</style>'
            '<script role="script" id="twine-user-script" type="text/twine-javascript">'
            f'{script}</script>' + "".join(rows) + '</tw-storydata>')


def published(twee):
    """The story published to a playable page: the archive inside an HTML
    page with the story format's code, which has markup of its own in it."""
    engine = ('var t = "<tw-storydata name=\\"Fake\\"><tw-passagedata name=\\"Fake\\">'
              'nothing</tw-passagedata></tw-storydata>"; if (a < b && c > d) {}')
    return ('<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n'
            '<title>The Bell Beneath</title>\n<style title="Twine CSS">tw-story{}</style>\n'
            '</head>\n<body>\n<tw-story></tw-story>\n' + archive(twee) +
            f'\n<script title="Twine engine code" data-main="harlowe">{engine}</script>\n'
            '</body>\n</html>\n')


class FromTwineHtml(unittest.TestCase):
    def setUp(self):
        self.mod = plotcanon.sample_world()[BELL]
        self.twee = plotcanon.to_twee(self.mod)

    def test_a_twine_archive_comes_back_as_the_same_file(self):
        back = plotcanon.from_twine(archive(self.twee))

        self.assertEqual(back.markdown, self.mod)
        self.assertEqual((back.warnings, back.problems), ((), ()))

    def test_a_published_story_comes_back_as_the_same_file(self):
        back = plotcanon.from_twine(published(self.twee))

        self.assertEqual(back.markdown, self.mod)
        self.assertEqual((back.warnings, back.problems), ((), ()))

    def test_the_file_may_be_given_as_bytes(self):
        back = plotcanon.from_twine(published(self.twee).encode("utf-8"))

        self.assertEqual(back.markdown, self.mod)

    def test_markup_characters_in_a_passage_are_read_as_text(self):
        twee = self.twee.replace("The sister stays above and is heard, not seen.",
                                 "The sister & the diver <never> \"meet\".")

        back = plotcanon.from_twine(archive(twee))

        self.assertIn("The sister & the diver <never> \"meet\".", back.markdown)

    def test_the_story_javascript_and_stylesheet_are_not_kept_and_say_so(self):
        back = plotcanon.from_twine(archive(self.twee, script="State.x = 1;",
                                            stylesheet="body { color: red }"))

        self.assertEqual(back.markdown, self.mod)
        self.assertEqual(len(back.warnings), 2)
        self.assertIn("JavaScript", back.warnings[0])
        self.assertIn("stylesheet", back.warnings[1])


class EditedInTwine(unittest.TestCase):
    """The Bell Beneath, opened in Twine, changed, and brought back."""

    def setUp(self):
        self.world = plotcanon.load_world(plotcanon.sample_world()).world
        self.twee = plotcanon.to_twee(plotcanon.sample_world()[BELL])

    def back(self, twee):
        result = plotcanon.from_twine(twee)
        self.assertEqual(result.problems, ())
        return result

    def test_passages_moved_on_the_map_change_nothing(self):
        moved = re.sub(r'"position":"\d+,\d+"', '"position":"725,1300"', self.twee)

        self.assertEqual(self.back(moved).markdown, plotcanon.sample_world()[BELL])

    def test_a_scene_added_in_twine_is_a_scene_of_the_mod(self):
        edited = self.twee.replace("[[down the rope->The bell]]",
                                   "[[down the rope->The bell]]; [[into the well->The well]]")
        edited += ("\n:: The well {\"position\":\"900,900\"}\n"
                   "Dark water.\n"
                   "**Leads to:** [[climb out->The bell]]\n")

        markdown = self.back(edited).markdown
        story = plotcanon.story(markdown)

        self.assertEqual([p.name for p in story.scenes],
                         ["The descent", "The bell", "Who rings it", "The well"])
        self.assertEqual(story.passage("The well").exits[0].passage, "The bell")
        self.assertIn("into the well → [[The well]]", markdown)
        self.assertLess(markdown.index("### The well"), markdown.index("## NPC Casting"))
        self.assertEqual(story.gaps, ())

    def test_a_link_changed_in_twine_leads_somewhere_else(self):
        edited = self.twee.replace("[[down the rope->The bell]]",
                                   "[[down the rope->Who rings it]]")

        story = plotcanon.story(self.back(edited).markdown)

        self.assertEqual([e.passage for e in story.passage("The descent").exits],
                         ["The crypt floods", "Who rings it"])

    def test_a_contest_result_added_in_twine_is_a_result_of_the_contest(self):
        edited = self.twee.replace("[[lose->The bell is rung]]",
                                   "[[lose->The bell is rung]], [[draw->The crypt floods]]")

        markdown = self.back(edited).markdown
        [contest] = plotcanon.story(markdown).passage("Who rings it").contests

        self.assertEqual([r.label for r in contest.results], ["win", "lose", "draw"])
        self.assertIn("**Contest:** stop her before the last stroke, win → [[The bell is "
                      "silenced]], lose → [[The bell is rung]], draw → [[The crypt floods]]",
                      markdown)

    def test_the_edited_mod_passes_the_validator(self):
        edited = self.twee.replace("[[down the rope->The bell]]",
                                   "[[down the rope->Who rings it]]")
        markdown = self.back(edited).markdown

        report = plotcanon.check_file(self.world, BELL, markdown)

        self.assertEqual(report.errors, ())
        self.assertIsNotNone(report.document)


class Warnings(unittest.TestCase):
    """What Twine can hold that a Dry Run does nothing with is kept as text
    and warned about. Nothing is dropped without a word."""

    def setUp(self):
        self.twee = plotcanon.to_twee(plotcanon.sample_world()[BELL])

    def edited(self, old, new):
        result = plotcanon.from_twine(self.twee.replace(old, new))
        self.assertEqual(result.problems, ())
        return result

    def test_twine_code_is_kept_as_text_with_a_warning_naming_the_passage(self):
        for code, kind in [("(goto: \"The bell\")", "macro"),
                           ("<<goto \"The bell\">>", "macro"),
                           ("You have $rope.", "variable"),
                           ("<span style=\"color:red\">cold</span>", "HTML"),
                           ("@@color:red;cold@@", "styling")]:
            with self.subTest(code):
                result = self.edited(
                    "**Find:** a stair full of sand", f"{code}\n**Find:** a stair full of sand")

                self.assertIn(code, result.markdown)
                [warning] = result.warnings
                self.assertTrue(warning.startswith("Twine: "))
                self.assertIn("`The descent`", warning)
                self.assertIn(kind, warning)
                self.assertIn("does nothing in a Dry Run", warning)

    def test_ordinary_prose_raises_no_warning(self):
        result = self.edited("**Find:** a stair full of sand",
                             "(Note: costs $5 a head.) Bring 2 > 1 lanterns.\n"
                             "**Find:** a stair full of sand")

        self.assertEqual(result.warnings, ())

    def test_a_tag_a_mod_has_no_use_for_is_not_kept_and_says_so(self):
        result = self.edited(":: The descent [scene]", ":: The descent [scene dark]")

        self.assertIn("### 1. The descent", result.markdown)
        [warning] = result.warnings
        self.assertIn("`dark`", warning)

    def test_a_link_with_no_label_is_kept_and_warned_about(self):
        result = self.edited("[[down the rope->The bell]]", "[[The bell]]")

        self.assertIn("**Leads to:** [[The bell]]", result.markdown)
        [warning] = result.warnings
        self.assertIn("[[The bell]]", warning)

    def test_a_heading_in_a_scene_that_would_start_another_scene_is_warned_about(self):
        result = self.edited("**Find:** a stair full of sand",
                             "### Notes\n\n**Find:** a stair full of sand")

        [warning] = result.warnings
        self.assertIn("### Notes", warning)

    def test_a_story_with_no_frontmatter_passage_fails_validation(self):
        start = self.twee.index(":: Frontmatter")
        end = self.twee.index("\n:: ", start)
        result = plotcanon.from_twine(self.twee[:start] + self.twee[end + 1:])
        world = plotcanon.load_world(plotcanon.sample_world()).world

        report = plotcanon.check_file(world, "inbox/the-bell-beneath.md", result.markdown)

        self.assertTrue(result.markdown.startswith("## Premise\n"))
        self.assertTrue(any("frontmatter" in w for w in result.warnings))
        self.assertTrue(report.errors)
        self.assertIsNone(report.document)

    def test_a_story_written_from_scratch_in_twine_converts(self):
        twee = (":: StoryTitle\nScratch\n\n"
                ":: Start [premise]\nIt begins. [[go in->Hall]]\n\n"
                ":: Hall\nA hall. [[leave->Out]]\n\n"
                ":: Out [outcome]\nThe end.\n")

        result = plotcanon.from_twine(twee)
        story = plotcanon.story(result.markdown)

        self.assertIn("## Start\n\nIt begins. go in → [[Hall]]", result.markdown)
        self.assertEqual([p.name for p in story.scenes], ["Hall"])
        self.assertEqual([p.name for p in story.endings], ["Out"])


class FilesFromStrangers(unittest.TestCase):
    """A Twine file is an upload. Whatever it holds, `from_twine` reports it
    and does not raise, and a small file cannot use up the machine."""

    def assertRefused(self, source, *words):
        result = plotcanon.from_twine(source)
        self.assertEqual(result.markdown, "")
        self.assertFalse(result.ok)
        [problem] = result.problems
        self.assertTrue(problem.startswith("Twine: "))
        for word in words:
            self.assertIn(word, problem)

    def test_a_file_with_no_passages_is_refused(self):
        self.assertRefused("", "no passages")
        self.assertRefused(plotcanon.sample_world()[BELL], "no passages")

    def test_an_html_file_with_no_twine_story_is_refused(self):
        self.assertRefused("<!DOCTYPE html><html><body>Hello</body></html>", "tw-storydata")

    def test_a_file_with_two_stories_is_refused(self):
        twee = plotcanon.to_twee(plotcanon.sample_world()[BELL])
        self.assertRefused(archive(twee) + archive(twee), "2 Twine stories")

    def test_bytes_that_are_not_utf8_are_refused(self):
        self.assertRefused(b"\xff\xfe:: Start\n\x00\xd8", "UTF-8")

    def test_a_huge_file_is_refused_unread(self):
        started = time.perf_counter()
        self.assertRefused(":: A\n" + "x" * 6_000_000, "larger than")
        self.assertRefused(b":: A\n" + b"x" * 6_000_000, "larger than")
        self.assertLess(time.perf_counter() - started, 1)

    def test_too_many_passages_are_refused(self):
        self.assertRefused("".join(f":: P{n}\nx\n" for n in range(1_001)), "passages")

    def test_a_contest_linked_over_and_over_cannot_blow_up_the_markdown(self):
        twee = (":: S\n" + "[[x->C]]\n" * 20_000 +
                ":: C [contest]\n" + "[[r->S]] " * 20_000 + "\n")
        started = time.perf_counter()

        self.assertRefused(twee, "larger than")
        self.assertLess(time.perf_counter() - started, 5)

    def test_lines_built_to_be_slow_are_not(self):
        for line in ["[[" * 200_000, "<<" * 200_000, "<a " * 200_000, "**" * 200_000,
                     "(set:" * 100_000, "@@" * 200_000, "→ [[" * 100_000]:
            with self.subTest(line[:8]):
                started = time.perf_counter()
                result = plotcanon.from_twine(f":: S [scene]\n{line}\n")
                self.assertEqual(result.problems, ())
                self.assertLess(time.perf_counter() - started, 2)

    def test_the_warnings_are_bounded(self):
        twee = "".join(f":: P{n} [tag{n}]\nx\n" for n in range(200))

        result = plotcanon.from_twine(twee)

        self.assertLessEqual(len(result.warnings), 51)
        self.assertIn("more", result.warnings[-1])

    def test_anything_but_text_or_bytes_is_a_type_error(self):
        with self.assertRaises(TypeError):
            plotcanon.from_twine(None)
        with self.assertRaises(TypeError):
            plotcanon.to_twee(b"---\n")
