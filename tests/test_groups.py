"""Parallel Groups: when a Mod splits its players at one Event, each Group's
Mod Runner files a report that says which Group it covers in `group`, and
`finished`, Paths and where play stopped follow each Group (ADR-0011 in RPG
Plot Helper). The sample World's `the-bell-beneath` is the Mod split."""

import re
import unittest

import plotcanon

MOD = "mods/lanternlight/the-bell-beneath.md"
E02, E04 = "e02-first-lantern", "e04-second-lantern"
AT = f"after-actions/{E04}/"

SILENCED = """\
  - hook: The sister asks them to close what was opened
  - The descent
  - The bell
  - Who rings it
  - contest: stop her before the last stroke
    result: win
  - The bell is silenced
"""
AT_THE_BELL = """\
  - hook: The diver has been to the door before, and knows a way past the sand
  - The bell
"""
AT_WHO_RINGS = """\
  - hook: The diver has been to the door before, and knows a way past the sand
  - The bell
  - Who rings it
"""


def rel(n, event=E04):
    return f"after-actions/{event}/{report_id(n)}.md"


def report_id(n):
    return "aa-the-bell-beneath" if n == 1 else f"aa-the-bell-beneath-{n}"


def report(n, path=SILENCED, *, group=None, finished="true", ran="true", changes="",
           event=E04):
    """The text of the `n`th report on the Mod, by its id."""
    path_field = "" if path is None else f"path:\n{path}"
    group_field = "" if group is None else f"group: {group}\n"
    return f"""\
---
id: {report_id(n)}
type: after-action
mod: the-bell-beneath
event: {event}
{group_field}ran: {ran}
finished: {finished}
mod_runner: sam
pcs: {"[]" if ran == "false" else "[pc-bram-tolliver]"}
{path_field}canon_changes: [{changes}]
---

## What Happened

## Divergences From The Mod

## Loose Ends
"""


def placed(n, text):
    """Where the `n`th report sits, by the Event its text names."""
    return rel(n, re.search(r"^event: (.*)$", text, re.M).group(1))


def loaded(*reports, changed=None):
    """`load_world` on the sample World with these `(n, text)` reports."""
    files = {**plotcanon.sample_world(), **(changed or {})}
    for n, text in reports:
        files[placed(n, text)] = text
    return plotcanon.load_world(files)


def findings(*reports, on=None, changed=None):
    """The errors and warnings on the reports given, or on the paths `on`."""
    result = loaded(*reports, changed=changed)
    paths = on or {placed(n, text) for n, text in reports}
    return ([f"{f.path}: {f.message}" for f in result.errors if f.path in paths],
            [f"{f.path}: {f.message}" for f in result.warnings if f.path in paths])


class TwoGroupsAtOneEvent(unittest.TestCase):
    def test_both_finishing_is_valid(self):
        self.assertEqual(findings((1, report(1, group="cellar")),
                                  (2, report(2, group="belfry"))), ([], []))

    def test_both_finishing_finishes_the_mod(self):
        _, warnings = findings((1, report(1, group="cellar")), (2, report(2, group="belfry")),
                               on={MOD})

        self.assertEqual(warnings, [
            f"{MOD}: `state: approved`, but its latest reports, one for each Group "
            "(`aa-the-bell-beneath` and `aa-the-bell-beneath-2`), say the mod is finished "
            "— set the state to match, or correct the reports"])

    def test_one_finishing_and_one_stopping_leaves_the_mod_with_more_to_play(self):
        finished = plotcanon.sample_world()[MOD].replace("state: approved", "state: finished")

        _, warnings = findings((1, report(1, group="cellar")),
                               (2, report(2, AT_THE_BELL, group="belfry", finished="false")),
                               on={MOD}, changed={MOD: finished})

        self.assertEqual(warnings, [
            f"{MOD}: `state: finished`, but its latest reports, one for each Group "
            "(`aa-the-bell-beneath` and `aa-the-bell-beneath-2`), say there is more to play "
            "— set the state to match, or correct the reports"])


