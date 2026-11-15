"""A World's rules, checked through `plotcanon.load_world`.

Each test builds a World in a temp directory (the example canon, plus or minus a
few edits), loads it, and checks what the report says.

Run with:  uv run python -m unittest discover tests
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import plotcanon

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class ValidatorTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)

    def restore_examples(self):
        for part in ("canon", "mods", "after-actions"):
            shutil.copytree(EXAMPLES / part, self.root / part)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def edit(self, rel, old, new):
        path = self.root / rel
        before = path.read_text()
        self.assertEqual(before.count(old), 1, f"{rel} should contain {old!r} once")
        path.write_text(before.replace(old, new))

    def validate(self):
        """Load the World and return what a person would be shown: the findings
        and the summary line as `stdout`, and 1 as `returncode` if any is an error."""
        report = plotcanon.load_world(self.root)
        stdout = f"{report.text()}\n\n{report.summary()}\n"
        return SimpleNamespace(stdout=stdout, returncode=0 if report.ok else 1, report=report)


class ExampleCanon(ValidatorTest):
    def test_restored_examples_are_clean(self):
        self.restore_examples()

        result = self.validate()

        self.assertIn("7 documents · 0 errors · 0 warnings", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)


PLOT = """---
id: the-ashcroft-debt
type: plot
aliases: ["The Ashcroft Debt"]
status: open
as_of: e02-hollow-night
entities: [varen-ashcroft]
mods: [the-ashen-vigil]
canon: approved
visibility: gm-only
---

## Premise

What Varen owes, and to whom.

## Current State

## Where It Could Go

## GM Notes
"""


class Plots(ValidatorTest):
    def test_a_plot_that_lists_its_mods_is_valid(self):
        self.restore_examples()
        self.write("canon/plots/the-ashcroft-debt.md", PLOT)
        npc = self.root / "canon/npcs/varen-ashcroft.md"
        before = npc.read_text()
        after = before.replace("owner: alex", "plots: [the-ashcroft-debt]\nowner: alex")
        self.assertNotEqual(before, after, "example NPC no longer has an owner line")
        npc.write_text(after)

        result = self.validate()

        self.assertIn("8 documents · 0 errors · 0 warnings", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_plot_naming_a_mod_that_does_not_exist_is_an_error(self):
        self.restore_examples()
        self.write("canon/plots/the-ashcroft-debt.md",
                   PLOT.replace("the-ashen-vigil", "no-such-mod"))

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("no-such-mod", result.stdout)


class Campaigns(ValidatorTest):
    def test_an_event_without_a_campaign_is_an_error(self):
        self.restore_examples()
        self.edit("canon/events/e01-first-frost.md", "campaign: greymoor\n", "")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("canon/events/e01-first-frost.md: missing required field `campaign`",
                      result.stdout)

    def test_an_event_in_a_campaign_that_does_not_exist_is_an_error(self):
        self.restore_examples()
        self.edit("canon/events/e01-first-frost.md",
                  "campaign: greymoor", "campaign: no-such-campaign")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`campaign: no-such-campaign` does not resolve", result.stdout)


VIGIL = "mods/greymoor/the-ashen-vigil.md"

SECOND_CAMPAIGN = """---
id: kells-ford
type: campaign
aliases: ["Kell's Ford"]
---

## Summary

## GM Notes
"""

THIRD_EVENT = """---
id: e03-thaw
type: event
campaign: greymoor
ordinal: 3
period_type: event
aliases: ["Thaw", "Event 3"]
real_date: 2026-05-15
in_world: "the thaw"
status: complete
---

## Summary

## GM Notes
"""

SECOND_REPORT = """---
id: aa-the-ashen-vigil-2
type: after-action
mod: the-ashen-vigil
event: e03-thaw
ran: true
finished: true
mod_runner: alex
pcs: [pc-tomas-veil]
canon_changes:
  - entity: varen-ashcroft
    kind: narrative
    decision: approved
    summary: "Seen on the north road by a carter who did not know him."
---

## What Happened

## Divergences From The Mod

