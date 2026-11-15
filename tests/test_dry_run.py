"""A Mod's story, written into its body by the Dry Run convention, read
through `plotcanon.story`, and the checks on it that `load_world` and
`check_file` run at the strictness the World's `world.yml` asks for.
"""

import unittest

import plotcanon
from tests.test_world_rules import ValidatorTest

BODY = """\
## Premise

Sister Oleen calls a night vigil at the chapel.

## Hooks

- Oleen asks the party directly → [[The vigil itself]]
- Anyone watching the Order -> [[the lower door]]

## Scene Breakdown

Any scene can be the first one the party reaches.

### 1. The vigil itself

**Find:** thirty people, candles.
**If players do nothing:** Varen leaves at the third bell → [[The Order comes through]]
**Leads to:** someone challenges Varen → [[3. The Order comes through]]

### 2. The lower door

**Find:** the door, unbarred.
**Leads to:** back inside → [[The vigil itself]]; out into the field → [[The Order comes through]]

### 3. The Order comes through

**Find:** eight of the Order.
**Contest:** fight the Order, win → [[Order driven off]], lose → [[Register taken]]
**If players do nothing:** they take it → [[Register taken]]

## NPC Casting

Varen — a fighter.

## Possible Outcomes

### Order driven off

The register stays.

### Register taken

No one dies.

## GM Notes

He wants to be seen.
"""


class TheStory(unittest.TestCase):
    def setUp(self):
        self.story = plotcanon.story(BODY)

    def test_it_starts_at_the_premise_with_the_hooks_as_its_exits(self):
        start = self.story.start

        self.assertEqual(start.name, "Premise")
        self.assertEqual(start.kind, "start")
        self.assertIn("Sister Oleen calls a night vigil", start.text)
        self.assertEqual([(e.label, e.target, e.passage) for e in start.exits],
                         [("Oleen asks the party directly", "The vigil itself",
                           "The vigil itself"),
                          ("Anyone watching the Order", "the lower door", "The lower door")])

    def test_each_scene_lists_its_exits_including_what_happens_if_players_do_nothing(self):
        vigil = self.story.passage("The vigil itself")

        self.assertEqual(vigil.kind, "scene")
        self.assertEqual(vigil.heading, "1. The vigil itself")
        self.assertEqual([(e.label, e.passage, e.players_do_nothing) for e in vigil.exits],
                         [("Varen leaves at the third bell", "The Order comes through", True),
                          ("someone challenges Varen", "The Order comes through", False)])

    def test_one_line_can_lead_to_several_places(self):
        door = self.story.passage("2. the lower door")

        self.assertEqual([(e.label, e.passage) for e in door.exits],
                         [("back inside", "The vigil itself"),
                          ("out into the field", "The Order comes through")])

    def test_a_contest_names_where_each_result_leads(self):
        order = self.story.passage("The Order comes through")

        (contest,) = order.contests
        self.assertEqual(contest.label, "fight the Order")
        self.assertEqual([(r.label, r.passage) for r in contest.results],
                         [("win", "Order driven off"), ("lose", "Register taken")])
        self.assertEqual([c.label for c in order.choices],
                         ["they take it", "win", "lose"])

    def test_each_possible_outcome_is_an_ending(self):
        self.assertEqual([p.name for p in self.story.endings],
                         ["Order driven off", "Register taken"])
        self.assertEqual(self.story.endings[1].prose.strip(), "No one dies.")

    def test_the_passages_are_in_the_order_the_body_has_them(self):
        self.assertEqual([(p.kind, p.name) for p in self.story.passages],
                         [("start", "Premise"), ("scene", "The vigil itself"),
                          ("scene", "The lower door"), ("scene", "The Order comes through"),
                          ("ending", "Order driven off"), ("ending", "Register taken")])

    def test_prose_leaves_out_the_links_and_keeps_the_rest(self):
        self.assertEqual(self.story.passage("The vigil itself").prose.strip(),
                         "**Find:** thirty people, candles.\n"
                         "**If players do nothing:** Varen leaves at the third bell")
        self.assertEqual(self.story.passage("The Order comes through").prose.strip(),
                         "**Find:** eight of the Order.\n"
                         "**If players do nothing:** they take it")

    def test_text_is_the_passage_exactly_as_written(self):
        self.assertIn("**Leads to:** back inside → [[The vigil itself]]; out into the field",
                      self.story.passage("The lower door").text)

    def test_the_sections_are_the_whole_body_unchanged(self):
        self.assertEqual("".join(s.source for s in self.story.sections), BODY)
        self.assertEqual([s.heading for s in self.story.sections],
                         ["Premise", "Hooks", "Scene Breakdown", "NPC Casting",
                          "Possible Outcomes", "GM Notes"])

    def test_a_well_made_story_is_playable_with_nothing_to_say(self):
        self.assertTrue(self.story.structured)
        self.assertTrue(self.story.playable)
        self.assertEqual((self.story.problems, self.story.gaps), ((), ()))

    def test_it_reads_a_whole_file_or_a_document(self):
        text = "---\nid: x\ntype: mod\n---\n" + BODY

        self.assertEqual(plotcanon.story(text).passages, self.story.passages)


