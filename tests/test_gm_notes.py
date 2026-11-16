"""A document's text without its `## GM Notes`, the secret section, for anyone
outside the plot team."""

import unittest

import plotcanon


NPC = """\
---
id: old-fenn
type: npc
# a comment stays
---

## Overview

A ferryman.

## GM Notes

He drowned a man once.
"""


class WithoutGmNotes(unittest.TestCase):
    def test_gm_notes_at_the_end_are_removed(self):
        self.assertEqual(plotcanon.without_gm_notes(NPC), """\
---
id: old-fenn
type: npc
# a comment stays
---

## Overview

A ferryman.

""")

    def test_gm_notes_in_the_middle_stop_at_the_next_section(self):
        text = NPC + "\n## Features\n\n- the ferry\n"

        self.assertEqual(plotcanon.without_gm_notes(text),
                         NPC.split("## GM Notes")[0] + "## Features\n\n- the ferry\n")

    def test_a_subsection_of_gm_notes_goes_with_them(self):
        text = NPC + "\n### The drowned man\n\nNobody knows.\n\n## Features\n\n- the ferry\n"

        self.assertEqual(plotcanon.without_gm_notes(text),
                         NPC.split("## GM Notes")[0] + "## Features\n\n- the ferry\n")

    def test_a_top_level_heading_also_ends_them(self):
        text = NPC + "\n# Appendix\n"

        self.assertEqual(plotcanon.without_gm_notes(text),
                         NPC.split("## GM Notes")[0] + "# Appendix\n")

    def test_a_document_without_gm_notes_comes_back_as_it_was(self):
        text = NPC.split("## GM Notes")[0]

        self.assertEqual(plotcanon.without_gm_notes(text), text)

    def test_the_heading_is_matched_on_its_exact_text(self):
        for heading in ("## GM notes", "## GM Notes and more", "### GM Notes"):
            with self.subTest(heading):
                text = NPC.replace("## GM Notes", heading)

                self.assertEqual(plotcanon.without_gm_notes(text), text)

    def test_gm_notes_in_a_code_block_are_not_a_heading(self):
        text = NPC.replace("A ferryman.", "A ferryman.\n\n```\n## GM Notes\nshown\n```")

        self.assertIn("## GM Notes\nshown\n```", plotcanon.without_gm_notes(text))
        self.assertNotIn("He drowned", plotcanon.without_gm_notes(text))

    def test_a_gm_notes_comment_in_the_frontmatter_is_kept(self):
        text = NPC.replace("# a comment stays", "## GM Notes")

        self.assertTrue(plotcanon.without_gm_notes(text).startswith(
            "---\nid: old-fenn\ntype: npc\n## GM Notes\n---\n"))

    def test_crlf_text_keeps_its_line_endings(self):
        text = (NPC + "\n## Features\n\n- the ferry\n").replace("\n", "\r\n")

        self.assertEqual(plotcanon.without_gm_notes(text),
                         (NPC.split("## GM Notes")[0] + "## Features\n\n- the ferry\n")
                         .replace("\n", "\r\n"))


class EveryDocumentInTheSampleWorld(unittest.TestCase):
    def test_each_can_be_stripped_and_the_world_still_loads_clean(self):
        sample = plotcanon.sample_world()
        stripped = {path: plotcanon.without_gm_notes(text) if path.endswith(".md") else text
                    for path, text in sample.items()}

        with_notes = [p for p, t in sample.items() if "\n## GM Notes" in t]
        self.assertTrue(any(p.startswith("mods/") for p in with_notes))
        for path in with_notes:
            with self.subTest(path):
                self.assertNotIn("\n## GM Notes", stripped[path])
                self.assertLess(len(stripped[path]), len(sample[path]))
        report = plotcanon.load_world(stripped)
        self.assertTrue(report.ok, report.text())
        self.assertEqual(report.text(), "")


if __name__ == "__main__":
    unittest.main()