## Loose Ends
"""


class ModStates(ValidatorTest):
    def copy_vigil(self, rel, state, extra_edits=()):
        """A second mod made from the example one, with its own id and state."""
        mod_id = Path(rel).stem
        text = (self.root / VIGIL).read_text()
        text = text.replace("id: the-ashen-vigil", f"id: {mod_id}")
        text = text.replace("state: finished", f"state: {state}")
        for old, new in extra_edits:
            self.assertIn(old, text)
            text = text.replace(old, new)
        self.write(rel, text)

    def test_a_mod_can_be_in_each_of_the_five_states(self):
        self.restore_examples()
        no_events = [("events: [e02-hollow-night]\n", "")]
        self.copy_vigil("inbox/a-draft.md", "draft",
                        no_events + [("canon: approved", "canon: proposed")])
        self.copy_vigil("mods/greymoor/an-approved-one.md", "approved", no_events)
        self.copy_vigil("mods/greymoor/a-running-one.md", "in-progress")
        self.copy_vigil("mods/shelved/a-shelved-one.md", "shelved", no_events)

        result = self.validate()

        self.assertIn("11 documents · 0 errors", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_the_old_mod_states_are_rejected(self):
        self.restore_examples()
        self.edit(VIGIL, "state: finished", "state: played")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`state: played` is not in vocabulary `mod_state`", result.stdout)

    def test_a_mod_that_has_been_run_must_name_an_event(self):
        self.restore_examples()
        self.copy_vigil("mods/greymoor/a-running-one.md", "in-progress",
                        [("events: [e02-hollow-night]\n", "")])

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("mods/greymoor/a-running-one.md: `state: in-progress` requires "
                      "at least one event in `events`", result.stdout)


class ModsBelongToACampaign(ValidatorTest):
    def test_a_mod_filed_under_another_campaign_is_an_error(self):
        self.restore_examples()
        self.write("canon/campaigns/kells-ford.md", SECOND_CAMPAIGN)
        (self.root / "mods/kells-ford").mkdir()
        (self.root / VIGIL).rename(self.root / "mods/kells-ford/the-ashen-vigil.md")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("requires the file to live in mods/greymoor, but it is in "
                      "mods/kells-ford/", result.stdout)

    def test_a_mod_run_at_another_campaigns_event_is_an_error(self):
        self.restore_examples()
        self.write("canon/campaigns/kells-ford.md", SECOND_CAMPAIGN)
        self.write("canon/events/e03-thaw.md",
                   THIRD_EVENT.replace("campaign: greymoor", "campaign: kells-ford"))
        self.edit(VIGIL, "events: [e02-hollow-night]",
                  "events: [e02-hollow-night, e03-thaw]")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`events: e03-thaw` belongs to campaign `kells-ford`, "
                      "but this mod belongs to `greymoor`", result.stdout)

    def test_a_mod_outside_the_inbox_without_a_campaign_is_an_error(self):
        self.restore_examples()
        self.edit(VIGIL, "campaign: greymoor\n", "")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("a mod outside inbox/ needs a `campaign`", result.stdout)


class SeveralReports(ValidatorTest):
    def test_a_mod_can_have_reports_at_different_events(self):
        self.restore_examples()
        self.edit(REPORT, "finished: true", "finished: false")
        self.write("canon/events/e03-thaw.md", THIRD_EVENT)
        self.edit(VIGIL, "events: [e02-hollow-night]",
                  "events: [e02-hollow-night, e03-thaw]")
        self.write("after-actions/e03-thaw/aa-the-ashen-vigil-2.md", SECOND_REPORT)

        result = self.validate()

        self.assertIn("0 errors · 0 warnings", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_report_at_an_event_its_mod_does_not_list_is_an_error(self):
        self.restore_examples()
        self.edit(REPORT, "finished: true", "finished: false")
        self.write("canon/events/e03-thaw.md", THIRD_EVENT)
        self.write("after-actions/e03-thaw/aa-the-ashen-vigil-2.md", SECOND_REPORT)

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`event: e03-thaw` is not in the `events` of mod "
                      "`the-ashen-vigil`", result.stdout)


REPORT = "after-actions/e02-hollow-night/aa-the-ashen-vigil.md"


class Features(ValidatorTest):
    def test_a_feature_that_is_not_in_the_world_is_an_error(self):
        self.restore_examples()
        self.edit(VIGIL, "npcs: [varen-ashcroft]", "npcs: [varen-ashcroft, no-such-npc]")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`features.npcs: no-such-npc` does not resolve to any document",
                      result.stdout)

    def test_a_feature_of_the_wrong_kind_is_an_error(self):
        self.restore_examples()
        self.edit(VIGIL, "npcs: [varen-ashcroft]",
                  "npcs: [varen-ashcroft]\n  locations: [varen-ashcroft]")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`features.locations: varen-ashcroft` points at a `npc`, "
                      "expected location", result.stdout)

    def test_a_mod_must_list_its_features(self):
        self.restore_examples()
        self.edit(VIGIL, "features:", "involves:")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing required field `features`", result.stdout)


class Reports(ValidatorTest):
    def test_a_report_must_list_the_pcs_who_took_part(self):
        self.restore_examples()
        self.edit(REPORT, "pcs: [pc-tomas-veil]\n", "")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing required field `pcs`", result.stdout)

    def test_a_pc_who_is_not_in_the_world_is_an_error(self):
        self.restore_examples()
        self.edit(REPORT, "pcs: [pc-tomas-veil]", "pcs: [pc-tomas-veil, pc-nobody]")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`pcs: pc-nobody` does not resolve to any document", result.stdout)

    def test_the_pcs_must_be_a_list(self):
        self.restore_examples()
        self.edit(REPORT, "pcs: [pc-tomas-veil]", "pcs: pc-tomas-veil")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`pcs` must be a list of ids", result.stdout)

    def test_a_report_must_name_its_mod_runner(self):
        self.restore_examples()
        self.edit(REPORT, "mod_runner: alex\n", "")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing required field `mod_runner`", result.stdout)

    def test_a_canon_change_can_be_any_of_the_seven_kinds(self):
        self.restore_examples()
        self.write("canon/locations/greymoor-chapel.md", CHAPEL)
        self.write("canon/locations/the-north-road.md",
                   CHAPEL.replace("greymoor-chapel", "the-north-road")
                         .replace("Greymoor Chapel", "The North Road"))
        self.write("canon/factions/ashen-order.md", ORDER)
        self.write("canon/factions/the-council.md",
                   ORDER.replace("ashen-order", "the-council")
                        .replace("The Ashen Order", "The Council"))
        self.edit("canon/npcs/varen-ashcroft.md", "canon: approved",
                  "factions: [ashen-order]\nlocation: the-north-road\ncanon: approved")
        self.edit(REPORT, "\n---\n\n## What Happened", """
  - entity: varen-ashcroft
    kind: location
    decision: approved
    from: greymoor-chapel
    to: the-north-road
    summary: "Left the chapel by the north road."
  - entity: varen-ashcroft
    kind: affiliation
    decision: approved
    from: the-council
    to: ashen-order
    summary: "Stood with the Order when it came through."
  - entity: pc-tomas-veil
    kind: knowledge
    decision: approved
    summary: "Learned the lower door was never sealed."
  - entity: greymoor-chapel
    kind: narrative
    decision: approved
    summary: "The register is gone from the chapel."
  - entity: the-north-road
    kind: created
    decision: approved
    summary: "First named when Varen fled along it."