def changed(old, new):
    assert BODY.count(old) == 1, old
    return BODY.replace(old, new)


class WhatIsWrongWithAStory(unittest.TestCase):
    def test_a_link_to_nothing_means_no_dry_run(self):
        told = plotcanon.story(changed("they take it → [[Register taken]]", "they take it → [[Register burned]]"))

        self.assertFalse(told.playable)
        self.assertEqual(told.problems, (
            "Dry Run: `[[Register burned]]` in scene `The Order comes through` links to no "
            "scene or outcome — a link is the heading of a `###` under `## Scene Breakdown` "
            "or `## Possible Outcomes`",))
        self.assertIsNone(told.passage("The Order comes through").exits[0].passage)
        self.assertEqual(told.passage("The Order comes through").exits[0].target, "Register burned")

    def test_a_body_with_no_links_has_no_structure_and_no_dry_run(self):
        told = plotcanon.story("## Premise\n\nA vigil.\n\n## Hooks\n\n- Oleen asks.\n")

        self.assertFalse(told.structured)
        self.assertFalse(told.playable)
        self.assertIn("no Dry Run structure", told.problems[0])
        self.assertEqual(told.gaps, ())

    def test_a_scene_nothing_links_to(self):
        told = plotcanon.story(changed("- Anyone watching the Order -> [[the lower door]]\n", ""))

        self.assertTrue(told.playable)
        self.assertEqual(told.gaps, (
            "Dry Run: nothing links to scene `The lower door` — link to it from a Hook or "
            "another scene",))

    def test_a_scene_with_no_exits_that_is_not_an_outcome(self):
        told = plotcanon.story(changed(
            "**Leads to:** back inside → [[The vigil itself]]; out into the field → "
            "[[The Order comes through]]\n", ""))

        self.assertEqual(told.gaps, (
            "Dry Run: scene `The lower door` has no exits — add `**Leads to:** label → "
            "[[Scene or outcome]]` or a Contest, or make it an outcome under "
            "`## Possible Outcomes`",))

    def test_an_outcome_that_can_never_be_reached(self):
        told = plotcanon.story(changed(", win → [[Order driven off]]", ", win → [[Register taken]]"))

        self.assertEqual(told.gaps, (
            "Dry Run: outcome `Order driven off` can never be reached from the Premise",))

    def test_a_contest_needs_at_least_two_results(self):
        told = plotcanon.story(changed(", lose → [[Register taken]]", ""))

        self.assertEqual(told.gaps, (
            "Dry Run: the Contest `fight the Order` in scene `The Order comes through` names "
            "1 result — give it at least a success and a failure, each "
            "`result → [[Where it leads]]`",))

    def test_two_passages_with_one_heading_are_ambiguous(self):
        told = plotcanon.story(changed("### Register taken\n", "### The lower door\n"))

        self.assertIn("2 passages are headed `The lower door`", told.problems[0])

    def test_a_link_inside_a_code_block_is_not_a_link(self):
        told = plotcanon.story(changed("He wants to be seen.\n",
                                       "```\nx → [[Nowhere]]\n```\n"))

        self.assertTrue(told.playable)

    def test_nothing_in_a_body_makes_it_raise(self):
        for body in ("", "###\n", "## Premise\n→ [[]]\n", "**Contest:**\n",
                     "## Scene Breakdown\n### a\n**Contest:** → [[a]]\n", "[[x]] → →"):
            with self.subTest(body=body):
                plotcanon.story(body)


