"""The instructions for an Interview: the text an LLM is given to help a Mod
Writer write a Mod, or revise one the Plot Master sent back."""

import re
import unittest

import plotcanon

instructions = plotcanon.interview_instructions

KINDS = ("new-mod", "revise-mod")
SURFACES = ("web", "cli")

DRAFT = """\
---
id: the-salt-ledger
type: mod
title: "The Salt Ledger"
aliases: ["The Salt Ledger"]
mod_writer: mira
features:
  npcs: [harbour-clerk]
---

## Premise

A clerk keeps two ledgers.
"""

REASON = "The clerk needs a second way in, and the ending is decided in advance."
FLAGS = (("harbour-clerk", "The clerk was arrested at the last Event."),
         ("ledger-house", "The house was burned by an approved Canon Change."))


def revising(surface="web", **more):
    return instructions("revise-mod", surface, draft=DRAFT, sent_back_reason=REASON,
                        flags=FLAGS, **more)


def every_output(world=None):
    for surface in SURFACES:
        yield f"new-mod/{surface}", instructions("new-mod", surface, world=world)
        yield f"revise-mod/{surface}", revising(surface, world=world)


class KindsAndSurfaces(unittest.TestCase):
    def test_every_kind_on_every_surface_has_instructions(self):
        for name, text in every_output():
            with self.subTest(name):
                self.assertIsInstance(text, str)
                self.assertGreater(len(text.strip()), 0)

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            instructions("debrief", "web")

    def test_an_unknown_surface_is_refused(self):
        with self.assertRaises(ValueError):
            instructions("new-mod", "email")


class TheDryRunConvention(unittest.TestCase):
    def test_the_example_story_passes_the_dry_run_check(self):
        for name, text in every_output():
            with self.subTest(name):
                examples = re.findall(r"```markdown\n(.*?)```", text, re.S)
                story = [e for e in examples if "Sister Oleen calls a night vigil" in e]
                self.assertEqual(len(story), 1)

                told = plotcanon.story(story[0])

                self.assertTrue(told.structured)
                self.assertEqual(told.problems, ())
                self.assertEqual(told.gaps, ())
                self.assertTrue(any(p.contests for p in told.passages))
                self.assertTrue(any(e.players_do_nothing for p in told.passages
                                    for e in p.exits))

    def test_each_rule_the_check_enforces_is_named(self):
        rules = [
            "`## Premise` is where a Dry Run starts",          # no Premise: no Dry Run
            "Each bullet under `## Hooks` names the scene",    # the Premise leads nowhere
            "`**Leads to:**",                                 # a scene's exits
            "`**If players do nothing:**",
            "`**Contest:**",
            "Each `###` under `## Possible Outcomes` is an ending",
            "A link is the target's heading text",
            "A label may not contain `,` or `;`",
            "A link line is one line: it may not wrap",
            "Every link leads to a scene or outcome that exists",
            "No two scenes or outcomes have the same heading",
            "at least one Hook leads on from it",
            "Every scene has something linking to it",
            "Every scene has at least one exit or a Contest",
            "Every Contest names at least two results",
            "Every outcome can be reached from the Premise",
        ]
        for name, text in every_output():
            flat = " ".join(text.split())
            for rule in rules:
                with self.subTest(name, rule=rule):
                    self.assertIn(rule, flat)


def sample():
    return plotcanon.load_world(plotcanon.sample_world()).world


