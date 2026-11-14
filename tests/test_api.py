"""The functions another project calls: load a World, check one file."""

import unittest
from pathlib import Path

import plotcanon

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def example_files():
    """The example World as `{path: text}`, the way a web app would hold it."""
    files = {}
    for part in ("canon", "mods", "after-actions"):
        for path in sorted((EXAMPLES / part).rglob("*.md")):
            files[path.relative_to(EXAMPLES).as_posix()] = path.read_text()
    return files


VIGIL = "mods/greymoor/the-ashen-vigil.md"
REPORT = "after-actions/e02-hollow-night/aa-the-ashen-vigil.md"


class LoadingAWorld(unittest.TestCase):
    def test_a_valid_world_comes_back_parsed(self):
        report = plotcanon.load_world(example_files())

        self.assertTrue(report.ok)
        self.assertEqual(report.errors, ())
        varen = report.world.get("varen-ashcroft")
        self.assertEqual(varen.type, "npc")
        self.assertEqual(varen.path, "canon/npcs/varen-ashcroft.md")
        self.assertEqual(varen.fields["status"], "missing")
        self.assertEqual(varen.fields["aliases"][0], "Varen Ashcroft")
        self.assertIn("## Summary", varen.body)

    def test_documents_can_be_listed_by_type(self):
        world = plotcanon.load_world(example_files()).world

        self.assertEqual([d.id for d in world.of_type("event")],
                         ["e01-first-frost", "e02-hollow-night"])
        self.assertEqual([d.id for d in world.of_type("mod")], ["the-ashen-vigil"])
        self.assertEqual(world.of_type("faction"), [])
        self.assertIsNone(world.get("no-such-id"))

    def test_a_world_can_be_loaded_from_a_directory(self):
        from_directory = plotcanon.load_world(EXAMPLES)
        from_mapping = plotcanon.load_world(example_files())

        self.assertTrue(from_directory.ok)
        self.assertEqual([d.id for d in from_directory.world.documents],
                         [d.id for d in from_mapping.world.documents])

    def test_a_world_with_errors_gives_errors_and_no_world(self):
        files = example_files()
        files[VIGIL] = files[VIGIL].replace("npcs: [varen-ashcroft]",
                                            "npcs: [varen-ashcroft, no-such-npc]")

        report = plotcanon.load_world(files)

        self.assertFalse(report.ok)
        self.assertIsNone(report.world)
        [error] = report.errors
        self.assertEqual(error.severity, "error")
        self.assertEqual(error.path, VIGIL)
        self.assertEqual(error.message,
                         "`features.npcs: no-such-npc` does not resolve to any document")

    def test_warnings_do_not_stop_a_world_loading(self):
        files = example_files()
        files["canon/npcs/varen-ashcroft.md"] = files["canon/npcs/varen-ashcroft.md"].replace(
            "type: npc", "type: npc\nnickname: Ash")

        report = plotcanon.load_world(files)

        self.assertTrue(report.ok)
        self.assertIsNotNone(report.world)
        [warning] = report.warnings
        self.assertEqual(warning.severity, "warning")
        self.assertIn("unrecognised field `nickname`", warning.message)

    def test_paths_are_tidied_before_use(self):
        files = {"./" + path.replace("/", "\\"): text for path, text in example_files().items()}

        report = plotcanon.load_world(files)

        self.assertTrue(report.ok, report.text())
        self.assertEqual(report.world.get("varen-ashcroft").path, "canon/npcs/varen-ashcroft.md")

    def test_a_path_that_leaves_the_world_is_refused(self):
        for bad in ("../canon/npcs/x.md", "/etc/canon/npcs/x.md", "canon/../../x.md"):
            with self.subTest(bad), self.assertRaises(ValueError):
                plotcanon.load_world({bad: "---\nid: x\n---\n"})

    def test_file_contents_must_be_text(self):
        with self.assertRaises(TypeError):
            plotcanon.load_world({"canon/npcs/x.md": b"---\nid: x\n---\n"})

    def test_a_byte_order_mark_is_ignored(self):
        files = example_files()
        files[VIGIL] = "\ufeff" + files[VIGIL]

        self.assertTrue(plotcanon.load_world(files).ok)

    def test_files_outside_the_world_folders_are_ignored(self):
        files = example_files()
        files["README.md"] = "# Not a document\n"
        files["lore/the-old-kingdom.md"] = "No frontmatter here.\n"

        report = plotcanon.load_world(files)

        self.assertTrue(report.ok)
        self.assertEqual(report.findings, ())


    def test_a_directory_that_does_not_exist_is_refused(self):
        with self.assertRaises(NotADirectoryError):
            plotcanon.load_world(EXAMPLES / "no-such-world")


