"""The sample World and its scripted After-Action Reports.

The sample is test data for larp-llm and for the web app, and the demo World a
new user is given. These tests check that it is a valid World of the promised
size, and that each scripted report flags exactly the Mods it says it does.
"""

import unittest

import plotcanon


class TheSampleWorld(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = plotcanon.load_world(plotcanon.sample_world())
        cls.world = cls.report.world

    def test_it_is_valid_with_nothing_for_a_person_to_judge(self):
        self.assertEqual(self.report.text(), "")
        self.assertTrue(self.report.ok)

    def test_it_is_big_enough_to_be_worth_testing_against(self):
        count = lambda kind: len(self.world.of_type(kind))  # noqa: E731

        self.assertEqual(
            {kind: count(kind) for kind in ("campaign", "event", "faction", "npc", "location",
                                            "pc", "plot", "mod", "after-action")},
            {"campaign": 2, "event": 4, "faction": 3, "npc": 12, "location": 4,
             "pc": 5, "plot": 3, "mod": 11, "after-action": 4})

    def test_it_has_two_campaigns_each_with_events_and_mods(self):
        campaigns = [c.id for c in self.world.of_type("campaign")]

        self.assertEqual(len(campaigns), 2)
        for campaign in campaigns:
            with self.subTest(campaign):
                events = [e for e in self.world.of_type("event")
                          if e.fields["campaign"] == campaign]
                mods = [m for m in self.world.of_type("mod")
                        if m.fields.get("campaign") == campaign]
                self.assertGreaterEqual(len(events), 2)
                self.assertGreaterEqual(len(mods), 3)

    def test_its_mods_are_in_every_state(self):
        states = {m.fields["state"] for m in self.world.of_type("mod")}

        self.assertEqual(states, {"draft", "approved", "in-progress", "finished", "shelved"})

    def test_it_already_has_history(self):
        """Some play has happened, so there are approved canon changes to show."""
        decisions = [change["decision"] for report in self.world.of_type("after-action")
                     for change in report.fields["canon_changes"]]

        self.assertIn("approved", decisions)
        self.assertGreaterEqual(len(self.world.of_type("after-action")), 3)

    def test_it_comes_back_fresh_each_time(self):
        files = plotcanon.sample_world()
        files.clear()

        self.assertTrue(plotcanon.sample_world())


class TheScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Submit the script in order. After each report its Mod's state is
        brought up to date, as the Plot Master or the app would do, so each
        report is checked against the World as it stands when it arrives."""
        cls.world = plotcanon.load_world(plotcanon.sample_world()).world
        cls.script = plotcanon.sample_script()
        cls.checked, cls.world_at = {}, {}
        files = plotcanon.sample_world()
        for scripted in cls.script:
            world = plotcanon.load_world(files).world
            report = plotcanon.check_file(world, scripted.path, scripted.text)
            cls.checked[scripted.path], cls.world_at[scripted.path] = report, world
            files[scripted.path] = scripted.text
            mod = world.get(report.document.fields["mod"])
            state = "finished" if report.document.fields["finished"] else "in-progress"
            files[mod.path] = files[mod.path].replace(
                f"state: {mod.fields['state']}", f"state: {state}")
        cls.files_after = files

    def campaign_of(self, mod_id):
        return self.world.get(mod_id).fields.get("campaign")

    def changes(self, scripted):
        return self.checked[scripted.path].document.fields["canon_changes"]

    def test_the_reports_come_in_the_order_they_are_to_be_submitted(self):
        self.assertEqual([s.path.rsplit("/", 1)[-1] for s in self.script], [
            "aa-the-tax-collectors-ledger-2.md",
            "aa-blood-on-the-salt-stair.md",
            "aa-storm-moon-vigil.md",
            "aa-storm-moon-vigil-2.md",
            "aa-what-the-keeper-saw.md",
        ])

    def test_they_are_still_valid_when_submitted_one_after_another(self):
        files = plotcanon.sample_world()
        for scripted in self.script:
            with self.subTest(scripted.path):
                self.assertEqual(plotcanon.check_file(files, scripted.path, scripted.text).text(), "")
                files[scripted.path] = scripted.text
        after = plotcanon.load_world(files)
        self.assertEqual(after.errors, ())
        # What is left for the Plot Master: each Mod the reports moved on needs
        # its state set to match.
        self.assertEqual(sorted(w.path.rsplit("/", 1)[-1] for w in after.warnings),
                         ["blood-on-the-salt-stair.md", "storm-moon-vigil.md",
                          "what-the-keeper-saw.md"])

    def test_with_each_mods_state_kept_up_to_date_nothing_is_left_to_judge(self):
        self.assertEqual(plotcanon.load_world(self.files_after).text(), "")

    def test_a_mod_finished_by_one_report_is_not_flagged_by_the_next(self):
        by_name = {s.path.rsplit("/", 1)[-1]: s for s in self.script}

        self.assertTrue(by_name["aa-blood-on-the-salt-stair.md"].finishes)
        self.assertNotIn("blood-on-the-salt-stair", by_name["aa-storm-moon-vigil.md"].flags)

    def test_some_mods_say_what_they_need_and_what_they_expect(self):
        mods = self.world.of_type("mod")

        self.assertTrue([m for m in mods if m.fields.get("requires")])
        self.assertTrue([m for m in mods if m.fields.get("expected_changes")])

    def test_none_of_them_is_in_the_world_yet(self):
        for scripted in self.script:
            self.assertNotIn(scripted.path, self.world.files)

    def test_each_is_a_valid_report_against_the_world(self):
        for scripted in self.script:
            with self.subTest(scripted.path):
                report = self.checked[scripted.path]
                self.assertEqual(report.text(), "")
                self.assertEqual(report.document.type, "after-action")

    def test_every_change_they_make_is_only_proposed(self):
        for scripted in self.script:
            with self.subTest(scripted.path):
                self.assertEqual({c["decision"] for c in self.changes(scripted)}, {"proposed"})

    def test_each_flags_exactly_the_mods_it_says_it_does(self):
        for scripted in self.script:
            with self.subTest(scripted.path):
                document = self.checked[scripted.path].document
                self.assertEqual(plotcanon.flagged_mods(self.world_at[scripted.path], document),
                                 sorted(scripted.flags))

    def test_each_explains_itself(self):
        for scripted in self.script:
            with self.subTest(scripted.path):
                self.assertTrue(scripted.summary.strip())

    def test_one_interrupts_a_mod_that_has_more_to_play(self):
        interrupting = [s for s in self.script if s.interrupts]

        self.assertTrue(interrupting)
        for scripted in interrupting:
            self.assertIs(self.checked[scripted.path].document.fields["finished"], False)
        again = [s for s in interrupting
                 if self.world.get(self.checked[s.path].document.fields["mod"]).fields["state"]
                 == "in-progress"]
        self.assertTrue(again, "one interrupts a Mod that was already interrupted once")

    def test_each_flag_names_the_change_and_the_feature_that_raised_it(self):
        for scripted in self.script:
            with self.subTest(scripted.path):
                document = self.checked[scripted.path].document
                flags = plotcanon.flags(self.world_at[scripted.path], document)
                changes = document.fields["canon_changes"]
                self.assertEqual(sorted({f.mod for f in flags}), sorted(scripted.flags))
                for flag in flags:
                    self.assertEqual(changes[flag.change]["entity"], flag.entity)
                    featured = self.world.get(flag.mod).fields["features"]
                    self.assertIn(flag.entity, [e for ids in featured.values() for e in ids])

    def test_no_report_is_filed_at_an_event_that_has_not_started(self):
        for scripted in self.script:
            event = self.world.get(self.checked[scripted.path].document.fields["event"])
            self.assertNotEqual(event.fields["status"], "planned", scripted.path)

    def test_one_flags_a_mod_in_another_campaign(self):
        crossing = [
            s for s in self.script
            if any(self.campaign_of(flagged) not in (None, self.campaign_of(
                self.checked[s.path].document.fields["mod"])) for flagged in s.flags)
        ]

        self.assertTrue(crossing)

    def test_one_finishes_a_mod_and_says_so(self):
        finishing = [s for s in self.script if s.finishes]

        self.assertTrue(finishing)
        for scripted in self.script:
            with self.subTest(scripted.path):
                document = self.checked[scripted.path].document
                self.assertIs(document.fields["finished"], scripted.finishes)
                self.assertFalse(scripted.finishes and scripted.interrupts)

    def test_a_report_that_finishes_its_mod_never_flags_it(self):
        for scripted in self.script:
            mod = self.checked[scripted.path].document.fields["mod"]
            if scripted.finishes:
                self.assertNotIn(mod, scripted.flags, scripted.path)

    def test_one_flags_nothing_at_all(self):
        self.assertTrue([s for s in self.script if s.flags == ()])

    def test_one_flags_a_draft_and_none_flags_a_finished_or_shelved_mod(self):
        flagged = {mod for s in self.script for mod in s.flags}
        states = {self.world.get(mod).fields["state"] for mod in flagged}

        self.assertIn("draft", states)
        self.assertFalse(states & {"finished", "shelved"})

    def test_a_pair_contradict_each_other_about_the_same_npc(self):
        by_path = {s.path: s for s in self.script}
        pairs = [(s, by_path[other]) for s in self.script for other in s.contradicts]

        self.assertTrue(pairs)
        for one, other in pairs:
            with self.subTest(one.path):
                self.assertIn(one.path, other.contradicts)
                status = lambda s: {c["entity"]: c["to"] for c in self.changes(s)  # noqa: E731
                                    if c["kind"] == "status"}
                clashes = [entity for entity in status(one).keys() & status(other).keys()
                           if status(one)[entity] != status(other)[entity]]
                self.assertTrue(clashes)
                self.assertEqual(self.world.get(clashes[0]).type, "npc")


class FlaggedMods(unittest.TestCase):
    """The rule, on a World small enough to read: a proposed canon change
    flags every unfinished Mod that features the entity it changes."""

    WORLD = {
        "canon/campaigns/north.md": "---\nid: north\ntype: campaign\naliases: [North]\n---\n",
        "canon/campaigns/south.md": "---\nid: south\ntype: campaign\naliases: [South]\n---\n",
        "canon/events/e01.md": ("---\nid: e01\ntype: event\ncampaign: north\nordinal: 1\n"
                                "period_type: event\naliases: [One]\nreal_date: 2026-01-01\n"
                                "in_world: spring\nstatus: complete\n---\n"),
        "canon/events/e02.md": ("---\nid: e02\ntype: event\ncampaign: south\nordinal: 2\n"
                                "period_type: event\naliases: [Two]\nreal_date: 2026-02-01\n"
                                "in_world: summer\nstatus: planned\n---\n"),
        "canon/npcs/the-baron.md": ("---\nid: the-baron\ntype: npc\naliases: [The Baron]\n"
                                    "status: alive\nas_of: e01\ncanon: approved\n"
                                    "visibility: gm-only\n---\n"),
        "canon/npcs/the-cook.md": ("---\nid: the-cook\ntype: npc\naliases: [The Cook]\n"
                                   "status: alive\nas_of: e01\ncanon: approved\n"
                                   "visibility: gm-only\n---\n"),
        "canon/pcs/pc-ada.md": ("---\nid: pc-ada\ntype: pc\naliases: [Ada]\nplayer: sam\n"
                                "canon: approved\nvisibility: gm-only\n---\n"),
    }

    def mod(self, mod_id, state, features, campaign="north", events="[e01]"):
        folder = {"draft": "inbox", "shelved": "mods/shelved"}.get(state, f"mods/{campaign}")
        canon = "proposed" if state == "draft" else "approved"
        return f"{folder}/{mod_id}.md", (
            f"---\nid: {mod_id}\ntype: mod\ntitle: {mod_id}\naliases: [{mod_id}]\n"
            f"mod_writer: mira\nstate: {state}\ncampaign: {campaign}\nevents: {events}\n"
            f"canon: {canon}\nvisibility: gm-only\nfeatures:\n  npcs: {features}\n---\n")

    def test_a_rejected_change_flags_nothing_but_an_approved_one_still_does(self):
        mods = [self.mod("the-hunt", "finished", "[the-cook]"),
                self.mod("the-feast", "approved", "[the-baron]")]

        self.assertEqual(self.flagged_by(["the-baron"], mods, decision="rejected"), [])
        self.assertEqual(self.flagged_by(["the-baron"], mods, decision="approved"), ["the-feast"])

    def test_each_flag_says_which_change_touched_which_feature(self):
        files = dict(self.WORLD)
        files.update(dict([self.mod("the-hunt", "finished", "[the-cook]"),
                           self.mod("the-feast", "approved", "[the-baron, the-cook]"),
                           self.mod("the-wake", "approved", "[the-baron]")]))
        world = plotcanon.load_world(files).world
        report = plotcanon.check_file(
            world, "after-actions/e01/aa-the-hunt.md",
            "---\nid: aa-the-hunt\ntype: after-action\nmod: the-hunt\nevent: e01\nran: true\nfinished: true\n"
            "mod_runner: alex\npcs: [pc-ada]\ncanon_changes:\n"
            "  - {entity: the-cook, kind: narrative, decision: proposed, summary: Burnt it.}\n"
            "  - {entity: the-baron, kind: narrative, decision: proposed, summary: Left early.}\n"
            "---\n").document

        flags = plotcanon.flags(world, report)

        self.assertEqual([(f.mod, f.change, f.entity) for f in flags], [
            ("the-feast", 0, "the-cook"),
            ("the-feast", 1, "the-baron"),
            ("the-wake", 1, "the-baron"),
        ])

    def test_a_report_that_finishes_its_own_mod_does_not_flag_it(self):
        mods = [self.mod("the-hunt", "in-progress", "[the-baron]"),
                self.mod("the-feast", "approved", "[the-baron]")]

        self.assertEqual(self.flagged_by(["the-baron"], mods, finished="true"), ["the-feast"])
        self.assertEqual(self.flagged_by(["the-baron"], mods, finished="false"),
                         ["the-feast", "the-hunt"])

    def flagged_by(self, changes, mods, decision="proposed", finished="false"):
        files = dict(self.WORLD)
        files.update(dict(mods))
        loaded = plotcanon.load_world(files)
        self.assertTrue(loaded.ok, loaded.text())
        listed = "".join(f"\n  - entity: {entity}\n    kind: narrative\n    decision: {decision}\n"
                         f"    summary: Something happened." for entity in changes) or " []"
        checked = plotcanon.check_file(
            loaded.world, "after-actions/e01/aa-the-hunt.md",
            "---\nid: aa-the-hunt\ntype: after-action\nmod: the-hunt\nevent: e01\nran: true\n"
            f"finished: {finished}\nmod_runner: alex\npcs: [pc-ada]\n"
            f"canon_changes:{listed}\n---\n")
        self.assertTrue(checked.ok, checked.text())
        return plotcanon.flagged_mods(loaded.world, checked.document)

    def test_an_unfinished_mod_that_features_the_changed_entity_is_flagged(self):
        flagged = self.flagged_by(["the-baron"], [
            self.mod("the-hunt", "finished", "[the-cook]"),
            self.mod("the-feast", "approved", "[the-baron]"),
        ])

        self.assertEqual(flagged, ["the-feast"])

    def test_a_mod_that_does_not_feature_it_is_not(self):
        flagged = self.flagged_by(["the-baron"], [
            self.mod("the-hunt", "finished", "[the-cook]"),
            self.mod("the-feast", "approved", "[the-cook]"),
        ])

        self.assertEqual(flagged, [])

    def test_drafts_and_mods_in_progress_count_as_unfinished(self):
        flagged = self.flagged_by(["the-baron"], [
            self.mod("the-hunt", "finished", "[the-cook]"),
            self.mod("a-draft", "draft", "[the-baron]"),
            self.mod("a-running-one", "in-progress", "[the-baron]"),
        ])

        self.assertEqual(flagged, ["a-draft", "a-running-one"])

    def test_finished_and_shelved_mods_are_never_flagged(self):
        flagged = self.flagged_by(["the-baron"], [
            self.mod("the-hunt", "finished", "[the-baron]"),
            self.mod("a-shelved-one", "shelved", "[the-baron]", events="[]"),
        ])

        self.assertEqual(flagged, [])

    def test_a_mod_in_another_campaign_is_flagged_too(self):
        flagged = self.flagged_by(["the-baron"], [
            self.mod("the-hunt", "finished", "[the-cook]"),
            self.mod("southern-affair", "approved", "[the-baron]", campaign="south",
                     events="[e02]"),
        ])

        self.assertEqual(flagged, ["southern-affair"])

    def test_the_reports_own_mod_is_flagged_if_it_has_more_to_play(self):
        flagged = self.flagged_by(["the-baron"], [
            self.mod("the-hunt", "in-progress", "[the-baron]"),
        ], finished="false")

        self.assertEqual(flagged, ["the-hunt"])

    def test_a_mod_is_listed_once_however_many_changes_touch_it(self):
        flagged = self.flagged_by(["the-baron", "the-cook", "the-baron"], [
            self.mod("the-hunt", "finished", "[the-cook]"),
            self.mod("the-feast", "approved", "[the-baron, the-cook]"),
        ])

        self.assertEqual(flagged, ["the-feast"])

    def test_the_result_of_checking_a_file_can_be_passed_straight_in(self):
        files = dict(self.WORLD)
        files.update(dict([self.mod("the-hunt", "finished", "[the-cook]"),
                           self.mod("the-feast", "approved", "[the-baron]")]))
        world = plotcanon.load_world(files).world
        checked = plotcanon.check_file(
            world, "after-actions/e01/aa-the-hunt.md",
            "---\nid: aa-the-hunt\ntype: after-action\nmod: the-hunt\nevent: e01\nran: true\nfinished: true\n"
            "mod_runner: alex\npcs: [pc-ada]\ncanon_changes:\n"
            "  - {entity: the-baron, kind: narrative, decision: proposed, summary: Left early.}\n"
            "---\n")

        self.assertEqual(plotcanon.flagged_mods(world, checked), ["the-feast"])

    def test_a_report_that_failed_its_check_is_refused_with_a_reason(self):
        world = plotcanon.load_world(dict(self.WORLD)).world
        failed = plotcanon.check_file(world, "after-actions/e01/aa-x.md", "not a report")

        with self.assertRaisesRegex(TypeError, "has errors"):
            plotcanon.flags(world, failed)

    def test_a_report_with_no_changes_flags_nothing(self):
        flagged = self.flagged_by([], [
            self.mod("the-hunt", "finished", "[the-cook]"),
            self.mod("the-feast", "approved", "[the-baron]"),
        ])

        self.assertEqual(flagged, [])


if __name__ == "__main__":
    unittest.main()