class AReportAfterOneThatFinishedItsGroup(unittest.TestCase):
    def test_is_an_error_on_both(self):
        errors, _ = findings((1, report(1, group="cellar")), (2, report(2, group="belfry")),
                             (3, report(3, group="cellar")))

        self.assertCountEqual(errors, [
            f"{rel(1)}: says mod `the-bell-beneath` is finished, but `aa-the-bell-beneath-3` "
            "reports on it afterwards — only the last report in a Group can say "
            "`finished: true`",
            f"{rel(3)}: mod `the-bell-beneath` was finished by `aa-the-bell-beneath` — a "
            "finished mod cannot be reported on again. If there was more to play, "
            "`aa-the-bell-beneath` should say `finished: false`",
        ])

    def test_a_group_after_the_whole_mod_finished_is_an_error_as_today(self):
        errors, _ = findings((1, report(1)), (2, report(2, group="belfry")))

        self.assertIn(f"{rel(2)}: mod `the-bell-beneath` was finished by `aa-the-bell-beneath` "
                      "— a finished mod cannot be reported on again. If there was more to "
                      "play, `aa-the-bell-beneath` should say `finished: false`", errors)
        self.assertIn(f"{rel(1)}: says mod `the-bell-beneath` is finished, but "
                      "`aa-the-bell-beneath-2` reports on it afterwards — only the last report "
                      "on a mod can say `finished: true`", errors)


FROM_THE_BELL = "  - The bell\n  - The bell is taken\n"
FROM_WHO_RINGS = "  - Who rings it\n  - The bell is rung\n"


class EachGroupsPath(unittest.TestCase):
    """Each Group's Path starts where that Group last stopped, and a Group's
    first report where the whole Mod stopped before the split."""

    def test_a_groups_first_report_starts_where_the_mod_stopped_before_the_split(self):
        self.assertEqual(findings((1, report(1, AT_THE_BELL, finished="false")),
                                  (2, report(2, FROM_THE_BELL, group="cellar")),
                                  (3, report(3, FROM_THE_BELL, group="belfry"))), ([], []))

    def test_each_group_continues_from_where_it_stopped(self):
        self.assertEqual(findings(
            (1, report(1, AT_THE_BELL, group="cellar", finished="false")),
            (2, report(2, AT_WHO_RINGS, group="belfry", finished="false")),
            (3, report(3, FROM_THE_BELL, group="cellar")),
            (4, report(4, FROM_WHO_RINGS, group="belfry"))), ([], []))

    def test_a_group_may_not_continue_from_where_another_stopped(self):
        errors, _ = findings(
            (1, report(1, AT_THE_BELL, group="cellar", finished="false")),
            (2, report(2, AT_WHO_RINGS, group="belfry", finished="false")),
            (3, report(3, FROM_WHO_RINGS, group="cellar")))

        self.assertEqual(errors, [
            f"{rel(3)}: `path[0]`: a Path starts with the Hook taken (`hook: <the Hook>`), or "
            "where the last report's Path stopped (`The bell`), not at `Who rings it`"])