---

## What Happened""")

        result = self.validate()

        self.assertIn("0 errors", result.stdout)
        self.assertNotIn("not applied", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_canon_change_of_an_unknown_kind_is_an_error(self):
        self.restore_examples()
        self.edit(REPORT, "kind: relationship", "kind: rumour")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("`kind: rumour` is not in vocabulary `canon_change_kind`",
                      result.stdout)

    def test_a_later_report_at_the_same_event_overrides_an_earlier_one(self):
        self.restore_examples()
        self.edit(REPORT, "finished: true", "finished: false")
        self.write("after-actions/e02-hollow-night/aa-the-ashen-vigil-2.md",
                   SECOND_REPORT.replace("event: e03-thaw", "event: e02-hollow-night")
                   .replace("finished: true", "finished: false")
                   .replace('kind: narrative', 'kind: status\n    from: missing\n    to: dead'))
        self.write("after-actions/e02-hollow-night/aa-the-ashen-vigil-10.md",
                   SECOND_REPORT.replace("event: e03-thaw", "event: e02-hollow-night")
                   .replace("aa-the-ashen-vigil-2", "aa-the-ashen-vigil-10")
                   .replace('kind: narrative', 'kind: status\n    from: dead\n    to: final-death'))
        self.edit("canon/npcs/varen-ashcroft.md", "status: missing", "status: final-death")

        result = self.validate()

        self.assertIn("0 errors", result.stdout)
        self.assertNotIn("not applied", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)


CHAPEL = """---
id: greymoor-chapel
type: location
aliases: ["Greymoor Chapel"]
status: intact
as_of: e02-hollow-night
canon: approved
visibility: player-known
---

## Summary

## Description

## Who Holds It

## Current Situation

## GM Notes
"""

ORDER = """---
id: ashen-order
type: faction
aliases: ["The Ashen Order"]
status: active
as_of: e02-hollow-night
canon: approved
visibility: gm-only
---

## Summary

## GM Notes
"""


STATUS_CHANGE = "    kind: status\n    decision: approved\n"


class Decisions(ValidatorTest):
    """The example report moves Varen from alive to missing, and his file says
    missing. Each test changes the decision on that one canon change."""

    def varen_is_still_alive(self):
        """His file as it stood before the report: alive, as of the first event."""
        self.edit("canon/npcs/varen-ashcroft.md",
                  "status: missing\nas_of: e02-hollow-night",
                  "status: alive\nas_of: e01-first-frost")

    def a_later_mod_needs_varen_alive(self):
        self.write("canon/events/e03-thaw.md", THIRD_EVENT)
        text = (self.root / VIGIL).read_text()
        for old, new in [("id: the-ashen-vigil", "id: the-thaw-hunt"),
                         ("state: finished", "state: approved"),
                         ("events: [e02-hollow-night]", "events: [e03-thaw]")]:
            self.assertIn(old, text)
            text = text.replace(old, new)
        self.write("mods/greymoor/the-thaw-hunt.md", text)

    def test_an_approved_change_counts_against_a_later_mods_requirements(self):
        self.restore_examples()
        self.varen_is_still_alive()
        self.a_later_mod_needs_varen_alive()

        result = self.validate()

        self.assertIn("mods/greymoor/the-thaw-hunt.md: requires[0] expects "
                      "`varen-ashcroft.status` to be 'alive' but it is 'missing'",
                      result.stdout)

    def test_a_rejected_change_does_not_count_against_a_later_mod(self):
        self.restore_examples()
        self.varen_is_still_alive()
        self.a_later_mod_needs_varen_alive()
        self.edit(REPORT, STATUS_CHANGE, "    kind: status\n    decision: rejected\n")

        result = self.validate()

        self.assertIn("0 errors · 0 warnings", result.stdout)

    def test_a_canon_change_without_a_decision_is_an_error(self):
        self.restore_examples()
        self.edit(REPORT, STATUS_CHANGE, "    kind: status\n")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("canon_changes[0] missing `decision`", result.stdout)

    def test_a_decision_must_be_proposed_approved_or_rejected(self):
        self.restore_examples()
        self.edit(REPORT, STATUS_CHANGE, "    kind: status\n    decision: maybe\n")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("canon_changes[0] `decision: maybe` is not in vocabulary "
                      "`canon_change_decision` (proposed, approved, rejected)",
                      result.stdout)

    def test_an_approved_change_must_match_the_entity(self):
        self.restore_examples()
        self.varen_is_still_alive()

        result = self.validate()

        self.assertIn("canon/npcs/varen-ashcroft.md: `status` is 'alive' but the latest "
                      "approved status change", result.stdout)
        self.assertIn("approved but not applied", result.stdout)

    def test_a_rejected_change_need_not_match_the_entity(self):
        self.restore_examples()
        self.varen_is_still_alive()
        self.edit(REPORT, STATUS_CHANGE, "    kind: status\n    decision: rejected\n")

        result = self.validate()

        self.assertIn("0 errors · 0 warnings", result.stdout)

    def test_a_proposed_change_need_not_match_the_entity(self):
        self.restore_examples()
        self.varen_is_still_alive()
        self.edit(REPORT, STATUS_CHANGE, "    kind: status\n    decision: proposed\n")

        result = self.validate()

        self.assertIn("0 errors · 0 warnings", result.stdout)

    def test_two_changes_to_one_field_in_one_report_are_taken_in_the_reports_order(self):
        self.restore_examples()
        self.edit(REPORT, "  - entity: varen-ashcroft\n    kind: relationship\n",
                  "  - entity: varen-ashcroft\n    kind: status\n    decision: approved\n"
                  "    from: missing\n    to: dead\n"
                  "    summary: \"Found dead on the north road the same night.\"\n"
                  "  - entity: varen-ashcroft\n    kind: relationship\n")
        self.edit("canon/npcs/varen-ashcroft.md", "status: missing", "status: dead")

        result = self.validate()

        self.assertIn("0 errors · 0 warnings", result.stdout)

    def test_a_report_no_longer_has_a_flag_for_the_whole_report(self):
        self.restore_examples()
        self.edit(REPORT, "ran: true", "ran: true\ncanon_applied: true")

        result = self.validate()

        self.assertIn("unrecognised field `canon_applied`", result.stdout)


class NotesOnDecisions(ValidatorTest):
    """A Plot Master can say, in a `note`, why a change was approved or rejected."""

    def test_a_rejected_change_can_say_why(self):
        self.restore_examples()
        self.edit(REPORT, "    kind: relationship\n    decision: approved\n",
                  "    kind: relationship\n    decision: rejected\n"
                  "    note: \"Varen was never named at the vigil; see the mod notes.\"\n")

        result = self.validate()

        self.assertIn("0 errors · 0 warnings", result.stdout)

    def test_an_approved_change_can_say_why(self):
        self.restore_examples()
        self.edit(REPORT, STATUS_CHANGE,
                  STATUS_CHANGE + "    note: Fits the thaw plot.\n")

        result = self.validate()

        self.assertIn("0 errors · 0 warnings", result.stdout)

    def test_a_note_must_be_text(self):
        self.restore_examples()
        self.edit(REPORT, STATUS_CHANGE,
                  STATUS_CHANGE + "    note: [one, two]\n")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("canon_changes[0].note must be text", result.stdout)


class TheWorldOwnsEverythingElse(ValidatorTest):
    def test_a_campaign_on_a_world_document_is_flagged(self):
        self.restore_examples()
        self.edit("canon/npcs/varen-ashcroft.md", "type: npc", "type: npc\ncampaign: greymoor")

        result = self.validate()

        self.assertIn("canon/npcs/varen-ashcroft.md: unrecognised field `campaign`",
                      result.stdout)

    def test_a_campaign_cannot_take_the_shelved_folders_name(self):
        self.restore_examples()
        self.write("canon/campaigns/shelved.md",
                   SECOND_CAMPAIGN.replace("id: kells-ford", "id: shelved"))

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("a campaign cannot have the id `shelved`", result.stdout)


class OldNames(ValidatorTest):
    def test_the_old_type_names_are_rejected(self):
        self.restore_examples()
        mod = self.root / VIGIL
        mod.write_text(mod.read_text().replace("type: mod", "type: adventure"))
        self.write("canon/plots/the-ashcroft-debt.md",
                   PLOT.replace("type: plot", "type: thread"))

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown or missing `type`: 'adventure'", result.stdout)
        self.assertIn("unknown or missing `type`: 'thread'", result.stdout)



class WhetherAModIsFinished(ValidatorTest):
    """Every report says whether the Mod has more to play. The example Mod is
    finished and its one report says so."""

    def second_report(self, event="e03-thaw", finished="true"):
        self.write("canon/events/e03-thaw.md", THIRD_EVENT)
        self.edit(VIGIL, "events: [e02-hollow-night]", "events: [e02-hollow-night, e03-thaw]")
        self.write(f"after-actions/{event}/aa-the-ashen-vigil-2.md",
                   SECOND_REPORT.replace("event: e03-thaw", f"event: {event}")
                   .replace("finished: true", f"finished: {finished}"))

    def test_a_report_must_say_whether_the_mod_is_finished(self):
        self.restore_examples()
        self.edit(REPORT, "finished: true\n", "")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{REPORT}: missing required field `finished`", result.stdout)

    def test_it_must_be_yes_or_no(self):
        self.restore_examples()
        self.edit(REPORT, "finished: true", "finished: mostly")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{REPORT}: `finished: mostly` must be true or false", result.stdout)

    def test_whether_it_ran_must_be_yes_or_no_too(self):
        self.restore_examples()
        self.edit(REPORT, "ran: true", "ran: maybe")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{REPORT}: `ran: maybe` must be true or false", result.stdout)

    def test_a_quoted_yes_is_named_as_text(self):
        self.restore_examples()
        self.edit(REPORT, "ran: true", 'ran: "true"')

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{REPORT}: `ran: 'true'` must be true or false", result.stdout)

    def test_a_report_after_the_one_that_finished_the_mod_is_an_error(self):
        self.restore_examples()
        self.second_report()

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("after-actions/e03-thaw/aa-the-ashen-vigil-2.md: mod `the-ashen-vigil` was "
                      "finished by `aa-the-ashen-vigil`", result.stdout)

    def test_that_holds_for_two_reports_at_the_same_event(self):
        self.restore_examples()
        self.second_report(event="e02-hollow-night", finished="false")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("after-actions/e02-hollow-night/aa-the-ashen-vigil-2.md: mod "
                      "`the-ashen-vigil` was finished by `aa-the-ashen-vigil`", result.stdout)

    def test_the_report_that_finished_it_is_told_too(self):
        """Either report may be the one just submitted, so both are told."""
        self.restore_examples()
        self.second_report()

        result = self.validate()

        self.assertIn(f"{REPORT}: says mod `the-ashen-vigil` is finished, but "
                      "`aa-the-ashen-vigil-2` reports on it afterwards", result.stdout)

    def test_reports_are_read_in_order_of_event_before_id(self):
        """A report at an earlier Event comes first, whatever it is called."""
        self.restore_examples()
        self.edit(REPORT, "finished: true", "finished: false")
        self.edit(VIGIL, "events: [e02-hollow-night]", "events: [e01-first-frost, e02-hollow-night]")
        self.write("after-actions/e01-first-frost/aa-the-ashen-vigil-9.md",
                   SECOND_REPORT.replace("event: e03-thaw", "event: e01-first-frost")
                   .replace("aa-the-ashen-vigil-2", "aa-the-ashen-vigil-9"))

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{REPORT}: mod `the-ashen-vigil` was finished by "
                      "`aa-the-ashen-vigil-9`", result.stdout)

    def test_a_mod_that_did_not_run_is_not_finished_by_that_report(self):
        self.restore_examples()
        self.edit(REPORT, "ran: true", "ran: false")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{REPORT}: `ran: false` with `finished: true`", result.stdout)

    def test_a_mod_that_has_been_run_but_is_still_marked_as_not_begun_is_warned_about(self):
        self.restore_examples()
        self.edit(REPORT, "finished: true", "finished: false")
        text = (self.root / VIGIL).read_text().replace("state: finished", "state: approved")
        (self.root / VIGIL).write_text(text)

        result = self.validate()

        self.assertEqual(result.returncode, 0)
        self.assertIn(f"WARN   {VIGIL}: `state: approved`, but its latest report "
                      "(`aa-the-ashen-vigil`) says it has been run and has more to play",
                      result.stdout)

    def test_an_interruption_followed_by_the_report_that_finishes_it_is_fine(self):
        self.restore_examples()
        self.edit(REPORT, "finished: true", "finished: false")
        self.second_report()

        result = self.validate()

        self.assertIn("0 errors · 0 warnings", result.stdout)

    def test_a_finished_mod_whose_latest_report_says_there_is_more_is_warned_about(self):
        self.restore_examples()
        self.edit(REPORT, "finished: true", "finished: false")

        result = self.validate()

        self.assertEqual(result.returncode, 0)
        self.assertIn(f"WARN   {VIGIL}: `state: finished`, but its latest report "
                      "(`aa-the-ashen-vigil`) says there is more to play", result.stdout)

    def test_an_unfinished_mod_whose_latest_report_finished_it_is_warned_about(self):
        self.restore_examples()
        self.edit(VIGIL, "state: finished", "state: in-progress")

        result = self.validate()

        self.assertEqual(result.returncode, 0)
        self.assertIn(f"WARN   {VIGIL}: `state: in-progress`, but its latest report "
                      "(`aa-the-ashen-vigil`) says the mod is finished", result.stdout)

    def test_an_id_with_an_unusual_digit_in_it_is_reported_not_crashed_on(self):
        self.restore_examples()
        text = (self.root / REPORT).read_text().replace("id: aa-the-ashen-vigil",
                                                        "id: aa-1\u00b22")
        (self.root / REPORT).unlink()
        self.write("after-actions/e02-hollow-night/aa-1\u00b22.md", text)

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn("is not a clean slug", result.stdout)

    def test_a_report_must_be_on_one_mod(self):
        self.restore_examples()
        self.edit(REPORT, "mod: the-ashen-vigil", "mod: [the-ashen-vigil]")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{REPORT}: `mod` must be one id, not a list", result.stdout)

    def test_a_shelved_mod_is_left_alone_whatever_its_reports_say(self):
        self.restore_examples()
        self.edit(REPORT, "finished: true", "finished: false")
        text = (self.root / VIGIL).read_text().replace("state: finished", "state: shelved")
        (self.root / VIGIL).unlink()
        self.write("mods/shelved/the-ashen-vigil.md", text)

        result = self.validate()

        self.assertNotIn("says there is more to play", result.stdout)


if __name__ == "__main__":
    unittest.main()
