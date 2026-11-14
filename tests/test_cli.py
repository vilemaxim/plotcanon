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


if __name__ == "__main__":
    unittest.main()