class ComingBackTogether(unittest.TestCase):
    """A later report with no `group` continues from the Groups that had not
    finished."""

    def test_it_continues_from_the_group_that_had_not_finished(self):
        self.assertEqual(findings(
            (1, report(1, group="cellar")),
            (2, report(2, AT_WHO_RINGS, group="belfry", finished="false")),
            (3, report(3, FROM_WHO_RINGS))), ([], []))

    def test_it_may_not_continue_from_a_group_that_had_finished(self):
        errors, _ = findings(
            (1, report(1, AT_THE_BELL, group="cellar", finished="false")),
            (2, report(2, FROM_THE_BELL, group="cellar")),
            (3, report(3, AT_WHO_RINGS, group="belfry", finished="false")),
            (4, report(4, FROM_THE_BELL)))

        self.assertEqual(errors, [
            f"{rel(4)}: `path[0]`: a Path starts with the Hook taken (`hook: <the Hook>`), or "
            "where the last report's Path stopped (`Who rings it`), not at `The bell`"])

    def test_with_two_groups_unfinished_it_starts_where_either_stopped(self):
        for path in (FROM_THE_BELL, FROM_WHO_RINGS):
            with self.subTest(path=path):
                self.assertEqual(findings(
                    (1, report(1, AT_THE_BELL, group="cellar", finished="false")),
                    (2, report(2, AT_WHO_RINGS, group="belfry", finished="false")),
                    (3, report(3, path))), ([], []))

    def test_with_two_groups_unfinished_it_may_not_start_anywhere_else(self):
        errors, _ = findings(
            (1, report(1, AT_THE_BELL, group="cellar", finished="false")),
            (2, report(2, AT_WHO_RINGS, group="belfry", finished="false")),
            (3, report(3, "  - The descent\n  - The crypt floods\n")))

        self.assertEqual(errors, [
            f"{rel(3)}: `path[0]`: a Path that brings Groups back together starts where one "
            "of the Groups that had not finished stopped (`The bell` or `Who rings it`), not "
            "at `The descent`"])

    def test_with_two_groups_unfinished_it_may_not_start_at_a_hook(self):
        errors, _ = findings(
            (1, report(1, AT_THE_BELL, group="cellar", finished="false")),
            (2, report(2, AT_WHO_RINGS, group="belfry", finished="false")),
            (3, report(3)))

        self.assertEqual(errors, [
            f"{rel(3)}: `path[0]`: a Path that brings Groups back together starts where one "
            "of the Groups that had not finished stopped (`The bell` or `Who rings it`), not "
            "with the Hook `The sister asks them to close what was opened`"])

    def test_with_one_group_unfinished_it_may_start_at_a_hook_as_after_any_one_stop(self):
        for together in (report(3), report(3, FROM_WHO_RINGS)):
            with self.subTest(together=together):
                self.assertEqual(findings(
                    (1, report(1, group="cellar")),
                    (2, report(2, AT_WHO_RINGS, group="belfry", finished="false")),
                    (3, together)), ([], []))

    def test_a_walk_that_brings_two_groups_back_together_may_not_start_at_the_premise(self):
        story = plotcanon.story(plotcanon.sample_world()[MOD])
        stop = plotcanon.LastStop(among=("The bell", "Who rings it"))

        with self.assertRaises(ValueError):
            plotcanon.path_steps(story, [story.start.exits[0]], continues_from=stop)
        self.assertEqual(plotcanon.path_steps(story, [], continues_from=stop, start="The bell"),
                         ["The bell"])

    def test_after_every_group_finished_it_is_an_error_as_today(self):
        errors, _ = findings((1, report(1, group="cellar")), (2, report(2, group="belfry")),
                             (3, report(3)))

        self.assertIn(f"{rel(3)}: mod `the-bell-beneath` was finished by `aa-the-bell-beneath` "
                      "and `aa-the-bell-beneath-2` — a finished mod cannot be reported on "
                      "again. If there was more to play, one of them should say "
                      "`finished: false`", errors)
        for n in (1, 2):
            self.assertIn(f"{rel(n)}: says mod `the-bell-beneath` is finished, but "
                          "`aa-the-bell-beneath-3` reports on it afterwards — only the last "
                          "report in a Group can say `finished: true`", errors)

    def test_a_new_split_after_coming_back_together_starts_from_there(self):
        self.assertEqual(findings(
            (1, report(1, AT_THE_BELL, group="cellar", finished="false")),
            (2, report(2, group="belfry")),
            (3, report(3, "  - The bell\n  - Who rings it\n", finished="false")),
            (4, report(4, FROM_WHO_RINGS, group="cellar")),
            (5, report(5, FROM_WHO_RINGS, group="belfry"))), ([], []))