class ErrorText(unittest.TestCase):
    def test_broken_yaml_is_reported_on_one_line(self):
        files = example_files()
        files[VIGIL] = files[VIGIL].replace('title: "The Ashen Vigil"', 'title: "The Ashen Vigil')

        report = plotcanon.load_world(files)

        [error] = [e for e in report.errors if e.path == VIGIL]
        self.assertTrue(error.message.startswith("frontmatter is not valid YAML: "), error)
        self.assertNotIn("\n", error.message)

    def test_each_line_names_the_file_the_field_and_what_is_wrong(self):
        files = example_files()
        files[REPORT] = files[REPORT].replace("mod_runner: alex\n", "")
        files[VIGIL] = files[VIGIL].replace("state: finished", "state: played")

        text = plotcanon.load_world(files).text()

        self.assertEqual(text.splitlines(), [
            "ERROR  mods/greymoor/the-ashen-vigil.md: `state: played` is not in vocabulary "
            "`mod_state` (draft, approved, in-progress, finished, shelved)",
            "ERROR  after-actions/e02-hollow-night/aa-the-ashen-vigil.md: "
            "missing required field `mod_runner`",
        ])

    def test_a_clean_world_has_no_text(self):
        self.assertEqual(plotcanon.load_world(example_files()).text(), "")


NEW_MOD = """---
id: the-thaw-hunt
type: mod
title: "The Thaw Hunt"
aliases: ["The Thaw Hunt"]
mod_writer: mira
state: draft
canon: proposed
visibility: gm-only
features:
  npcs: [varen-ashcroft]
---

## Premise

Varen is seen on the north road.

## Hooks

## Scene Breakdown

## NPC Casting

## Player Agency Notes

## Possible Outcomes

## Rewards

## Logistics

## GM Notes
"""

NEW_REPORT = """---
id: aa-the-ashen-vigil-2
type: after-action
mod: the-ashen-vigil
event: e02-hollow-night
ran: true
mod_runner: alex
pcs: [pc-tomas-veil]
canon_changes:
  - entity: varen-ashcroft
    kind: narrative
    decision: proposed
    summary: "Seen on the north road by a carter who did not know him."
---

## What Happened

## Divergences From The Mod

## Loose Ends
"""