class WhatThePersonMayRead(unittest.TestCase):
    def test_with_a_world_every_slug_in_it_is_given(self):
        world = sample()
        for name, text in every_output(plotcanon.sample_world()):
            for document in world.documents:
                with self.subTest(name, slug=document.id):
                    self.assertIn(document.id, text)

    def test_a_world_is_taken_in_any_form_a_world_is(self):
        files = plotcanon.sample_world()

        self.assertEqual(instructions("new-mod", "web", world=sample()),
                         instructions("new-mod", "web", world=files))

    def test_with_no_world_no_slug_from_one_is_given(self):
        world = sample()
        for name, text in every_output():
            for document in world.documents:
                with self.subTest(name, slug=document.id):
                    self.assertNotRegex(text, rf"(?<![\w-]){re.escape(document.id)}(?![\w-])")

    def test_a_document_left_out_of_the_world_never_appears(self):
        world = sample()
        # A Mod nothing else in the World names, so only its own file could
        # put its id, title or text into the instructions.
        left_out = world.get("the-guildmasters-daughter")
        files = plotcanon.sample_world()
        del files[left_out.path]
        del files["canon/plots/feud-of-vale-and-marr.md"]   # it lists the Mod
        premise = "what happened the night her uncle drowned"

        for name, text in every_output(files):
            with self.subTest(name):
                self.assertNotIn(left_out.id, text)
                self.assertNotIn(left_out.fields["title"], text)
                self.assertNotIn(left_out.path, text)
                self.assertNotIn(premise, text)

    def test_with_a_world_existing_slugs_are_used_and_only_new_things_proposed(self):
        with_world = instructions("new-mod", "web", world=plotcanon.sample_world())
        without = instructions("new-mod", "cli")

        self.assertIn("only if the Mod needs an NPC, faction, location or plot that is truly new",
                      " ".join(with_world.split()))
        self.assertIn("including ones you are sure already exist", " ".join(without.split()))


class Revising(unittest.TestCase):
    def test_the_draft_its_send_back_reason_and_its_flags_are_given(self):
        for surface in SURFACES:
            with self.subTest(surface):
                text = revising(surface)

                self.assertIn("the-salt-ledger", text)
                self.assertIn("A clerk keeps two ledgers.", text)
                self.assertIn(REASON, text)
                for feature, message in FLAGS:
                    self.assertIn(feature, text)
                    self.assertIn(message, text)

    def test_the_draft_keeps_its_id(self):
        flat = " ".join(revising().split())

        self.assertIn("Keep `id: the-salt-ledger` exactly as it is", flat)

    def test_the_conversation_starts_with_the_reason_and_the_flags(self):
        flat = " ".join(revising().split())

        self.assertIn("Start the conversation by working through why the Plot Master sent "
                      "the draft back, and then each Flag on it", flat)

    def test_a_draft_may_come_back_with_no_reason_and_no_flags(self):
        text = instructions("revise-mod", "cli", draft=DRAFT)

        self.assertIn("the-salt-ledger", text)
        self.assertIn("The Plot Master gave no reason", text)
        self.assertIn("There are no open Flags on it", text)

    def test_revising_needs_a_draft(self):
        with self.assertRaises(ValueError):
            instructions("revise-mod", "web")

    def test_a_draft_with_no_id_is_refused(self):
        with self.assertRaises(ValueError):
            instructions("revise-mod", "web", draft="## Premise\n\nNo frontmatter.\n")

    def test_a_new_mod_has_no_draft(self):
        with self.assertRaises(ValueError):
            instructions("new-mod", "web", draft=DRAFT)
        with self.assertRaises(ValueError):
            instructions("new-mod", "web", flags=FLAGS)


class Wording(unittest.TestCase):
    def test_every_output_keeps_to_the_glossary(self):
        for world in (None, plotcanon.sample_world()):
            for name, text in every_output(world):
                with self.subTest(name, world=world is not None):
                    self.assertEqual(plotcanon.avoided_words(text), [])


ERRORS = "inbox/the-salt-ledger.md: `type` is `nonsense`, not one of the document types."


class FixRequest(unittest.TestCase):
    def test_it_gives_the_errors_and_says_it_comes_from_the_app(self):
        text = plotcanon.interview_fix_request(ERRORS)
        flat = " ".join(text.split())

        self.assertIn(ERRORS, text)
        self.assertIn("This message is from the app, not the person", flat)

    def test_it_says_the_person_has_not_seen_the_file(self):
        flat = " ".join(plotcanon.interview_fix_request(ERRORS).split())

        self.assertIn("The person has not seen the file yet", flat)

    def test_it_asks_for_the_whole_file_again_in_one_code_block_as_the_web_instructions_do(self):
        flat = " ".join(plotcanon.interview_fix_request(ERRORS).split())
        web = " ".join(instructions("new-mod", "web").split())

        asked = "the whole of it, from the opening `---` to the last section, in a single markdown code block"
        self.assertIn(asked, web)
        self.assertIn("give the whole file again: from the opening `---` to the last section, "
                      "in a single markdown code block", flat)

    def test_empty_errors_are_refused(self):
        for errors in ("", "  \n"):
            with self.subTest(errors=errors), self.assertRaises(ValueError):
                plotcanon.interview_fix_request(errors)

    def test_it_keeps_to_the_glossary(self):
        self.assertEqual(plotcanon.avoided_words(plotcanon.interview_fix_request(ERRORS)), [])