class WhereAGroupLastStopped(unittest.TestCase):
    """`last_stop` takes a Group, so an app's walk for a Group's report starts
    where that Group stopped."""

    def world(self, *reports):
        files = plotcanon.sample_world()
        for n, text in reports:
            files[rel(n)] = text
        return files

    def split(self):
        return self.world((1, report(1, AT_THE_BELL, finished="false")),
                          (2, report(2, FROM_THE_BELL.replace("The bell is taken", "Who rings it"),
                                     group="cellar", finished="false")))

    def test_it_is_where_that_group_stopped(self):
        self.assertEqual(plotcanon.last_stop(self.split(), "the-bell-beneath", group="cellar"),
                         plotcanon.LastStop("Who rings it"))

    def test_for_a_groups_first_report_it_is_where_the_mod_stopped_before_the_split(self):
        self.assertEqual(plotcanon.last_stop(self.split(), "the-bell-beneath", group="belfry"),
                         plotcanon.LastStop("The bell"))

    def test_before_a_report_it_is_where_that_reports_group_stopped(self):
        world = self.world((1, report(1, AT_THE_BELL, group="cellar", finished="false")),
                           (2, report(2, AT_WHO_RINGS, group="belfry", finished="false")),
                           (3, report(3, FROM_THE_BELL, group="cellar")))

        self.assertEqual(plotcanon.last_stop(world, "the-bell-beneath",
                                             before="aa-the-bell-beneath-3"),
                         plotcanon.LastStop("The bell"))
        self.assertEqual(plotcanon.last_stop(world, "the-bell-beneath",
                                             before="aa-the-bell-beneath-3", group="belfry"),
                         plotcanon.LastStop("Who rings it"))

    def test_with_no_group_after_a_split_it_is_where_the_unfinished_groups_stopped(self):
        world = self.world((1, report(1, AT_THE_BELL, group="cellar", finished="false")),
                           (2, report(2, AT_WHO_RINGS, group="belfry", finished="false")))

        stop = plotcanon.last_stop(world, "the-bell-beneath")

        self.assertEqual(stop, plotcanon.LastStop(among=("The bell", "Who rings it")))
        self.assertEqual(stop.passages, ("The bell", "Who rings it"))
        self.assertTrue(stop.lets_start_at("who rings it"))
        self.assertFalse(stop.lets_start_at("The descent"))

    def test_with_no_groups_it_keeps_its_meaning(self):
        world = self.world((1, report(1, AT_THE_BELL, finished="false")))

        self.assertEqual(plotcanon.last_stop(world, "the-bell-beneath"),
                         plotcanon.LastStop("The bell"))

    def test_a_stop_among_several_scenes_names_two_or_more_and_nothing_else(self):
        for made in (dict(among=("The bell",)), dict(passage="The bell", among=("a", "b")),
                     dict(known=False, among=("a", "b"))):
            with self.subTest(made), self.assertRaises(ValueError):
                plotcanon.LastStop(**made)


class AReportInterviewThatBringsGroupsBackTogether(unittest.TestCase):
    def test_it_says_where_each_group_that_had_not_finished_stopped(self):
        mod = plotcanon.sample_world()[MOD]
        stop = plotcanon.LastStop(among=("The bell", "Who rings it"))

        for path in (["Who rings it", "The bell is rung"], None):
            with self.subTest(path=path):
                text = " ".join(plotcanon.interview_instructions(
                    "report", "web", mod=mod, path=path, continues_from=stop).split())

                self.assertIn("play stopped at `The bell` for one Group and at `Who rings it` "
                              "for another", text)


