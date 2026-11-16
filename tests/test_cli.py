"""The `plotcanon` command, run the way a person or a git hook runs it."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
VIGIL = "mods/greymoor/the-ashen-vigil.md"


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        for part in ("canon", "mods", "after-actions"):
            shutil.copytree(EXAMPLES / part, self.root / part)

    def plotcanon(self, *args, cwd=None):
        return subprocess.run([sys.executable, "-m", "plotcanon.cli", *args],
                              cwd=cwd or self.root, capture_output=True, text=True)

    def break_the_mod(self):
        path = self.root / VIGIL
        path.write_text(path.read_text().replace("state: finished", "state: played"))

    def add_a_warning(self):
        path = self.root / "canon/npcs/varen-ashcroft.md"
        path.write_text(path.read_text().replace("type: npc", "type: npc\nnickname: Ash"))


class Validate(CommandTest):
    def test_a_clean_world_passes(self):
        result = self.plotcanon("validate")

        self.assertEqual(result.stdout, "\n7 documents · 0 errors · 0 warnings\ncanon is clean\n")
        self.assertEqual(result.returncode, 0)

    def test_an_error_is_printed_and_fails(self):
        self.break_the_mod()

        result = self.plotcanon("validate")

        self.assertIn(f"ERROR  {VIGIL}: `state: played` is not in vocabulary", result.stdout)
        self.assertIn("7 documents · 1 errors · 0 warnings", result.stdout)
        self.assertEqual(result.returncode, 1)

    def test_a_warning_alone_passes(self):
        self.add_a_warning()

        result = self.plotcanon("validate")

        self.assertIn("WARN   canon/npcs/varen-ashcroft.md: unrecognised field `nickname`",
                      result.stdout)
        self.assertNotIn("canon is clean", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_strict_fails_on_a_warning(self):
        self.add_a_warning()

        self.assertEqual(self.plotcanon("validate", "--strict").returncode, 1)

    def test_quiet_prints_findings_only(self):
        self.break_the_mod()

        result = self.plotcanon("validate", "--quiet")

        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertNotIn("documents", result.stdout)

    def test_paths_limit_what_is_reported(self):
        self.break_the_mod()

        result = self.plotcanon("validate", "canon/npcs/varen-ashcroft.md")

        self.assertIn("0 errors", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_a_path_that_is_not_in_the_world_is_refused(self):
        self.break_the_mod()

        result = self.plotcanon("validate", "mods/greymoor/no-such-file.md")

        self.assertEqual(result.returncode, 2)
        self.assertIn("mods/greymoor/no-such-file.md", result.stderr)

    def test_a_root_that_does_not_exist_is_refused(self):
        result = self.plotcanon("validate", "--root", str(self.root / "nowhere"))

        self.assertEqual(result.returncode, 2)
        self.assertIn("no World directory", result.stderr)

    def test_a_file_that_is_not_text_is_named(self):
        (self.root / "canon/npcs/broken.md").write_bytes(b"\xff\xfe\x00")

        result = self.plotcanon("validate")

        self.assertEqual(result.returncode, 2)
        self.assertIn("canon/npcs/broken.md is not UTF-8 text", result.stderr)

    def test_root_points_at_a_world_elsewhere(self):
        self.break_the_mod()

        result = self.plotcanon("validate", "--root", str(self.root), cwd=Path.cwd())

        self.assertEqual(result.returncode, 1)

    def test_a_stale_copy_of_the_schema_is_warned_about(self):
        self.plotcanon("schema", "--write", "schema")
        self.assertIn("0 warnings", self.plotcanon("validate").stdout)
        with open(self.root / "schema/vocabularies.yml", "a") as f:
            f.write("\n# edited by hand\n")

        result = self.plotcanon("validate")

        self.assertIn("WARN   schema/vocabularies.yml: differs from the schema this version "
                      "of plotcanon validates against", result.stdout)

    def test_a_stale_schema_doc_is_warned_about_too(self):
        self.plotcanon("schema", "--write", "schema")
        with open(self.root / "schema/mod.md", "a") as f:
            f.write("\nA note added by hand.\n")
        (self.root / "schema/plot.md").unlink()

        result = self.plotcanon("validate")

        self.assertIn("WARN   schema/mod.md: differs from the schema", result.stdout)
        self.assertIn("WARN   schema/plot.md: is missing from this copy of the schema", result.stdout)


class Pov(CommandTest):
    def test_it_lists_what_canon_records_about_an_entity(self):
        result = self.plotcanon("pov", "varen-ashcroft")

        self.assertEqual(result.returncode, 0)
        self.assertIn("# Retrieval bundle — `varen-ashcroft` (npc)", result.stdout)
        self.assertIn("The Ashen Vigil", result.stdout)
        self.assertIn("- `status`: alive → missing — Opened the lower door", result.stdout)

    def test_an_unknown_entity_fails_with_a_hint(self):
        result = self.plotcanon("pov", "varen")

        self.assertEqual(result.returncode, 1)
        self.assertIn("no entity with id `varen`.  Did you mean: varen-ashcroft", result.stderr)


class Sample(CommandTest):
    def test_write_puts_the_sample_world_on_disk_as_a_valid_world(self):
        target = self.root / "demo"

        result = self.plotcanon("sample", "--write", "demo")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target / "canon/campaigns/tideward.md").exists())
        check = self.plotcanon("validate", "--root", str(target))
        self.assertIn("48 documents · 0 errors · 0 warnings", check.stdout)

    def test_the_scripted_reports_go_in_a_folder_of_their_own(self):
        self.plotcanon("sample", "--write", "demo", "--script", "demo-script")

        reports = sorted(p.name for p in (self.root / "demo-script").rglob("*.md"))
        self.assertEqual(len(reports), 5)
        self.assertTrue((self.root / "demo-script/script.yml").exists())
        self.assertFalse(list((self.root / "demo/after-actions").rglob("aa-storm-moon-vigil.md")))

    def test_it_will_not_write_over_a_folder_that_has_things_in_it(self):
        result = self.plotcanon("sample", "--write", "canon")

        self.assertEqual(result.returncode, 2)
        self.assertIn("is not empty", result.stderr)


class Words(CommandTest):
    def test_it_names_each_avoided_word_and_the_file_it_is_in(self):
        (self.root / "notes.md").write_text("Ask the plot lead.\nThe author agreed.\n")
        (self.root / "fine.md").write_text("Ask the Plot Master.\n")

        result = self.plotcanon("words", "notes.md", "fine.md")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines(), [
            "notes.md:1: 'plot lead' (use Plot Master)",
            "notes.md:2: 'author' (use Mod Writer)",
        ])

    def test_clean_files_pass(self):
        (self.root / "fine.md").write_text("Ask the Plot Master.\n")

        result = self.plotcanon("words", "fine.md")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_a_folder_is_searched_for_markdown(self):
        (self.root / "docs/deep").mkdir(parents=True)
        (self.root / "docs/deep/notes.md").write_text("A new arc.\n")

        result = self.plotcanon("words", "docs")

        self.assertEqual(result.stdout.splitlines(), ["docs/deep/notes.md:1: 'arc' (use Plot)"])

    def test_a_path_that_does_not_exist_is_refused(self):
        result = self.plotcanon("words", "nowhere.md")

        self.assertEqual(result.returncode, 2)

    def test_a_phrase_broken_across_two_lines_is_found_on_the_line_it_starts(self):
        (self.root / "notes.md").write_text("First line.\nSo ask the plot\nlead about it.\n")

        result = self.plotcanon("words", "notes.md")

        self.assertEqual(result.stdout.splitlines(), ["notes.md:2: 'plot lead' (use Plot Master)"])

    def test_a_file_named_twice_is_checked_once(self):
        (self.root / "docs").mkdir()
        (self.root / "docs/notes.md").write_text("A new arc.\n")

        result = self.plotcanon("words", "docs", "docs/notes.md")

        self.assertEqual(len(result.stdout.splitlines()), 1)

    def test_a_file_that_is_not_text_is_named(self):
        (self.root / "blob.md").write_bytes(b"\xff\xfe\x00")

        result = self.plotcanon("words", "blob.md")

        self.assertEqual(result.returncode, 2)
        self.assertIn("blob.md is not UTF-8 text", result.stderr)

    def test_a_path_outside_the_root_is_refused(self):
        outside = Path(tempfile.mkdtemp()) / "notes.md"
        outside.write_text("A new arc.\n")

        result = self.plotcanon("words", str(outside))

        self.assertEqual(result.returncode, 2)


class Schema(CommandTest):
    def test_write_is_relative_to_the_root(self):
        result = self.plotcanon("schema", "--write", "schema", "--root", str(self.root),
                                cwd=Path(tempfile.mkdtemp()))

        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.root / "schema/vocabularies.yml").exists())

    def test_write_copies_the_schema_docs(self):
        result = self.plotcanon("schema", "--write", "schema")

        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.root / "schema/vocabularies.yml").exists())
        self.assertTrue((self.root / "schema/after-action.md").exists())


class Instructions(CommandTest):
    def test_write_saves_the_instructions_for_a_new_mod_on_the_command_line(self):
        import plotcanon

        result = self.plotcanon("instructions", "--write", "prompts/mod-writer.md")

        self.assertEqual(result.returncode, 0)
        self.assertEqual((self.root / "prompts/mod-writer.md").read_text(encoding="utf-8"),
                         plotcanon.interview_instructions("new-mod", "cli"))

    def test_write_is_relative_to_the_root(self):
        result = self.plotcanon("instructions", "--write", "mod-writer.md",
                                "--root", str(self.root), cwd=Path(tempfile.mkdtemp()))

        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.root / "mod-writer.md").exists())

    def test_without_write_they_are_printed(self):
        import plotcanon

        result = self.plotcanon("instructions")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, plotcanon.interview_instructions("new-mod", "cli"))


if __name__ == "__main__":
    unittest.main()
