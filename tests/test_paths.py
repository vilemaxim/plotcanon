"""A report's Path: the way one Stretch went through its Mod's Dry Run, written
as the report's `path`, and checked against the Mod's story by `load_world`
and `check_file`. The sample World's `the-bell-beneath` is the Mod walked."""

import unittest

import plotcanon

FIRST = "after-actions/e04-second-lantern/aa-the-bell-beneath.md"
SECOND = "after-actions/e04-second-lantern/aa-the-bell-beneath-2.md"

SILENCED = """\
  - hook: The sister asks them to close what was opened
  - The descent
  - The bell
  - Who rings it
  - contest: stop her before the last stroke
    result: win
  - The bell is silenced
"""


def report(path=SILENCED, *, id="aa-the-bell-beneath", finished="true", ran="true"):
    path_field = "" if path is None else f"path:\n{path}"
    return f"""\
---
id: {id}
type: after-action
mod: the-bell-beneath
event: e04-second-lantern
ran: {ran}
finished: {finished}
mod_runner: sam
pcs: [pc-bram-tolliver]
{path_field}canon_changes: []
---

## What Happened

## Divergences From The Mod

## Loose Ends
"""


def findings(files, changed=None):
    """The errors and warnings `load_world` gives on the reports added, as
    their messages, with the sample World's files, and any `changed`, under
    them."""
    loaded = plotcanon.load_world({**plotcanon.sample_world(), **(changed or {}), **files})
    errors = [f.message for f in loaded.errors if f.path in files]
    warnings = [f.message for f in loaded.warnings if f.path in files]
    return errors, warnings


class AReportsPath(unittest.TestCase):
    def test_a_path_from_a_hook_to_an_ending_is_clean(self):
        self.assertEqual(findings({FIRST: report()}), ([], []))

    def test_a_step_that_names_no_passage_is_an_error(self):
        errors, _ = findings({FIRST: report(SILENCED.replace("- The bell\n", "- The belfry\n"))})

        self.assertIn("`path[2]`: `The belfry` is not a scene or outcome of the Mod", errors)

    def test_a_step_that_cannot_be_reached_from_the_one_before_is_an_error(self):
        # The descent leads only down the rope to the bell, or to the flood.
        errors, _ = findings({FIRST: report(SILENCED.replace("  - The bell\n", ""))})

        self.assertEqual(errors, ["`path[2]`: `Who rings it` cannot be reached from "
                                  "`The descent` — its ways on are "
                                  "`The crypt floods`, `The bell`"])

    def test_a_contest_result_the_contest_does_not_have_is_an_error(self):
        errors, _ = findings({FIRST: report(SILENCED.replace("result: win", "result: draw"))})

        self.assertEqual(errors, ["`path[4]`: the Contest `stop her before the last stroke` "
                                  "has no result `draw` — its results are `win`, `lose`"])

    def test_a_contest_the_mod_does_not_have_is_an_error(self):
        errors, _ = findings({FIRST: report(SILENCED.replace("stop her before the last stroke",
                                                             "wrestle the bell"))})

        self.assertEqual(errors, ["`path[4]`: `wrestle the bell` is not a Contest in the Mod"])

    def test_a_hook_the_mod_does_not_have_is_an_error(self):
        errors, _ = findings({FIRST: report(SILENCED.replace("The sister asks them",
                                                             "A stranger asks them"))})

        self.assertEqual(errors, ["`path[0]`: `A stranger asks them to close what was opened` "
                                  "is not one of the Mod's Hooks"])

    def test_a_step_must_follow_where_a_hook_or_a_result_leads(self):
        errors, _ = findings({FIRST: report(SILENCED.replace("The bell is silenced",
                                                             "The bell is rung"))})

        self.assertEqual(errors, ["`path[5]`: `The bell is rung` is not where the result "
                                  "`win` of the Contest `stop her before the last stroke` "
                                  "leads, which is `The bell is silenced`"])

    def test_a_contest_out_of_the_passage_before_it_is_an_error(self):
        errors, _ = findings({FIRST: report(SILENCED.replace("  - Who rings it\n", ""))})

        self.assertEqual(errors, ["`path[3]`: the Contest `stop her before the last stroke` "
                                  "cannot be reached from `The bell`"])

    def test_a_path_ends_at_a_passage_not_at_a_contest(self):
        errors, _ = findings({FIRST: report(SILENCED.replace("  - The bell is silenced\n", ""),
                                            finished="false")})

        self.assertEqual(errors, ["`path[4]`: a Path ends at the scene or outcome where play "
                                  "stopped — add `The bell is silenced`, where the result "
                                  "`win` of the Contest `stop her before the last stroke` "
                                  "leads"])

    def test_a_path_starts_with_a_hook(self):
        errors, _ = findings({FIRST: report(SILENCED.split("\n", 1)[1])})

        self.assertEqual(errors, ["`path[0]`: a Path starts with the Hook taken "
                                  "(`hook: <the Hook>`), or where the last report's Path "
                                  "stopped, not at `The descent`"])

    def test_steps_are_matched_as_links_are(self):
        path = SILENCED.replace("The descent", "1. the DESCENT").replace("result: win",
                                                                        "result: Win")

        self.assertEqual(findings({FIRST: report(path)}), ([], []))

    def test_a_step_of_the_wrong_shape_is_an_error(self):
        for step in ("[The bell]", "{scene: The bell}", "{contest: x}", "''", "3"):
            with self.subTest(step):
                errors, _ = findings({FIRST: report(SILENCED.replace("- The bell\n",
                                                                     f"- {step}\n", 1))})

                self.assertIn("`path[2]` must be the name of a scene or outcome, `hook: <the "
                              "Hook taken>`, or `contest: <the Contest>` with `result: <the "
                              "result taken>`", errors)

    def test_a_path_that_is_not_a_list_is_an_error(self):
        errors, _ = findings({FIRST: report("  The bell\n")})

        self.assertEqual(errors, ["`path` must be a list of steps"])

    def test_a_report_with_no_path_is_not_checked(self):
        self.assertEqual(findings({FIRST: report(None)}), ([], []))