class ReviseOpener(unittest.TestCase):
    def test_it_asks_the_llm_to_begin_with_the_reason_and_the_flags(self):
        flat = " ".join(plotcanon.interview_revise_opener().split())

        self.assertIn("why the Plot Master sent the draft back", flat)
        self.assertIn("each Flag on it", flat)
        self.assertIn("say so and ask me what I want to change", flat)

    def test_it_asks_for_what_the_revise_instructions_say_to_start_with(self):
        flat = " ".join(plotcanon.interview_revise_opener().split())
        told = " ".join(revising().split())

        for phrase in ("why the Plot Master sent the draft back", "each Flag on it"):
            with self.subTest(phrase):
                self.assertIn(phrase, flat)
                self.assertIn(phrase, told)

    def test_it_keeps_to_the_glossary(self):
        self.assertEqual(plotcanon.avoided_words(plotcanon.interview_revise_opener()), [])


BELL = "mods/lanternlight/the-bell-beneath.md"
EXPECTED = "learns what rings the bell, and whether to forgive it"
BELL_MOD = plotcanon.sample_world()[BELL].replace(
    "supersedes: []\n", f'expected_changes:\n  sister-ane: "{EXPECTED}"\nsupersedes: []\n')
SILENCED = [{"hook": "The sister asks them to close what was opened"}, "The descent",
            "The bell", "Who rings it",
            {"contest": "stop her before the last stroke", "result": "win"},
            "The bell is silenced"]
STOPPED = [{"hook": "The sister asks them to close what was opened"}, "The descent"]


def reporting(surface="web", **more):
    return instructions("report", surface, mod=BELL_MOD, **more)


