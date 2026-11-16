"""Changing one value in a document's text, as an app does when it writes a
file back, without disturbing comments, layout, quoting or line endings."""

import unittest

from plotcanon import editing
from plotcanon.editing import CannotEdit

NPC = """---
type: npc
id: varen-ashcroft  # the harbourmaster
status: alive
factions: [harbour-wardens, salt-guild]
---
Body text.
"""


class Replacing(unittest.TestCase):
    def test_only_the_one_value_changes_and_its_comment_stays(self):
        self.assertEqual(editing.replace(NPC, ["id"], "varen"),
                         NPC.replace("id: varen-ashcroft  #", "id: varen  #"))

    def test_a_value_inside_a_list_of_mappings(self):
        text = ("---\ntype: after-action\ncanon_changes:\n"
                "  - entity: varen-ashcroft\n    decision: proposed  # waiting\n"
                "  - entity: salt-guild\n    decision: proposed\n---\n")

        self.assertEqual(
            editing.replace(text, ["canon_changes", 1, "decision"], "approved"),
            text.replace("    decision: proposed\n---", "    decision: approved\n---"))

    def test_an_empty_value_keeps_a_space_after_its_colon(self):
        text = "---\nid: x\nas_of:\n---\n"
        self.assertEqual(editing.replace(text, ["as_of"], "e01"), "---\nid: x\nas_of: e01\n---\n")

    def test_a_list_down_the_page_is_replaced_and_the_next_field_keeps_its_line(self):
        text = "---\nfactions:\n  - harbour-wardens\n  - salt-guild\nstatus: alive\n---\n"
        self.assertEqual(editing.replace(text, ["factions"], "[salt-guild]"),
                         "---\nfactions:\n  [salt-guild]\nstatus: alive\n---\n")

    def test_crlf_line_endings_are_kept(self):
        text = NPC.replace("\n", "\r\n")
        self.assertEqual(editing.replace(text, ["status"], "dead"),
                         text.replace("status: alive", "status: dead"))

    def test_a_missing_path_cannot_be_edited(self):
        for path in (["nowhere"], ["factions", 5], ["id", "deeper"]):
            with self.subTest(path=path), self.assertRaises(CannotEdit):
                editing.replace(NPC, path, "x")

    def test_a_file_without_frontmatter_cannot_be_edited(self):
        with self.assertRaises(CannotEdit):
            editing.replace("Just text.\n", ["id"], "x")


class Finding(unittest.TestCase):
    def test_the_node_at_a_path_and_where_the_frontmatter_starts(self):
        node, offset = editing.find(NPC, ["factions", 1])
        self.assertEqual(node.value, "salt-guild")
        self.assertEqual(offset, 4)


class SettingAField(unittest.TestCase):
    def test_a_field_that_is_there_is_replaced(self):
        self.assertEqual(editing.set_field(NPC, "status", "dead"),
                         NPC.replace("status: alive", "status: dead"))

    def test_a_field_that_is_not_there_is_added_at_the_end(self):
        self.assertEqual(editing.set_field(NPC, "as_of", "e01"),
                         NPC.replace("salt-guild]\n---", "salt-guild]\nas_of: e01\n---"))

    def test_added_with_the_files_own_line_ending(self):
        text = NPC.replace("\n", "\r\n")
        self.assertEqual(editing.set_field(text, "as_of", "e01"),
                         text.replace("salt-guild]\r\n---", "salt-guild]\r\nas_of: e01\r\n---"))


CHANGES = ("---\ncanon_changes:\n"
           "  - entity: varen-ashcroft\n    decision: approved  # by the PM\n    summary: x\n"
           "  - {entity: salt-guild, decision: proposed, summary: y}\n---\n")