MOD = "inbox/the-ashen-vigil-2.md"
FRONTMATTER = """---
id: the-ashen-vigil-2
type: mod
title: "The Ashen Vigil, again"
aliases: ["The Ashen Vigil, again"]
mod_writer: mira
state: draft
canon: proposed
visibility: gm-only
features:
  npcs: [varen-ashcroft]
---
"""
UNSTRUCTURED = FRONTMATTER + "## Premise\n\nA vigil.\n\n## Hooks\n\n- Oleen asks.\n"
BROKEN = FRONTMATTER + changed("they take it → [[Register taken]]",
                               "they take it → [[Register burned]]")
UNLINKED = FRONTMATTER + changed("- Anyone watching the Order -> [[the lower door]]\n", "")


class TheWorldsDryRunStructure(ValidatorTest):
    """`world.yml` at the World's root says how strictly Mods are held to the
    convention: `off`, `encouraged` (the default) or `required`."""

    def setUp(self):
        super().setUp()
        self.restore_examples()

    def setting(self, value):
        self.write("world.yml", f"dry_run_structure: {value}\n")

    def findings(self, text):
        self.write(MOD, text)
        report = plotcanon.load_world(self.root)
        return ([str(f) for f in report.errors if f.path == MOD],
                [str(f) for f in report.warnings if f.path == MOD])

    def test_a_world_with_no_setting_is_encouraged(self):
        self.assertEqual(plotcanon.load_world(self.root).world.settings.dry_run_structure,
                         "encouraged")

    def test_encouraged_makes_the_checks_warnings(self):
        errors, warnings = self.findings(BROKEN)

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [f"WARN   {MOD}: Dry Run: `[[Register burned]]` in scene "
                                    "`The Order comes through` links to no scene or outcome "
                                    "— a link is the heading of a `###` under `## Scene "
                                    "Breakdown` or `## Possible Outcomes`"])

    def test_encouraged_says_nothing_of_a_mod_with_no_structure(self):
        self.assertEqual(self.findings(UNSTRUCTURED), ([], []))

    def test_required_makes_the_checks_errors(self):
        self.setting("required")

        errors, warnings = self.findings(UNLINKED)

        self.assertEqual(warnings, [])
        self.assertEqual(errors, [f"ERROR  {MOD}: Dry Run: nothing links to scene "
                                  "`The lower door` — link to it from a Hook or another scene"])

    def test_required_makes_a_mod_with_no_structure_an_error(self):
        self.setting("required")

        errors, _ = self.findings(UNSTRUCTURED)

        self.assertEqual(len(errors), 1)
        self.assertIn("no Dry Run structure", errors[0])

    def test_off_runs_no_checks(self):
        self.setting("off")  # YAML reads a bare `off` as false; it still means off

        self.assertEqual(self.findings(BROKEN), ([], []))
        self.assertEqual(plotcanon.load_world(self.root).world.settings.dry_run_structure, "off")

    def test_check_file_uses_the_worlds_setting(self):
        self.setting("required")
        # The example World's own Mod has no structure, so under `required`
        # the World loads only with the checks off.
        world = plotcanon.load_world(self.root, dry_run_structure="off").world

        report = plotcanon.check_file(world, MOD, UNLINKED)

        self.assertEqual(len(report.errors), 1)
        self.assertIsNone(report.document)

    def test_the_setting_can_be_given_instead_of_read(self):
        report = plotcanon.check_file(self.root, MOD, UNLINKED, dry_run_structure="off")
        self.assertEqual(report.findings, ())

        report = plotcanon.load_world({**plotcanon.read_directory(self.root), MOD: UNLINKED},
                                      dry_run_structure="required")
        self.assertFalse(report.ok)

    def test_a_setting_that_is_not_one_of_the_three_is_an_error(self):
        for value in ("strict", "on", "[required]"):
            with self.subTest(value):
                self.setting(value)

                report = plotcanon.load_world(self.root)

                self.assertFalse(report.ok)
                self.assertEqual([f.path for f in report.errors], ["world.yml"])
                self.assertIn("dry_run_structure", report.errors[0].message)

    def test_a_settings_file_that_is_not_a_mapping_of_known_settings(self):
        for text, said in (("- required\n", "must be a mapping"),
                           ("dry_run_structure: [\n", "not valid YAML"),
                           ("a: &x 1\nb: *x\n", "alias"),
                           ("organization: acme\n", "unknown setting `organization`")):
            with self.subTest(text):
                self.write("world.yml", text)

                report = plotcanon.load_world(self.root)

                self.assertIn(said, report.text())

    def test_the_settings_file_is_read_from_disk_and_kept_with_the_world(self):
        self.setting("off")

        files = plotcanon.read_directory(self.root)
        world = plotcanon.load_world(files).world

        self.assertEqual(files["world.yml"], "dry_run_structure: off\n")
        self.assertEqual(world.files["world.yml"], "dry_run_structure: off\n")

    def test_world_settings_reads_any_world_source(self):
        self.setting("required")

        for source in (self.root, plotcanon.read_directory(self.root),
                       plotcanon.load_world(self.root, dry_run_structure="off").world):
            with self.subTest(type(source).__name__):
                self.assertEqual(plotcanon.world_settings(source),
                                 plotcanon.WorldSettings(dry_run_structure="required"))
        self.assertEqual(plotcanon.world_settings({}), plotcanon.WorldSettings())


