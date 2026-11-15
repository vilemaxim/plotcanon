"""Canon Changes made during an Interlude, with no Mod run: the
`interlude-changes` document.

The example World has two Events. Each test adds an Interlude after them, in
which Varen, missing as of Hollow Night, is found dead.
"""

import unittest

import plotcanon
from tests.test_world_rules import ValidatorTest

INTERLUDE = """---
id: e03-the-long-frost
type: event
campaign: greymoor
ordinal: 3
period_type: interlude
aliases: ["The Long Frost"]
real_date: 2026-03-23
in_world: "the weeks after Hollow Night"
status: complete
---
"""

RECORD = "interludes/e03-the-long-frost/ic-the-long-frost.md"
CHANGES = """---
id: ic-the-long-frost
type: interlude-changes
event: e03-the-long-frost
recorded_by: mira
canon_changes:
  - entity: varen-ashcroft
    kind: status
    from: missing
    to: dead
    decision: approved
    summary: Found frozen on the moor road.
---

The thaw turned up more than anyone wanted.
"""
VAREN = "canon/npcs/varen-ashcroft.md"


class InterludeTest(ValidatorTest):
    def setUp(self):
        super().setUp()
        self.restore_examples()
        self.write("canon/events/e03-the-long-frost.md", INTERLUDE)

    def applied(self):
        """Varen's file brought up to date with the change."""
        self.edit(VAREN, "status: missing", "status: dead")
        self.edit(VAREN, "as_of: e02-hollow-night", "as_of: e03-the-long-frost")


class RecordingChanges(InterludeTest):
    def test_an_applied_change_in_an_interlude_is_clean(self):
        self.write(RECORD, CHANGES)
        self.applied()

        result = self.validate()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(list(result.report.warnings), [], result.stdout)
        self.assertEqual(result.report.world.get("ic-the-long-frost").type, "interlude-changes")

    def test_an_approved_change_not_yet_applied_is_warned_about(self):
        self.write(RECORD, CHANGES)

        result = self.validate()

        self.assertIn(f"{VAREN}: `status` is 'missing' but the latest approved status change "
                      f"({RECORD})", result.stdout)

    def test_a_proposed_change_is_not_canon(self):
        self.write(RECORD, CHANGES.replace("decision: approved", "decision: proposed"))

        result = self.validate()

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("approved but not applied", result.stdout)

    def test_its_changes_are_checked_as_a_reports_are(self):
        self.write(RECORD, CHANGES.replace("to: dead", "to: sleeping"))

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{RECORD}: canon_changes[0].to: `sleeping` is not in vocabulary "
                      f"`npc_status`", result.stdout)

    def test_it_must_say_who_recorded_it(self):
        self.write(RECORD, CHANGES.replace("recorded_by: mira\n", ""))

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{RECORD}: missing required field `recorded_by`", result.stdout)

    def test_its_changes_count_in_the_chain_of_changes_to_a_field(self):
        # A later report that moves Varen on from where the Interlude left him
        # reads its `from` against the Interlude's change.
        self.write(RECORD, CHANGES)
        self.applied()

        state = plotcanon.load_world(self.root)
        self.assertTrue(state.ok, state.text())
        self.assertIn("ic-the-long-frost", [d.id for d in state.world.of_type("interlude-changes")])


class WhereItBelongs(InterludeTest):
    def test_it_lives_under_its_interlude(self):
        self.write("interludes/e02-hollow-night/ic-the-long-frost.md", CHANGES)

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("must live in interludes/e03-the-long-frost/, not interludes/"
                      "e02-hollow-night/", result.stdout)

    def test_its_event_must_be_an_interlude(self):
        self.write("interludes/e02-hollow-night/ic-the-long-frost.md",
                   CHANGES.replace("event: e03-the-long-frost", "event: e02-hollow-night"))

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`event: e02-hollow-night` is not an Interlude", result.stdout)

    def test_its_event_must_exist(self):
        self.write("interludes/e09-nowhere/ic-the-long-frost.md",
                   CHANGES.replace("event: e03-the-long-frost", "event: e09-nowhere"))

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`event: e09-nowhere` does not resolve", result.stdout)


class Flagging(unittest.TestCase):
    """In the sample World, the warrant Mod is approved and features Harrow
    Dunmore. An Interlude after its last Event finds him dead."""

    def world_with(self, decision="approved"):
        files = plotcanon.sample_world()
        files["canon/events/e05-the-quiet-month.md"] = (
            INTERLUDE.replace("e03-the-long-frost", "e05-the-quiet-month")
            .replace("greymoor", "lanternlight").replace("ordinal: 3", "ordinal: 5"))
        files["interludes/e05-the-quiet-month/ic-the-quiet-month.md"] = (
            CHANGES.replace("e03-the-long-frost", "e05-the-quiet-month")
            .replace("ic-the-long-frost", "ic-the-quiet-month")
            .replace("varen-ashcroft", "harrow-dunmore").replace("from: missing", "from: alive")
            .replace(f"decision: approved", f"decision: {decision}"))
        state = plotcanon.load_world(files)
        self.assertTrue(state.ok, state.text())
        return state.world

    def test_a_change_flags_the_unfinished_mods_featuring_what_it_changes(self):
        world = self.world_with()

        flagged = plotcanon.flagged_mods(world, world.get("ic-the-quiet-month"))

        self.assertIn("a-warrant-for-dunmore", flagged)

    def test_a_rejected_change_flags_nothing(self):
        world = self.world_with("rejected")

        self.assertEqual(plotcanon.flags(world, world.get("ic-the-quiet-month")), [])


class Describing(unittest.TestCase):
    def test_its_schema_is_published(self):
        self.assertIn("interlude-changes.md", plotcanon.schema_files())

    def test_the_pov_bundle_shows_interlude_changes(self):
        files = plotcanon.sample_world()
        files["canon/events/e05-the-quiet-month.md"] = (
            INTERLUDE.replace("e03-the-long-frost", "e05-the-quiet-month")
            .replace("greymoor", "lanternlight").replace("ordinal: 3", "ordinal: 5"))
        files["interludes/e05-the-quiet-month/ic-the-quiet-month.md"] = (
            CHANGES.replace("e03-the-long-frost", "e05-the-quiet-month")
            .replace("ic-the-long-frost", "ic-the-quiet-month")
            .replace("varen-ashcroft", "harrow-dunmore").replace("from: missing", "from: alive"))
        from plotcanon import _pov

        subject, items, backlinks, by_id = _pov.build(files, "harrow-dunmore")
        bundle = "\n".join(_pov.emit_markdown(subject, items, backlinks, by_id, None, []))

        self.assertIn("ic-the-quiet-month", bundle)
        self.assertIn("Found frozen on the moor road.", bundle)
