"""Applying an approved Canon Change to an entity's file, and taking it back
out, by the rules `load_world` checks: a factions change takes `before` out
and puts `after` in, any other field goes from `before` to `after`, and
`as_of` moves with the latest approved change."""

import unittest

import plotcanon
from plotcanon import Change, ChangeRefused

ORDINALS = {"e01": 1, "e02": 2, "e03": 3, "e04": 4}
event_ordinal = ORDINALS.get

NPC = """---
type: npc
id: varen-ashcroft
status: alive  # for now
location: brackwater-harbour
factions: [harbour-wardens, salt-guild]
as_of: e02
---
Body text.
"""


def apply(text, field, change, **kwargs):
    return plotcanon.applied(text, field, change, event_ordinal=event_ordinal, **kwargs)


def undo(text, field, change, **kwargs):
    return plotcanon.unapplied(text, field, change, event_ordinal=event_ordinal, **kwargs)


def refusal(call):
    try:
        call()
    except ChangeRefused as refused:
        return refused
    raise AssertionError("not refused")


class ApplyingAChangeToAField(unittest.TestCase):
    def test_the_field_moves_to_after_and_as_of_to_the_changes_event(self):
        self.assertEqual(
            apply(NPC, "status", Change("alive", "dead", "e03")),
            NPC.replace("status: alive", "status: dead").replace("as_of: e02", "as_of: e03"))

    def test_as_of_stays_when_it_already_stands_at_a_later_event(self):
        self.assertEqual(apply(NPC, "status", Change("alive", "dead", "e01")),
                         NPC.replace("status: alive", "status: dead"))

    def test_as_of_is_added_when_the_file_has_none(self):
        text = NPC.replace("as_of: e02\n", "")
        self.assertEqual(apply(text, "status", Change("alive", "dead", "e01")),
                         text.replace("status: alive", "status: dead")
                         .replace("salt-guild]\n", "salt-guild]\nas_of: e01\n"))

    def test_no_after_leaves_the_field_null(self):
        self.assertEqual(apply(NPC, "location", Change("brackwater-harbour", None, "e03")),
                         NPC.replace("location: brackwater-harbour", "location: null")
                         .replace("as_of: e02", "as_of: e03"))

    def test_from_nothing(self):
        text = NPC.replace("location: brackwater-harbour", "location:")
        self.assertEqual(apply(text, "location", Change("", "the-drowned-chapel", "e03")),
                         NPC.replace("brackwater-harbour", "the-drowned-chapel")
                         .replace("as_of: e02", "as_of: e03"))

    def test_following_on_from_the_previous_change(self):
        self.assertEqual(
            apply(NPC, "status", Change("alive", "dead", "e03"),
                  previous=Change("missing", "alive", "e02")),
            NPC.replace("status: alive", "status: dead").replace("as_of: e02", "as_of: e03"))

    def test_a_later_change_already_deciding_the_field_leaves_the_file_as_it_was(self):
        text = NPC.replace("status: alive", "status: dead")
        self.assertEqual(
            apply(text, "status", Change("alive", "missing", "e01"),
                  following=Change("missing", "dead", "e02")),
            text)


class RefusingAChangeToAField(unittest.TestCase):
    def test_one_that_does_not_follow_on_from_the_previous_change(self):
        previous = Change("alive", "missing", "e01")

        refused = refusal(lambda: apply(NPC, "status", Change("alive", "dead", "e03"),
                                        previous=previous))

        self.assertEqual(refused.reason, "contradicts-previous")
        self.assertEqual(refused.neighbor, "previous")
        self.assertEqual(refused.other, previous)

    def test_one_that_does_not_lead_into_the_following_change(self):
        following = Change("missing", "dead", "e04")

        refused = refusal(lambda: apply(NPC, "status", Change("alive", "dead", "e03"),
                                        following=following))

        self.assertEqual(refused.reason, "contradicts-following")
        self.assertEqual(refused.neighbor, "following")
        self.assertEqual(refused.other, following)

    def test_one_that_does_not_start_from_the_current_value(self):
        refused = refusal(lambda: apply(NPC, "status", Change("missing", "dead", "e03")))

        self.assertEqual(refused.reason, "contradicts-current")
        self.assertEqual(refused.current, "alive")
        self.assertIsNone(refused.neighbor)

    def test_the_current_value_since_the_previous_change(self):
        previous = Change("missing", "dead", "e01")
        refused = refusal(lambda: apply(NPC, "status", Change("dead", "missing", "e03"),
                                        previous=previous))

        self.assertEqual(refused.reason, "contradicts-current")
        self.assertEqual(refused.current, "alive")
        self.assertEqual(refused.neighbor, "previous")
        self.assertEqual(refused.other, previous)

    def test_nothing_and_an_empty_value_are_the_same(self):
        text = NPC.replace("location: brackwater-harbour", "location: null")
        self.assertEqual(apply(text, "location", Change("", "x", "e03")),
                         NPC.replace("location: brackwater-harbour", "location: x")
                         .replace("as_of: e02", "as_of: e03"))