class AReportInterviewForTheWholeModAfterASplit(unittest.TestCase):
    def test_it_says_the_players_came_back_together(self):
        mod = plotcanon.sample_world()[MOD]
        files = {**plotcanon.sample_world(),
                 rel(1): report(1, AT_THE_BELL, group="cellar", finished="false")}

        after = " ".join(plotcanon.interview_instructions(
            "report", "web", world=files, mod=mod, group="").split())
        never = " ".join(plotcanon.interview_instructions(
            "report", "web", world=plotcanon.sample_world(), mod=mod, group="").split())

        self.assertIn("The players came back together after splitting into Groups", after)
        self.assertIn("Leave out `group`", after)
        self.assertNotIn("came back together", never)


class TheGroupField(unittest.TestCase):
    def test_a_group_is_a_short_label(self):
        for value in ("2", "[cellar]", "{a: b}", "''", "' '", "\"two\\nlines\"", "x" * 61):
            with self.subTest(value):
                errors, _ = findings((1, report(1, group=value)))

                self.assertEqual(errors, [f"{rel(1)}: `group` must be a short label, as text "
                                          "on one line of at most 60 characters"])

    def test_a_report_with_a_misshapen_group_is_read_as_having_none(self):
        errors, _ = findings((1, report(1, AT_THE_BELL, group="[cellar]", finished="false")),
                             (2, report(2, FROM_THE_BELL)))

        self.assertEqual(errors, [f"{rel(1)}: `group` must be a short label, as text on one "
                                  "line of at most 60 characters"])


class ReadingAGroup(unittest.TestCase):
    def test_a_label_is_its_text_stripped_and_blank_or_not_text_is_none(self):
        for value, label in (("  reef  ", "reef"), ("cellar", "cellar"), ("", None),
                             ("   ", None), (None, None), (2, None), (["cellar"], None)):
            with self.subTest(value):
                self.assertEqual(plotcanon.group_label(value), label)

    def test_a_label_that_will_not_do_says_why_as_the_file_check_does(self):
        message = ("`group` must be a short label, as text on one line of at most "
                   "60 characters")
        for value in ("x" * 61, "two\nlines", "   ", "", 2, ["cellar"], None):
            with self.subTest(value):
                self.assertEqual(plotcanon.group_label_problem(value), message)
        for value in ("cellar", "  reef  ", "x" * 60):
            with self.subTest(value):
                self.assertIsNone(plotcanon.group_label_problem(value))

    def test_a_label_is_at_most_sixty_characters(self):
        self.assertEqual(plotcanon.MAX_GROUP_CHARACTERS, 60)

    def test_a_reports_group_is_read_from_its_document(self):
        result = loaded((1, report(1, AT_THE_BELL, group="  cellar ", finished="false")))
        document = next(d for d in result.world.documents if d.id == report_id(1))
        mod = next(d for d in result.world.documents if d.id == "the-bell-beneath")

        self.assertEqual(plotcanon.group_of(document), "cellar")
        self.assertIsNone(plotcanon.group_of(mod))


def status_change(to, decision="proposed"):
    return (f"{{entity: sister-ane, kind: status, decision: {decision}, from: alive, "
            f"to: {to}, summary: Changed.}}")


NARRATIVE = "{entity: sister-ane, kind: narrative, decision: proposed, summary: Spoke.}"