class SettingAKey(unittest.TestCase):
    def test_a_key_that_is_there_is_replaced(self):
        self.assertEqual(editing.set_key(CHANGES, ["canon_changes", 0], "summary", "z",
                                         after="decision"),
                         CHANGES.replace("summary: x", "summary: z"))

    def test_added_after_the_given_key_down_the_page_keeping_its_comment(self):
        self.assertEqual(
            editing.set_key(CHANGES, ["canon_changes", 0], "note", '"Fine."', after="decision"),
            CHANGES.replace("# by the PM\n", '# by the PM\n    note: "Fine."\n'))

    def test_added_after_the_given_key_on_one_line(self):
        self.assertEqual(
            editing.set_key(CHANGES, ["canon_changes", 1], "note", '"No."', after="decision"),
            CHANGES.replace("decision: proposed,", 'decision: proposed, note: "No.",'))

    def test_a_missing_after_key_cannot_be_edited(self):
        with self.assertRaises(CannotEdit):
            editing.set_key(CHANGES, ["canon_changes", 0], "note", "x", after="nowhere")


class RemovingAKey(unittest.TestCase):
    def test_down_the_page_its_line_goes(self):
        self.assertEqual(editing.remove_key(CHANGES, ["canon_changes", 0], "summary"),
                         CHANGES.replace("\n    summary: x", ""))

    def test_on_one_line_with_its_comma(self):
        self.assertEqual(editing.remove_key(CHANGES, ["canon_changes", 1], "decision"),
                         CHANGES.replace(", decision: proposed", ""))

    def test_the_first_key_on_one_line_with_the_comma_after_it(self):
        self.assertEqual(editing.remove_key(CHANGES, ["canon_changes", 1], "entity"),
                         CHANGES.replace("entity: salt-guild, ", ""))

    def test_a_key_that_is_not_there_leaves_the_file_as_it_was(self):
        self.assertEqual(editing.remove_key(CHANGES, ["canon_changes", 0], "note"), CHANGES)

    def test_the_first_key_down_the_page_cannot_be_taken_out(self):
        with self.assertRaises(CannotEdit):
            editing.remove_key(CHANGES, ["canon_changes", 0], "entity")

    def test_with_crlf_line_endings(self):
        text = CHANGES.replace("\n", "\r\n")
        self.assertEqual(editing.remove_key(text, ["canon_changes", 0], "summary"),
                         text.replace("\r\n    summary: x", ""))


class AddingToAList(unittest.TestCase):
    def test_a_list_on_one_line(self):
        self.assertEqual(editing.add_to_list(NPC, "factions", "tide-cult"),
                         NPC.replace("salt-guild]", "salt-guild, tide-cult]"))

    def test_an_empty_list_on_one_line(self):
        text = NPC.replace("[harbour-wardens, salt-guild]", "[]")
        self.assertEqual(editing.add_to_list(text, "factions", "tide-cult"),
                         NPC.replace("[harbour-wardens, salt-guild]", "[tide-cult]"))

    def test_a_list_down_the_page_with_a_comment(self):
        text = "---\nfactions:\n  - harbour-wardens  # sworn\nstatus: alive\n---\n"
        self.assertEqual(editing.add_to_list(text, "factions", "tide-cult"),
                         "---\nfactions:\n  - harbour-wardens  # sworn\n  - tide-cult\n"
                         "status: alive\n---\n")

    def test_an_empty_or_missing_field_becomes_a_list_of_the_one_item(self):
        self.assertEqual(editing.add_to_list("---\nid: x\nfactions:\n---\n", "factions", "a"),
                         "---\nid: x\nfactions: [a]\n---\n")
        self.assertEqual(editing.add_to_list("---\nid: x\n---\n", "factions", "a"),
                         "---\nid: x\nfactions: [a]\n---\n")

    def test_a_field_that_is_not_a_list_cannot_be_added_to(self):
        with self.assertRaises(CannotEdit):
            editing.add_to_list(NPC, "status", "x")


class WritingValues(unittest.TestCase):
    def test_quoted_is_one_double_quoted_line(self):
        self.assertEqual(editing.quoted('She said "no": twice.'), '"She said \\"no\\": twice."')
        self.assertEqual(editing.quoted("Café"), '"Café"')

    def test_flow_list(self):
        self.assertEqual(editing.flow_list(["a", "b"]), "[a, b]")
        self.assertEqual(editing.flow_list([]), "[]")