class Reporting(unittest.TestCase):
    """The report Interview: an LLM helps a Mod Runner write the After-Action
    Report for one Stretch, from the Path walked, if any."""

    def test_both_surfaces_have_instructions_with_a_path_and_without(self):
        for surface in SURFACES:
            for path in (SILENCED, None):
                with self.subTest(surface, path=path is not None):
                    text = reporting(surface, path=path)

                    self.assertIsInstance(text, str)
                    self.assertIn("After-Action Report", text)

    def test_the_mod_and_its_expected_changes_are_given(self):
        text = reporting()

        self.assertIn("id: the-bell-beneath", text)
        self.assertIn("The party goes down into the crypt under the chapel", text)
        flat = " ".join(text.split())
        self.assertIn(f"`sister-ane`: {EXPECTED}", flat)

    def test_the_path_walked_is_given_step_by_step(self):
        flat = " ".join(reporting(path=SILENCED).split())

        for step in ("The sister asks them to close what was opened", "The descent",
                     "Who rings it", "stop her before the last stroke", "win",
                     "The bell is silenced"):
            with self.subTest(step):
                self.assertIn(step, flat)
        self.assertIn("contest: stop her before the last stroke", reporting(path=SILENCED))

    def test_finished_is_proposed_by_the_path_for_the_mod_runner_to_confirm(self):
        ending = " ".join(reporting(path=SILENCED).split())
        scene = " ".join(reporting(path=STOPPED).split())

        self.assertIn("The Path ends at the outcome `The bell is silenced`, so it proposes "
                      "`finished: true`", ending)
        self.assertIn("The Path ends at the scene `The descent`, so it proposes "
                      "`finished: false`", scene)
        for text in (ending, scene):
            self.assertIn("Ask me to confirm it", text)

    def test_with_no_path_the_mod_runner_says_what_happened_and_where_play_stopped(self):
        flat = " ".join(reporting().split())

        self.assertIn("There is no Path for this report", flat)
        self.assertIn("say in my own words what happened and where play stopped", flat)

    def test_it_asks_pcs_and_what_went_off_script(self):
        for path in (SILENCED, None):
            flat = " ".join(reporting(path=path).split())
            for asked in ("which PCs took part (`pcs`)", "what went off-script"):
                with self.subTest(asked, path=path is not None):
                    self.assertIn(asked, flat)

    def test_with_no_path_it_asks_whether_the_mod_ran(self):
        flat = " ".join(reporting().split())

        self.assertIn("whether the Mod ran (`ran`)", flat)
        self.assertIn("If it did not run", flat)

    def test_a_path_walked_means_the_mod_ran(self):
        text = reporting(path=SILENCED)
        flat = " ".join(text.split())

        self.assertNotIn("whether the Mod ran", flat)
        self.assertNotIn("If it did not run", flat)
        self.assertIn("\nran: true\n", text)

    def test_canon_changes_are_written_in_the_schemas_terms(self):
        flat = " ".join(reporting().split())

        for kind in ("status", "location", "affiliation", "relationship", "knowledge",
                     "narrative", "created"):
            with self.subTest(kind):
                self.assertIn(f"`{kind}`", flat)
        self.assertIn("`decision: proposed`", flat)
        self.assertIn("**Required** for `status`, `location` and `affiliation`", flat)
        self.assertIn("`## What Happened` · `## Divergences From The Mod` · `## Loose Ends`",
                      flat)

    def test_the_path_is_copied_into_the_report_as_given(self):
        text = reporting(path=SILENCED)

        self.assertIn("path:\n  - hook: The sister asks them to close what was opened\n"
                      "  - The descent\n", text)

    def test_a_stretch_that_continues_another_says_where_the_last_stopped(self):
        later = ["The bell", "The bell is taken"]

        for stop in ("The bell", plotcanon.LastStop("The bell")):
            with self.subTest(stop=stop):
                text = " ".join(reporting(path=later, continues_from=stop).split())

                self.assertIn("The last report on this Mod says play stopped at `The bell`",
                              text)
        no_path = " ".join(reporting(continues_from="The bell").split())
        self.assertIn("The last report on this Mod says play stopped at `The bell`", no_path)

    def test_when_where_the_last_stretch_stopped_is_not_known_it_says_so(self):
        unknown = plotcanon.LastStop(known=False)
        later = ["Who rings it", "The bell is rung"]

        for path in (later, None):
            with self.subTest(path=path):
                text = " ".join(reporting(path=path, continues_from=unknown).split())

                self.assertIn("where play stopped is not known", text)
                self.assertNotIn("says play stopped at", text)
        with self.assertRaises(ValueError):
            reporting(path=later)

    def test_the_first_report_on_a_mod_says_nothing_of_an_earlier_one(self):
        text = " ".join(reporting(path=SILENCED, continues_from=plotcanon.LastStop()).split())

        self.assertNotIn("The last report on this Mod", text)
        self.assertNotIn("is not known", text)

    def test_the_event_is_given_so_the_llm_need_not_ask(self):
        text = reporting(path=SILENCED, event="e04-second-lantern")

        self.assertIn("\nevent: e04-second-lantern\n", text)
        self.assertNotIn("If you do not know which, ask me", " ".join(text.split()))
        self.assertIn("If you do not know which, ask me", " ".join(reporting().split()))

    def test_a_group_given_is_written_so_the_llm_need_not_ask(self):
        text = reporting(path=SILENCED, event="e04-second-lantern", group=" cellar ")
        flat = " ".join(text.split())

        self.assertIn("\nevent: e04-second-lantern\ngroup: cellar\n", text)
        self.assertIn("this report is for my Group, `cellar`", flat)
        self.assertNotIn("If you do not know whether the players split, ask me", flat)

    def test_no_group_given_says_to_leave_it_out(self):
        flat = " ".join(reporting(path=SILENCED, group="").split())

        self.assertNotIn("\ngroup:", reporting(path=SILENCED, group=""))
        self.assertIn("Leave out `group`: this report covers the whole Mod", flat)
        self.assertNotIn("If you do not know whether the players split, ask me", flat)

    def test_with_the_group_not_given_the_llm_asks_as_before(self):
        self.assertIn("If you do not know whether the players split, ask me",
                      " ".join(reporting(path=SILENCED).split()))

    def test_a_group_must_be_a_short_label_on_one_line(self):
        for group in ("x" * 61, "two\nlines"):
            with self.subTest(group), self.assertRaises(ValueError):
                reporting(group=group)
        with self.assertRaises(TypeError):
            reporting(group=["cellar"])

    def test_only_a_report_takes_a_group(self):
        with self.assertRaises(ValueError):
            plotcanon.interview_instructions("new-mod", "web", group="cellar")

    def test_with_a_world_the_reports_id_is_worked_out(self):
        files = plotcanon.sample_world()
        self.assertIn("\nid: aa-the-bell-beneath\n", reporting(world=files))

        files["after-actions/e04-second-lantern/aa-the-bell-beneath.md"] = \
            files["after-actions/e02-first-lantern/aa-the-ferrymans-price.md"].replace(
                "aa-the-ferrymans-price", "aa-the-bell-beneath")
        text = reporting(world=files)

        self.assertIn("\nid: aa-the-bell-beneath-2\n", text)
        self.assertIn("Keep `id: aa-the-bell-beneath-2` exactly", " ".join(text.split()))

    def test_without_a_world_the_id_follows_the_convention(self):
        self.assertIn("id: aa-the-bell-beneath              # aa-the-bell-beneath-2",
                      reporting())

    def test_a_world_gives_the_slugs_to_use(self):
        text = reporting(path=SILENCED, world=plotcanon.sample_world())

        self.assertIn("pc-bram-tolliver", text)

    def test_a_path_that_does_not_fit_the_mod_is_refused(self):
        with self.assertRaises(ValueError):
            reporting(path=["The belfry"])
        with self.assertRaises(ValueError):
            reporting(path=["The bell"])                 # does not start at a Hook

    def test_a_path_on_a_mod_with_no_dry_run_is_refused(self):
        unstructured = plotcanon.sample_world()["mods/lanternlight/the-ferrymans-price.md"]

        with self.assertRaises(ValueError):
            instructions("report", "web", mod=unstructured, path=STOPPED)
        self.assertIn("There is no Path for this report",
                      " ".join(instructions("report", "web", mod=unstructured).split()))

    def test_reporting_needs_a_mod_with_an_id(self):
        with self.assertRaises(ValueError):
            instructions("report", "web")
        with self.assertRaises(ValueError):
            instructions("report", "web", mod="## Premise\n\nNo frontmatter.\n")

    def test_values_of_the_wrong_type_raise_type_error(self):
        with self.assertRaises(TypeError):
            reporting(continues_from=3)
        with self.assertRaises(TypeError):
            reporting(event=["e04-second-lantern"])
        with self.assertRaises(TypeError):
            instructions("report", "web", mod=3)

    def test_each_kind_takes_only_what_it_uses(self):
        with self.assertRaises(ValueError):
            instructions("report", "web", mod=BELL_MOD, draft=DRAFT)
        with self.assertRaises(ValueError):
            instructions("new-mod", "web", mod=BELL_MOD)
        with self.assertRaises(ValueError):
            revising(path=SILENCED)
        with self.assertRaises(ValueError):
            instructions("new-mod", "web", event="e04-second-lantern")

    def test_it_keeps_to_the_glossary(self):
        for surface in SURFACES:
            for path in (SILENCED, None):
                with self.subTest(surface, path=path is not None):
                    self.assertEqual(plotcanon.avoided_words(reporting(surface, path=path)), [])


class ReportOpener(unittest.TestCase):
    def test_with_a_path_it_asks_the_llm_to_begin_with_it(self):
        flat = " ".join(plotcanon.interview_report_opener(SILENCED).split())

        self.assertIn("Go through the Path with me", flat)

    def test_with_no_path_it_asks_the_mod_runner_to_say_what_happened(self):
        for path in (None, []):
            with self.subTest(path=path):
                flat = " ".join(plotcanon.interview_report_opener(path).split())

                self.assertIn("ask me to say in my own words what happened and where play "
                              "stopped", flat)

    def test_it_keeps_to_the_glossary(self):
        for path in (SILENCED, None):
            self.assertEqual(plotcanon.avoided_words(plotcanon.interview_report_opener(path)),
                             [])