class ChangesInParallel(unittest.TestCase):
    """Parallel Groups' Canon Changes are still decided in order of Event,
    then report id, then place in the report. When two Groups change the same
    field of the same entity, both reports are warned, so a Plot Master
    checks it."""

    def test_two_groups_changing_one_field_is_a_warning_on_both(self):
        _, warnings = findings(
            (1, report(1, group="cellar", changes=status_change("missing"))),
            (2, report(2, group="belfry", changes=f"{NARRATIVE}, {status_change('dead')}")))

        self.assertEqual(warnings, [
            f"{rel(1)}: `canon_changes[0]` changes `status` of `sister-ane`, as "
            "`aa-the-bell-beneath-2` does in the Group `belfry`, which played alongside this "
            "one — they are decided in order of report id, so check that they agree",
            f"{rel(2)}: `canon_changes[1]` changes `status` of `sister-ane`, as "
            "`aa-the-bell-beneath` does in the Group `cellar`, which played alongside this "
            "one — they are decided in order of report id, so check that they agree",
        ])

    def test_the_warning_carries_a_code_and_no_other_warning_does(self):
        result = loaded(
            (1, report(1, group="cellar", changes=status_change("missing"))),
            (2, report(2, group="belfry", changes=status_change("dead"))))

        clashing = {w.path for w in result.warnings
                    if w.code == plotcanon.PARALLEL_GROUPS_CLASH}
        self.assertEqual(clashing, {rel(1), rel(2)})
        self.assertEqual(plotcanon.PARALLEL_GROUPS_CLASH, "parallel-groups-clash")
        self.assertEqual(len([w for w in result.warnings if w.code is not None]), 2)

    def test_with_three_groups_each_report_is_warned_once(self):
        _, warnings = findings(
            (1, report(1, group="cellar", changes=status_change("missing"))),
            (2, report(2, group="belfry", changes=status_change("dead"))),
            (3, report(3, group="nave", changes=status_change("dead"))))

        self.assertEqual(warnings, [
            f"{rel(1)}: `canon_changes[0]` changes `status` of `sister-ane`, as "
            "`aa-the-bell-beneath-2` does in the Group `belfry` and `aa-the-bell-beneath-3` "
            "in the Group `nave`, which played alongside this one — they are decided in "
            "order of report id, so check that they agree",
            f"{rel(2)}: `canon_changes[0]` changes `status` of `sister-ane`, as "
            "`aa-the-bell-beneath` does in the Group `cellar` and `aa-the-bell-beneath-3` "
            "in the Group `nave`, which played alongside this one — they are decided in "
            "order of report id, so check that they agree",
            f"{rel(3)}: `canon_changes[0]` changes `status` of `sister-ane`, as "
            "`aa-the-bell-beneath` does in the Group `cellar` and `aa-the-bell-beneath-2` "
            "in the Group `belfry`, which played alongside this one — they are decided in "
            "order of report id, so check that they agree",
        ])

    def test_the_same_group_changing_one_field_twice_is_not(self):
        self.assertEqual(findings(
            (1, report(1, AT_THE_BELL, group="cellar", finished="false",
                       changes=status_change("missing"))),
            (2, report(2, FROM_THE_BELL, group="cellar", changes=status_change("dead")))),
            ([], []))

    def test_changes_once_the_groups_came_back_together_are_not(self):
        self.assertEqual(findings(
            (1, report(1, AT_THE_BELL, group="cellar", finished="false",
                       changes=status_change("missing"))),
            (2, report(2, AT_THE_BELL, group="belfry", finished="false")),
            (3, report(3, FROM_THE_BELL, changes=status_change("dead")))), ([], []))

    def test_prose_changes_and_rejected_ones_are_not(self):
        self.assertEqual(findings(
            (1, report(1, group="cellar", changes=f"{NARRATIVE}, "
                                                  f"{status_change('dead', 'rejected')}")),
            (2, report(2, group="belfry", changes=f"{NARRATIVE}, {status_change('missing')}"))),
            ([], []))