class ApplyingAFactionsChange(unittest.TestCase):
    def test_before_comes_out_and_after_goes_in(self):
        self.assertEqual(
            apply(NPC, "factions", Change("salt-guild", "tide-cult", "e03")),
            NPC.replace("[harbour-wardens, salt-guild]", "[harbour-wardens, tide-cult]")
            .replace("as_of: e02", "as_of: e03"))

    def test_joining_from_nothing_and_leaving_for_nothing(self):
        self.assertEqual(
            apply(NPC, "factions", Change(None, "tide-cult", "e01")),
            NPC.replace("salt-guild]", "salt-guild, tide-cult]"))
        self.assertEqual(
            apply(NPC, "factions", Change("salt-guild", None, "e01")),
            NPC.replace("[harbour-wardens, salt-guild]", "[harbour-wardens]"))

    def test_a_faction_already_held_is_not_listed_twice(self):
        self.assertEqual(
            apply(NPC, "factions", Change("salt-guild", "harbour-wardens", "e01")),
            NPC.replace("[harbour-wardens, salt-guild]", "[harbour-wardens]"))

    def test_a_list_down_the_page(self):
        text = NPC.replace("factions: [harbour-wardens, salt-guild]",
                           "factions:\n  - harbour-wardens\n  - salt-guild")
        self.assertEqual(
            apply(text, "factions", Change("salt-guild", "tide-cult", "e01")),
            NPC.replace("factions: [harbour-wardens, salt-guild]",
                        "factions:\n  [harbour-wardens, tide-cult]"))

    def test_with_crlf_line_endings(self):
        text = NPC.replace("\n", "\r\n")
        self.assertEqual(
            apply(text, "factions", Change("salt-guild", "tide-cult", "e03")),
            text.replace("salt-guild]", "tide-cult]").replace("as_of: e02", "as_of: e03"))

    def test_refused_when_a_later_factions_change_is_already_approved(self):
        following = Change("tide-cult", "salt-guild", "e04")

        refused = refusal(lambda: apply(NPC, "factions", Change("salt-guild", "tide-cult", "e03"),
                                        following=following))

        self.assertEqual(refused.reason, "factions-out-of-order")
        self.assertEqual(refused.neighbor, "following")
        self.assertEqual(refused.other, following)

    def test_refused_when_not_a_member_of_before(self):
        refused = refusal(lambda: apply(NPC, "factions", Change("tide-cult", "salt-guild", "e03")))

        self.assertEqual(refused.reason, "not-a-member")
        self.assertEqual(refused.current, ["harbour-wardens", "salt-guild"])


class TheRefusal(unittest.TestCase):
    def test_says_its_reason_and_nothing_more(self):
        refused = refusal(lambda: apply(NPC, "status", Change("missing", "dead", "e03")))
        self.assertEqual(str(refused), "contradicts-current")