class CheckingOneFile(unittest.TestCase):
    def setUp(self):
        self.world = plotcanon.load_world(example_files()).world

    def test_a_valid_mod_comes_back_parsed(self):
        report = plotcanon.check_file(self.world, "inbox/the-thaw-hunt.md", NEW_MOD)

        self.assertTrue(report.ok)
        self.assertEqual(report.findings, ())
        self.assertEqual(report.document.id, "the-thaw-hunt")
        self.assertEqual(report.document.type, "mod")
        self.assertEqual(report.document.fields["features"], {"npcs": ["varen-ashcroft"]})

    def test_a_valid_report_comes_back_parsed(self):
        report = plotcanon.check_file(
            self.world, "after-actions/e02-hollow-night/aa-the-ashen-vigil-2.md", NEW_REPORT)

        self.assertTrue(report.ok)
        self.assertEqual(report.document.type, "after-action")
        self.assertEqual(report.document.fields["canon_changes"][0]["decision"], "proposed")

    def test_a_report_naming_things_the_world_does_not_have_is_rejected(self):
        text = NEW_REPORT.replace("pcs: [pc-tomas-veil]", "pcs: [pc-nobody]").replace(
            "entity: varen-ashcroft", "entity: the-baron")

        report = plotcanon.check_file(
            self.world, "after-actions/e02-hollow-night/aa-the-ashen-vigil-2.md", text)

        self.assertFalse(report.ok)
        self.assertIsNone(report.document)
        self.assertEqual(report.text().splitlines(), [
            "ERROR  after-actions/e02-hollow-night/aa-the-ashen-vigil-2.md: "
            "`pcs: pc-nobody` does not resolve to any document",
            "ERROR  after-actions/e02-hollow-night/aa-the-ashen-vigil-2.md: "
            "`canon_changes[0].entity: the-baron` does not resolve to any document",
        ])

    def test_a_file_that_is_not_frontmatter_and_markdown_is_rejected(self):
        report = plotcanon.check_file(self.world, "inbox/the-thaw-hunt.md",
                                      "Just some prose about a hunt.\n")

        self.assertIsNone(report.document)
        self.assertEqual(report.text(),
                         "ERROR  inbox/the-thaw-hunt.md: no YAML frontmatter block")

    def test_only_findings_about_that_file_are_returned(self):
        files = example_files()
        files[REPORT] = files[REPORT].replace("mod_runner: alex\n", "")

        report = plotcanon.check_file(files, "inbox/the-thaw-hunt.md", NEW_MOD)

        self.assertTrue(report.ok)
        self.assertEqual(report.findings, ())

    def test_checking_a_file_does_not_change_the_world(self):
        plotcanon.check_file(self.world, "inbox/the-thaw-hunt.md", NEW_MOD)

        self.assertIsNone(self.world.get("the-thaw-hunt"))
        self.assertNotIn("inbox/the-thaw-hunt.md", self.world.files)

    def test_a_file_can_replace_one_already_in_the_world(self):
        revised = self.world.files[VIGIL].replace('title: "The Ashen Vigil"',
                                                  'title: "The Ashen Vigil, revised"')

        report = plotcanon.check_file(self.world, VIGIL, revised)

        self.assertTrue(report.ok)
        self.assertEqual(report.document.fields["title"], "The Ashen Vigil, revised")

    def test_a_file_reusing_another_documents_id_is_rejected(self):
        text = NEW_MOD.replace("id: the-thaw-hunt", "id: the-ashen-vigil")

        report = plotcanon.check_file(self.world, "inbox/the-ashen-vigil.md", text)

        self.assertIsNone(report.document)
        self.assertEqual(report.text(),
                         "ERROR  inbox/the-ashen-vigil.md: duplicate id `the-ashen-vigil` — "
                         "also in mods/greymoor/the-ashen-vigil.md")

    def test_an_untidy_path_still_replaces_the_file_it_names(self):
        revised = self.world.files[VIGIL].replace("state: finished", "state: played")

        report = plotcanon.check_file(self.world, "./" + VIGIL, revised)

        self.assertFalse(report.ok)
        self.assertEqual(report.errors[0].path, VIGIL)

    def test_a_path_outside_the_world_folders_is_rejected(self):
        report = plotcanon.check_file(self.world, "the-thaw-hunt.md", NEW_MOD)

        self.assertFalse(report.ok)
        self.assertIn("not a document path", report.text())


class TheSchema(unittest.TestCase):
    def test_the_vocabularies_are_available(self):
        states = plotcanon.vocabularies()["vocabularies"]["mod_state"]

        self.assertEqual(list(states), ["draft", "approved", "in-progress", "finished", "shelved"])

    def test_the_schema_docs_ship_with_the_package(self):
        files = plotcanon.schema_files()

        self.assertIn("vocabularies.yml", files)
        self.assertIn("mod.md", files)
        self.assertTrue(files["mod.md"].startswith("# `mod`"))

    def test_the_version_is_the_installed_one(self):
        self.assertRegex(plotcanon.__version__, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