class TheSchemaDoc(unittest.TestCase):
    """`schema/after-action.md` describes `group`, with an example of two
    Groups at one Event, one finishing and one stopping, and a later report
    with no `group` that brings them back together."""

    @classmethod
    def setUpClass(cls):
        import re

        import yaml

        mod = plotcanon.schema_files()["mod.md"]
        start = mod.index("```markdown\n") + len("```markdown\n")
        cls.story = plotcanon.story(mod[start:mod.rindex("```")])
        cls.doc = plotcanon.schema_files()["after-action.md"]
        section = cls.doc[cls.doc.index("## `group`"):cls.doc.index("## `canon_changes`")]
        cls.reports = [yaml.safe_load(b) for b in re.findall(r"```yaml\n(.*?)```", section, re.S)]

    def test_it_describes_the_field(self):
        self.assertIn("| `group` | ○ |", self.doc)

    def test_its_example_splits_and_comes_back_together(self):
        finishing, stopping, together = self.reports
        nave = plotcanon.check_path(self.story, finishing["path"])
        door = plotcanon.check_path(self.story, stopping["path"])
        later = plotcanon.check_path(self.story, together["path"],
                                     continues_from=door.end.name)

        self.assertNotEqual(finishing["group"], stopping["group"])
        self.assertEqual((finishing["finished"], nave.finished), (True, True))
        self.assertEqual((stopping["finished"], door.finished), (False, False))
        self.assertNotIn("group", together)
        self.assertEqual(later.problems, ())
        self.assertFalse(plotcanon.check_path(self.story, together["path"],
                                              continues_from=nave.end.name).ok)

    def test_its_example_splits_at_one_event_and_comes_back_together_at_a_later_one(self):
        finishing, stopping, together = self.reports

        self.assertEqual(finishing["event"], stopping["event"])
        self.assertNotEqual(together["event"], stopping["event"])


class AModWithManyReports(unittest.TestCase):
    """Reading a Mod's lines of play takes one pass over its reports, so a
    Mod with no `group` on any report checks however many reports it has."""

    def test_a_thousand_reports_check_without_error(self):
        reports = [(1, report(1, AT_THE_BELL, finished="false"))]
        reports += [(n, report(n, "  - The bell\n", finished="false")) for n in range(2, 1001)]

        self.assertEqual(list(loaded(*reports).errors), [])

    def test_a_thousand_reports_that_did_not_run_check_without_error(self):
        reports = [(1, report(1, AT_THE_BELL, finished="false"))]
        reports += [(n, report(n, None, finished="false", ran="false"))
                    for n in range(2, 1001)]
        reports += [(1001, report(1001, FROM_THE_BELL))]

        self.assertEqual(list(loaded(*reports).errors), [])


AT_TWO_EVENTS = {MOD: plotcanon.sample_world()[MOD].replace(
    "events: [e04-second-lantern]", f"events: [{E02}, {E04}]")}


def at_two(*reports, on=None):
    """`findings` on the Mod run at two Events, `E02` and then `E04`."""
    return findings(*reports, on=on, changed=AT_TWO_EVENTS)