STOPPED = """\
  - hook: The diver has been to the door before, and knows a way past the sand
  - The bell
"""


class WherePlayStopped(unittest.TestCase):
    def test_a_path_that_stops_at_a_scene_is_clean_when_not_finished(self):
        self.assertEqual(findings({FIRST: report(STOPPED, finished="false")}), ([], []))

    def test_an_ending_reached_with_finished_false_is_a_warning(self):
        self.assertEqual(findings({FIRST: report(finished="false")}), ([], [
            "`path` ends at the outcome `The bell is silenced`, but the report says "
            "`finished: false` — an ending reached leaves the Mod nothing to play. Say "
            "`finished: true`, or correct the Path"]))

    def test_a_scene_with_finished_true_is_a_warning(self):
        self.assertEqual(findings({FIRST: report(STOPPED)}), ([], [
            "`path` ends at the scene `The bell`, but the report says `finished: true` — "
            "play that stopped at a scene has more of the Mod to play. Say "
            "`finished: false`, or correct the Path"]))


MOD = "mods/lanternlight/the-bell-beneath.md"


class AModWithNoDryRun(unittest.TestCase):
    def mod_without_links(self):
        text = plotcanon.sample_world()[MOD]
        return (text.replace("→ [[", "(").replace("]]", ")")
                .replace("**Contest:**", "**Struggle:**"))

    def test_a_path_on_a_mod_with_no_dry_run_is_a_warning(self):
        errors, warnings = findings({FIRST: report()}, {MOD: self.mod_without_links()})

        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["has a `path`, but mod `the-bell-beneath` has no Dry Run "
                                    "to check it against — Dry Run: the body has no Dry Run "
                                    "structure — no Hook, scene or Contest links to a scene "
                                    "or outcome. See the Dry Run convention in schema/mod.md"])

    def test_no_path_on_a_mod_with_no_dry_run_says_nothing(self):
        self.assertEqual(findings({FIRST: report(None)}, {MOD: self.mod_without_links()}),
                         ([], []))


class AStretchThatContinuesAnother(unittest.TestCase):
    """A report's Path may start where the Path of the report before it on the
    same Mod stopped, instead of at a Hook."""

    def earlier(self, path=STOPPED):
        return {FIRST: report(path, finished="false")}

    def test_it_may_start_where_the_last_path_stopped(self):
        later = report("  - The bell\n  - The bell is taken\n", id="aa-the-bell-beneath-2")

        self.assertEqual(findings({SECOND: later}, self.earlier()), ([], []))

    def test_it_may_start_at_a_hook(self):
        self.assertEqual(findings({SECOND: report(id="aa-the-bell-beneath-2")}, self.earlier()),
                         ([], []))

    def test_it_may_not_start_anywhere_else(self):
        later = report("  - Who rings it\n  - The bell is rung\n", id="aa-the-bell-beneath-2")

        errors, _ = findings({SECOND: later}, self.earlier())

        self.assertEqual(errors, ["`path[0]`: a Path starts with the Hook taken "
                                  "(`hook: <the Hook>`), or where the last report's Path "
                                  "stopped (`The bell`), not at `Who rings it`"])

    def test_after_a_report_with_no_path_it_may_start_at_any_scene(self):
        later = report("  - Who rings it\n  - The bell is rung\n", id="aa-the-bell-beneath-2")

        self.assertEqual(findings({SECOND: later}, self.earlier(None)), ([], []))

    def test_a_report_on_a_mod_that_did_not_run_is_passed_over(self):
        did_not_run = report(None, id="aa-the-bell-beneath-2", ran="false", finished="false")
        later = report("  - The bell\n  - The bell is taken\n", id="aa-the-bell-beneath-3")
        third = SECOND.replace("-2", "-3")

        self.assertEqual(findings({third: later}, {**self.earlier(), SECOND: did_not_run}),
                         ([], []))

    def test_each_of_several_stretches_may_start_where_the_last_stopped(self):
        second = report("  - The bell\n  - Who rings it\n", id="aa-the-bell-beneath-2",
                        finished="false")
        third = report("  - Who rings it\n  - The bell is rung\n", id="aa-the-bell-beneath-3")

        self.assertEqual(findings({SECOND: second, SECOND.replace("-2", "-3"): third},
                                  self.earlier()), ([], []))

    def test_where_several_stretches_stopped_is_followed_from_one_to_the_next(self):
        second = report("  - The bell\n  - Who rings it\n", id="aa-the-bell-beneath-2",
                        finished="false")
        third = report("  - The bell\n  - The bell is taken\n", id="aa-the-bell-beneath-3")

        errors, _ = findings({SECOND: second, SECOND.replace("-2", "-3"): third},
                             self.earlier())

        self.assertEqual(errors, ["`path[0]`: a Path starts with the Hook taken "
                                  "(`hook: <the Hook>`), or where the last report's Path "
                                  "stopped (`Who rings it`), not at `The bell`"])