class WritingTheSettings(unittest.TestCase):
    def test_the_text_of_a_settings_file_reads_back_as_the_same_settings(self):
        for value in ("off", "encouraged", "required"):
            with self.subTest(value):
                text = plotcanon.WorldSettings(dry_run_structure=value).text()

                self.assertEqual(plotcanon.world_settings({"world.yml": text}).dry_run_structure,
                                 value)

    def test_a_setting_that_is_not_one_of_the_three_cannot_be_made(self):
        with self.assertRaises(ValueError):
            plotcanon.WorldSettings(dry_run_structure="strict")

    def test_the_allowed_values_are_a_vocabulary(self):
        vocabularies = plotcanon.vocabularies()

        self.assertEqual(list(vocabularies["vocabularies"]["dry_run_structure"]),
                         ["off", "encouraged", "required"])
        self.assertEqual(plotcanon.WORLD_SETTINGS_FILE, "world.yml")

    def test_a_setting_given_that_is_not_one_of_the_three_raises(self):
        with self.assertRaises(ValueError):
            plotcanon.load_world({}, dry_run_structure="strict")


class TheSampleWorldsDryRuns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = plotcanon.sample_world()
        cls.world = plotcanon.load_world(cls.files).world

    def test_it_says_its_dry_run_structure_is_encouraged(self):
        self.assertIn("world.yml", self.files)
        self.assertEqual(self.world.settings.dry_run_structure, "encouraged")

    def test_one_mod_uses_the_convention_and_can_be_played_to_every_ending(self):
        told = plotcanon.story(self.world.get("the-bell-beneath"))

        self.assertTrue(told.playable)
        self.assertEqual(told.gaps, ())
        self.assertEqual([p.name for p in told.endings],
                         ["The bell is silenced", "The bell is rung", "The bell is taken",
                          "The crypt floods"])

    def test_the_mods_with_no_structure_validate_under_encouraged(self):
        unstructured = [m.id for m in self.world.of_type("mod")
                        if not plotcanon.story(m).structured]

        self.assertIn("the-ferrymans-price", unstructured)
        self.assertEqual(plotcanon.load_world(self.files).findings, ())


class TheSchemaDoc(unittest.TestCase):
    def test_its_example_mod_can_be_played_with_nothing_to_say(self):
        doc = plotcanon.schema_files()["mod.md"]
        example = doc[doc.index("```markdown\n") + len("```markdown\n"):doc.rindex("```")]

        told = plotcanon.story(example)

        self.assertTrue(told.structured)
        self.assertEqual((told.problems, told.gaps), ((), ()))
        self.assertEqual(len(told.scenes), 3)