class GroupsAtMoreThanOneEvent(unittest.TestCase):
    """Groups are parallel at one Event. At a later Event, the Groups of the
    last one have come back together: a Group there, whatever its label,
    starts where the Mod stood at the end of the last Event."""

    def split_at_e02(self, cellar=AT_THE_BELL, cellar_finished="false"):
        return ((1, report(1, cellar, group="cellar", finished=cellar_finished, event=E02)),
                (2, report(2, AT_WHO_RINGS, group="belfry", finished="false", event=E02)))

    def test_with_no_groups_reports_at_two_events_read_as_before(self):
        self.assertEqual(at_two((1, report(1, AT_THE_BELL, finished="false", event=E02)),
                                (2, report(2, FROM_THE_BELL))), ([], []))

    def test_a_group_at_a_later_event_starts_where_the_mod_stood_at_the_end_of_the_last(self):
        self.assertEqual(at_two((1, report(1, AT_THE_BELL, group="cellar", finished="false",
                                           event=E02)),
                                (2, report(2, FROM_THE_BELL, group="belfry"))), ([], []))

    def test_after_two_groups_stopped_a_group_at_a_later_event_starts_where_either_did(self):
        for path in (FROM_THE_BELL, FROM_WHO_RINGS):
            with self.subTest(path=path):
                self.assertEqual(at_two(*self.split_at_e02(),
                                        (3, report(3, path, group="nave"))), ([], []))

    def test_a_label_at_a_later_event_is_a_new_group(self):
        self.assertEqual(at_two(*self.split_at_e02(SILENCED, "true"),
                                (3, report(3, FROM_WHO_RINGS, group="cellar"))), ([], []))

    def test_groups_at_different_events_did_not_play_side_by_side(self):
        self.assertEqual(at_two(
            (1, report(1, AT_THE_BELL, group="cellar", finished="false", event=E02,
                       changes=status_change("missing"))),
            (2, report(2, FROM_THE_BELL, group="belfry", changes=status_change("dead")))),
            ([], []))

    def test_after_every_group_at_an_event_finished_a_later_group_is_an_error(self):
        errors, _ = at_two((1, report(1, group="cellar", event=E02)),
                           (2, report(2, group="belfry", event=E02)),
                           (3, report(3, group="cellar")))

        self.assertIn(f"{rel(3)}: mod `the-bell-beneath` was finished by `aa-the-bell-beneath` "
                      "and `aa-the-bell-beneath-2` — a finished mod cannot be reported on "
                      "again. If there was more to play, one of them should say "
                      "`finished: false`", errors)

    def test_the_mod_is_finished_when_every_group_at_its_latest_event_finished(self):
        _, warnings = at_two(*self.split_at_e02(),
                             (3, report(3, FROM_WHO_RINGS, group="nave")),
                             (4, report(4, FROM_THE_BELL, group="crypt")), on={MOD})

        self.assertEqual(warnings, [
            f"{MOD}: `state: approved`, but its latest reports, one for each Group "
            "(`aa-the-bell-beneath-3` and `aa-the-bell-beneath-4`), say the mod is finished "
            "— set the state to match, or correct the reports"])

    def test_where_a_group_at_a_later_event_starts(self):
        files = {**plotcanon.sample_world(), **AT_TWO_EVENTS}
        for n, text in self.split_at_e02():
            files[placed(n, text)] = text

        self.assertEqual(plotcanon.last_stop(files, "the-bell-beneath", group="cellar"),
                         plotcanon.LastStop("The bell"))
        self.assertEqual(plotcanon.last_stop(files, "the-bell-beneath", group="cellar",
                                             event=E04),
                         plotcanon.LastStop(among=("The bell", "Who rings it")))
        self.assertEqual(plotcanon.last_stop(files, "the-bell-beneath", group="cellar",
                                             event=E02),
                         plotcanon.LastStop("The bell"))


class FlagsOnASplitMod(unittest.TestCase):
    """A report finishes its own Mod, and so does not flag it, only when every
    Group at the Mod's latest Event has finished with it."""

    def flagged(self, *filed, submitted):
        result = loaded(*filed)
        self.assertEqual(list(result.errors), [])
        n, text = submitted
        checked = plotcanon.check_file(result.world, placed(n, text), text)
        self.assertTrue(checked.ok, checked.text())
        return "the-bell-beneath" in plotcanon.flagged_mods(result.world, checked.document)

    def test_a_group_finishing_while_another_has_more_to_play_flags_its_mod(self):
        self.assertTrue(self.flagged(
            (1, report(1, AT_WHO_RINGS, group="belfry", finished="false")),
            submitted=(2, report(2, group="cellar", changes=NARRATIVE))))

    def test_the_last_group_to_finish_does_not_flag_its_mod(self):
        self.assertFalse(self.flagged(
            (1, report(1, group="belfry")),
            submitted=(2, report(2, group="cellar", changes=NARRATIVE))))

    def test_a_report_with_no_group_that_finishes_does_not_flag_its_mod(self):
        self.assertFalse(self.flagged(submitted=(1, report(1, changes=NARRATIVE))))


class AReportInterviewExplainsGroup(unittest.TestCase):
    def test_it_explains_the_optional_group_field(self):
        mod = plotcanon.sample_world()[MOD]
        import yaml

        for path in (yaml.safe_load(SILENCED), None):
            with self.subTest(path=path):
                text = " ".join(plotcanon.interview_instructions(
                    "report", "web", mod=mod, path=path).split())

                self.assertIn("**`group`** is only for a Stretch played by one of several "
                              "Groups the players split into at this Event", text)