class WalkingAPath(unittest.TestCase):
    """`path_steps` writes a Path from the choices taken in a walk through a
    Dry Run, and `check_path` reads one back, as the checks on a report do."""

    @classmethod
    def setUpClass(cls):
        world = plotcanon.load_world(plotcanon.sample_world()).world
        cls.story = plotcanon.story(world.get("the-bell-beneath"))

    def walk(self, *labels, continues_from=None):
        """The choices with these labels, taken one after another."""
        here = self.story.start if continues_from is None \
            else self.story.passage(continues_from)
        choices = []
        for label in labels:
            choice = next(c for c in here.choices if c.label == label)
            choices.append(choice)
            here = self.story.passage(choice.passage)
        return choices

    def test_the_choices_taken_are_written_as_the_steps_a_report_holds(self):
        choices = self.walk("The sister asks them to close what was opened", "down the rope",
                            "follow the sound inward", "win")

        steps = plotcanon.path_steps(self.story, choices)

        self.assertEqual(steps, [
            {"hook": "The sister asks them to close what was opened"},
            "The descent",
            "The bell",
            "Who rings it",
            {"contest": "stop her before the last stroke", "result": "win"},
            "The bell is silenced",
        ])

    def test_steps_written_from_a_walk_are_what_the_check_reads(self):
        steps = plotcanon.path_steps(self.story, self.walk(
            "The diver has been to the door before, and knows a way past the sand",
            "it rings"))

        walked = plotcanon.check_path(self.story, steps)

        self.assertTrue(walked.ok)
        self.assertEqual(walked.problems, ())
        self.assertEqual(walked.end.name, "Who rings it")
        self.assertIs(walked.finished, False)

    def test_an_ending_reached_proposes_the_mod_is_finished(self):
        steps = plotcanon.path_steps(self.story, self.walk(
            "The sister asks them to close what was opened",
            "the tide gives them an hour, then the steps flood"))

        walked = plotcanon.check_path(self.story, steps)

        self.assertEqual(walked.end.kind, "ending")
        self.assertIs(walked.finished, True)

    def test_a_walk_may_continue_from_where_the_last_path_stopped(self):
        choices = self.walk("lose", continues_from="Who rings it")

        steps = plotcanon.path_steps(self.story, choices, continues_from="Who rings it")

        self.assertEqual(steps, ["Who rings it",
                                 {"contest": "stop her before the last stroke",
                                  "result": "lose"},
                                 "The bell is rung"])
        self.assertTrue(plotcanon.check_path(self.story, steps,
                                             continues_from="Who rings it").ok)

    def test_a_walk_with_no_choices_yet(self):
        self.assertEqual(plotcanon.path_steps(self.story, []), [])
        self.assertEqual(plotcanon.path_steps(self.story, [], continues_from="the bell"),
                         ["The bell"])

    def test_a_choice_that_is_not_one_of_the_ways_on_is_refused(self):
        down, *_ = self.walk("The sister asks them to close what was opened")

        with self.assertRaises(ValueError):
            plotcanon.path_steps(self.story, [down, down])

    def test_a_path_with_problems_has_no_end(self):
        walked = plotcanon.check_path(self.story, ["The belfry"])

        self.assertFalse(walked.ok)
        self.assertIsNone(walked.end)
        self.assertIsNone(walked.finished)

    def test_nothing_in_a_path_makes_the_check_raise(self):
        for steps in (None, [], "The bell", [None], [{"hook": None}], [{1: 2}],
                      [{"contest": "x", "result": ["win"]}], [[["deep"]]]):
            with self.subTest(steps=steps):
                self.assertFalse(plotcanon.check_path(self.story, steps).ok)