class UndoingAChangeToAField(unittest.TestCase):
    """NPC stands as of e02, where a change took its status from missing to alive."""

    CHANGE = Change("missing", "alive", "e02", replaced={"status": "missing", "as_of": "e01"})

    def test_the_field_goes_back_to_before_and_as_of_to_what_was_replaced(self):
        self.assertEqual(undo(NPC, "status", self.CHANGE),
                         NPC.replace("status: alive", "status: missing")
                         .replace("as_of: e02", "as_of: e01"))

    def test_the_field_goes_back_to_where_the_previous_change_left_it(self):
        self.assertEqual(
            undo(NPC, "status", self.CHANGE, previous=Change("alive", "lost", "e01")),
            NPC.replace("status: alive", "status: lost").replace("as_of: e02", "as_of: e01"))

    def test_back_to_nothing_is_null(self):
        change = Change(None, "alive", "e02")
        self.assertEqual(undo(NPC, "status", change),
                         NPC.replace("status: alive", "status: null"))

    def test_as_of_goes_back_to_the_latest_remaining_change_when_that_is_later(self):
        text = NPC.replace("as_of: e02", "as_of: e03")
        change = Change("missing", "alive", "e03", replaced={"as_of": "e01"})
        self.assertEqual(undo(text, "status", change, remaining_events=("e01", "e02")),
                         NPC.replace("status: alive", "status: missing"))

    def test_a_remaining_change_at_the_same_event_keeps_as_of(self):
        self.assertEqual(undo(NPC, "status", self.CHANGE, remaining_events=("e02",)),
                         NPC.replace("status: alive", "status: missing"))

    def test_without_replaced_as_of_goes_back_to_the_latest_remaining_change(self):
        change = Change("missing", "alive", "e02")
        self.assertEqual(undo(NPC, "status", change, remaining_events=("e01",)),
                         NPC.replace("status: alive", "status: missing")
                         .replace("as_of: e02", "as_of: e01"))

    def test_with_nothing_replaced_and_nothing_remaining_as_of_stays(self):
        self.assertEqual(undo(NPC, "status", Change("missing", "alive", "e02")),
                         NPC.replace("status: alive", "status: missing"))

    def test_as_of_stays_when_this_change_did_not_put_it_there(self):
        self.assertEqual(undo(NPC, "status", Change("missing", "alive", "e01",
                                                    replaced={"as_of": "e00"})),
                         NPC.replace("status: alive", "status: missing"))

    def test_an_event_with_no_ordinal_is_passed_over(self):
        self.assertEqual(undo(NPC, "status", self.CHANGE, remaining_events=("e09", None)),
                         NPC.replace("status: alive", "status: missing")
                         .replace("as_of: e02", "as_of: e01"))

    def test_refused_when_a_later_change_follows_on(self):
        following = Change("alive", "dead", "e03")

        refused = refusal(lambda: undo(NPC, "status", self.CHANGE, following=following))

        self.assertEqual(refused.reason, "followed-on")
        self.assertEqual(refused.neighbor, "following")
        self.assertEqual(refused.other, following)


class UndoingAFactionsChange(unittest.TestCase):
    def test_the_list_goes_back_to_what_was_replaced(self):
        change = Change("tide-cult", "salt-guild", "e02",
                        replaced={"factions": ["tide-cult", "harbour-wardens"], "as_of": "e01"})
        self.assertEqual(undo(NPC, "factions", change),
                         NPC.replace("[harbour-wardens, salt-guild]",
                                     "[tide-cult, harbour-wardens]")
                         .replace("as_of: e02", "as_of: e01"))

    def test_without_replaced_after_comes_out_and_before_goes_back_in(self):
        self.assertEqual(undo(NPC, "factions", Change("tide-cult", "salt-guild", "e02")),
                         NPC.replace("[harbour-wardens, salt-guild]",
                                     "[harbour-wardens, tide-cult]"))

    def test_without_replaced_a_faction_already_held_is_kept(self):
        self.assertEqual(
            undo(NPC, "factions", Change("salt-guild", "salt-guild", "e02")), NPC)
        self.assertEqual(
            undo(NPC, "factions", Change("harbour-wardens", "salt-guild", "e02")),
            NPC.replace("[harbour-wardens, salt-guild]", "[harbour-wardens]"))

    def test_replaced_that_was_not_a_list_leaves_an_empty_one(self):
        change = Change(None, "salt-guild", "e02", replaced={"factions": None})
        self.assertEqual(undo(NPC, "factions", change),
                         NPC.replace("[harbour-wardens, salt-guild]", "[]"))

    def test_refused_when_a_later_change_follows_on(self):
        refused = refusal(lambda: undo(NPC, "factions", Change("a", "b", "e02"),
                                       following=Change("b", "c", "e03")))
        self.assertEqual(refused.reason, "followed-on")
