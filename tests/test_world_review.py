"""The instructions for a World review, and reading what the LLM writes: the
app's LLM looks across a whole World for drift, dormant Plots and chances to
bring recurring NPCs and Plots back, for the plot team."""

import unittest

import plotcanon

instructions = plotcanon.world_review_instructions

SURFACES = ("web", "cli")


def reviewing(surface="web", **more):
    given = dict(world=plotcanon.sample_world())
    given.update(more)
    return instructions(surface, **given)


class TheInstructions(unittest.TestCase):
    def test_both_surfaces_name_every_section_in_order(self):
        for surface in SURFACES:
            for world in (plotcanon.sample_world(), None):
                if surface == "web" and world is None:
                    continue
                with self.subTest(surface, world=world is not None):
                    text = reviewing(surface, world=world)
                    places = [text.find(f"## {heading}\n")
                              for heading in plotcanon.WORLD_REVIEW_SECTIONS]

                    self.assertNotIn(-1, places)
                    self.assertEqual(places, sorted(places))

    def test_the_sections_are_the_ones_the_plot_team_reads(self):
        self.assertEqual(plotcanon.WORLD_REVIEW_SECTIONS, (
            "State of the World", "Drift", "Watch list", "Weaving", "Coverage"))

    def test_the_whole_world_is_given(self):
        text = reviewing()

        for document in plotcanon.load_world(plotcanon.sample_world()).world.documents:
            with self.subTest(document.id):
                self.assertIn(document.id, text)

    def test_it_looks_for_what_no_single_check_can_see(self):
        flat = " ".join(reviewing().split())
        for looked_for in ("Plots that lost their way", "`decision: proposed`",
                           "`as_of`", "## Divergences From The Mod", "## Loose Ends",
                           "## Where It Could Go", "Recurring NPCs"):
            with self.subTest(looked_for):
                self.assertIn(looked_for, flat)

    def test_the_check_findings_are_given_so_they_are_not_repeated(self):
        text = reviewing(findings=["WARN canon/npcs/old-fenn.md: as_of is old"])

        self.assertIn("WARN canon/npcs/old-fenn.md: as_of is old", text)

    def test_it_is_one_report_not_a_conversation(self):
        self.assertIn("one report, not a conversation", " ".join(reviewing().split()))

    def test_on_the_cli_the_world_may_be_read_from_files(self):
        flat = " ".join(instructions("cli").split())

        self.assertIn("`canon/`", flat)
        self.assertIn("plotcanon validate", flat)

    def test_it_keeps_to_the_glossary(self):
        for surface in SURFACES:
            with self.subTest(surface):
                self.assertEqual(plotcanon.avoided_words(reviewing(surface)), [])
        self.assertEqual(plotcanon.avoided_words(instructions("cli")), [])


class WhatIsRefused(unittest.TestCase):
    def test_an_unknown_surface_is_refused(self):
        with self.assertRaises(ValueError):
            reviewing("email")

    def test_the_web_needs_the_world(self):
        with self.assertRaises(ValueError):
            instructions("web")

    def test_findings_given_as_one_text_raise_type_error(self):
        with self.assertRaises(TypeError):
            reviewing(findings="one finding")


SAMPLE = """\
## State of the World

Four Events have run. Two Plots are open and one is quietly dormant.

- not a finding that needs ids: this section is prose.

## Drift

- `feud-of-vale-and-marr`: marked `open`, but no Mod has touched it since
  `e01-low-tide`.
- `old-fenn`: `as_of` is `e01-low-tide`, three Events behind.

## Watch list

None.

## Weaving

- `harrow-dunmore`, `the-guildmasters-daughter`: he could be in the room in
  the second scene. Disruption: none.

## Coverage

- `e05-high-water`: nothing is scheduled.
"""


class ReadingTheReport(unittest.TestCase):
    def test_a_review_in_the_shape_is_read_into_its_sections(self):
        read = plotcanon.read_world_review(SAMPLE)

        self.assertEqual(read.problems, ())
        self.assertEqual(tuple(s.heading for s in read.sections),
                         plotcanon.WORLD_REVIEW_SECTIONS)
        self.assertTrue(read.section("State of the World").text.startswith("Four Events"))
        self.assertEqual([f.ids for f in read.section("Drift").findings],
                         [("feud-of-vale-and-marr",), ("old-fenn",)])
        self.assertEqual(read.section("Weaving").findings[0].ids,
                         ("harrow-dunmore", "the-guildmasters-daughter"))
        self.assertEqual(read.section("Watch list").findings, ())

    def test_a_reconciliations_headings_are_problems_in_a_review(self):
        read = plotcanon.read_world_review("## Conflicts\n\nNone.\n")

        self.assertTrue(any("Conflicts" in p for p in read.problems))
        self.assertEqual(sum("there is no" in p for p in read.problems), 5)


if __name__ == "__main__":
    unittest.main()
