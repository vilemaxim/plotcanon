"""Files from strangers.

The web app hands plotcanon uploads from the internet. Whatever is in a file,
the public functions report it as a finding. They do not raise, and they do
not let a small file use up the machine.
"""

import re
import time
import unittest

import yaml

import plotcanon

# Values of the wrong shape, to put where something else is expected.
WRONG_SHAPES = [None, 7, "", "not-an-id-that-exists", ["a"], [["a"]], {"a": "b"},
                [{"a": ["b"]}], [None, 1], {1: 2}]


def frontmatter(text):
    block = text.split("---\n", 2)[1]
    return yaml.safe_load(block)


def with_frontmatter(text, fields):
    body = text.split("---\n", 2)[2]
    return "---\n" + yaml.safe_dump(fields, sort_keys=False, allow_unicode=True) + "---\n" + body


def alias_bomb(levels=9, width=8):
    """YAML in which each value is a list of references to the one before:
    a few hundred bytes that stand for width ** levels values."""
    lines = ["a0: &a0 [x, x, x, x, x, x, x, x]"]
    for level in range(1, levels):
        refs = ", ".join([f"*a{level - 1}"] * width)
        lines.append(f"a{level}: &a{level} [{refs}]")
    return "\n".join(lines) + "\n"


class Aliases(unittest.TestCase):
    NPC = "canon/npcs/cutter-jass.md"

    def world_with(self, extra):
        files = plotcanon.sample_world()
        files[self.NPC] = files[self.NPC].replace("type: npc\n", "type: npc\n" + extra)
        return files

    def test_a_file_that_uses_an_alias_is_an_error_naming_the_file(self):
        report = plotcanon.load_world(self.world_with("first: &name [a, b]\nsecond: *name\n"))

        [error] = [e for e in report.errors if e.path == self.NPC]
        self.assertIn("alias", error.message)
        self.assertNotIn("\n", error.message)

    def test_the_file_built_to_exhaust_memory_is_refused_at_once(self):
        files = self.world_with(alias_bomb())
        started = time.perf_counter()

        report = plotcanon.load_world(files)

        self.assertLess(time.perf_counter() - started, 1.0)
        self.assertTrue([e for e in report.errors if e.path == self.NPC and "alias" in e.message])

    def test_it_is_refused_when_submitted_on_its_own_too(self):
        world = plotcanon.load_world(plotcanon.sample_world()).world
        text = self.world_with(alias_bomb())[self.NPC]
        started = time.perf_counter()

        report = plotcanon.check_file(world, self.NPC, text)

        self.assertLess(time.perf_counter() - started, 1.0)
        self.assertFalse(report.ok)
        self.assertIn("alias", report.text())

    def test_an_anchor_that_is_never_used_is_harmless(self):
        report = plotcanon.load_world(self.world_with("note: &unused hello\n"))

        self.assertEqual([e for e in report.errors if e.path == self.NPC], [])


class Limits(unittest.TestCase):
    NPC = "canon/npcs/cutter-jass.md"

    def test_a_very_large_file_is_refused_without_being_parsed(self):
        files = plotcanon.sample_world()
        files[self.NPC] = files[self.NPC] + ("word " * 300_000)
        started = time.perf_counter()

        report = plotcanon.load_world(files)

        self.assertLess(time.perf_counter() - started, 1.0)
        [error] = [e for e in report.errors if e.path == self.NPC]
        self.assertIn("larger than", error.message)

    def test_frontmatter_nested_absurdly_deep_is_refused(self):
        files = plotcanon.sample_world()
        deep = "deep: " + "[" * 400 + "]" * 400 + "\n"
        files[self.NPC] = files[self.NPC].replace("type: npc\n", "type: npc\n" + deep)

        report = plotcanon.load_world(files)

        [error] = [e for e in report.errors if e.path == self.NPC]
        self.assertIn("nested", error.message)

    def test_a_very_long_frontmatter_block_is_refused_without_being_parsed(self):
        """Parsing is far slower per character than reading, so the YAML block
        has a tighter limit than the file."""
        files = plotcanon.sample_world()
        long_list = "tags: [" + ", ".join(["word"] * 60_000) + "]\n"
        files[self.NPC] = files[self.NPC].replace("type: npc\n", "type: npc\n" + long_list)
        started = time.perf_counter()

        report = plotcanon.load_world(files)

        self.assertLess(time.perf_counter() - started, 1.0)
        [error] = [e for e in report.errors if e.path == self.NPC]
        self.assertIn("frontmatter is longer than", error.message)

    def test_ordinary_nesting_is_fine(self):
        self.assertEqual(plotcanon.load_world(plotcanon.sample_world()).text(), "")


class WrongShapes(unittest.TestCase):
    """Put a value of the wrong shape in every field of every document of the
    sample World, one at a time. Each must come back as a report, not an error
    raised."""

    # The documents the tests below change, plus enough of the sample World
    # round them for every kind of check to have something to look at. A
    # small World keeps thousands of validations quick; it does not have to
    # be a valid one, since every check runs whether or not an earlier one
    # found an error.
    KEEP = ("canon/campaigns/", "canon/events/", "canon/factions/harbour-wardens",
            "canon/locations/the-salt-stair", "canon/npcs/ysolde-marr",
            "canon/npcs/harrow-dunmore", "canon/npcs/clerk-pell", "canon/pcs/pc-dask-orrin",
            "canon/plots/the-salt-tax-revolt", "mods/tideward/blood-on-the-salt-stair",
            "mods/tideward/the-tax-collectors-ledger",
            "after-actions/e01-low-tide/aa-the-tax-collectors-ledger")

    @classmethod
    def setUpClass(cls):
        cls.files = {path: text for path, text in plotcanon.sample_world().items()
                     if path.startswith(cls.KEEP)}
        cls.files["canon/timeline/the-night-the-chapel-sank.md"] = (
            "---\nid: the-night-the-chapel-sank\ntype: timeline\naliases: [The night the chapel "
            "sank]\nera: recent-history\nin_world: thirty years ago\ninvolves:\n  npcs: "
            "[ysolde-marr]\ncanon: approved\nvisibility: public\n---\n\n## What Happened\n")

    def assert_reported(self, path, fields, what):
        files = dict(self.files)
        files[path] = with_frontmatter(self.files[path], fields)
        try:
            report = plotcanon.load_world(files)
        except Exception as error:  # noqa: BLE001 - the point is that nothing escapes
            self.fail(f"{path}: {what} raised {type(error).__name__}: {error}")
        self.assert_properly_reported(report, f"{path}: {what}")

    def assert_properly_reported(self, report, what):
        """Whatever was wrong was reported against a file. A finding against
        the World as a whole means a check raised and the last resort caught
        it: the caller was spared, but that is a fault to fix, not a pass."""
        faults = [f for f in report.findings if f.path == "(the World)"]
        self.assertEqual(faults, [], what)
        for finding in report.findings:
            self.assertNotIn("\n", finding.message, what)

    def test_a_wrongly_shaped_file_submitted_on_its_own_is_reported_too(self):
        path = "mods/tideward/blood-on-the-salt-stair.md"
        original = frontmatter(self.files[path])
        for field in original:
            for value in WRONG_SHAPES:
                text = with_frontmatter(self.files[path], {**original, field: value})
                try:
                    report = plotcanon.check_file(self.files, path, text)
                except Exception as error:  # noqa: BLE001
                    self.fail(f"{field} = {value!r} raised {type(error).__name__}: {error}")
                self.assert_properly_reported(report, f"{field} = {value!r}")

    def test_the_small_world_has_every_type_of_document(self):
        types = {frontmatter(text)["type"] for text in self.files.values()}

        self.assertEqual(types, {"campaign", "event", "faction", "location", "npc", "pc", "plot",
                                 "timeline", "mod", "after-action"})

    def one_of_each_type(self):
        """One document of each type: enough to reach every field the format has."""
        chosen = {}
        for path in sorted(self.files):
            chosen.setdefault(frontmatter(self.files[path])["type"], path)
        return sorted(chosen.values())

    def test_every_field_survives_every_wrong_shape(self):
        for path in self.one_of_each_type():
            original = frontmatter(self.files[path])
            for field in original:
                for value in WRONG_SHAPES:
                    self.assert_reported(path, {**original, field: value},
                                         f"{field} = {value!r}")

    def test_fields_a_document_should_not_have_survive_too(self):
        """A field that belongs to another type, such as `canon_changes` on an
        NPC, is only an unrecognised field. Its contents must not matter."""
        borrowed = ("features", "involves", "canon_changes", "requires", "expected_changes",
                    "mods", "entities", "events", "pcs", "members", "aliases", "mod", "event")
        for path in ("canon/npcs/ysolde-marr.md", "canon/plots/the-salt-tax-revolt.md",
                     "mods/tideward/blood-on-the-salt-stair.md",
                     "after-actions/e01-low-tide/aa-the-tax-collectors-ledger.md"):
            original = frontmatter(self.files[path])
            for field in borrowed:
                for value in WRONG_SHAPES:
                    self.assert_reported(path, {**original, field: value},
                                         f"{field} = {value!r}")

    def test_wrong_shapes_inside_a_list_of_canon_changes_survive(self):
        path = "after-actions/e01-low-tide/aa-the-tax-collectors-ledger.md"
        original = frontmatter(self.files[path])
        change = original["canon_changes"][0]
        for key in list(change) + ["entity", "kind", "decision", "from", "to", "summary"]:
            for value in WRONG_SHAPES:
                changes = [{**change, key: value}] + original["canon_changes"][1:]
                self.assert_reported(path, {**original, "canon_changes": changes},
                                     f"canon_changes[0].{key} = {value!r}")
        for value in WRONG_SHAPES:
            self.assert_reported(path, {**original, "canon_changes": [value]},
                                 f"canon_changes = [{value!r}]")

    def test_wrong_shapes_inside_features_and_requires_survive(self):
        path = "mods/tideward/blood-on-the-salt-stair.md"
        original = frontmatter(self.files[path])
        for group in list(original["features"]) + ["unknown-group"]:
            for value in WRONG_SHAPES:
                self.assert_reported(path, {**original,
                                            "features": {**original["features"], group: value}},
                                     f"features.{group} = {value!r}")
        clause = original["requires"][0]
        for key in list(clause) + ["equals", "in", "entity", "field"]:
            for value in WRONG_SHAPES:
                self.assert_reported(path, {**original, "requires": [{**clause, key: value}]},
                                     f"requires[0].{key} = {value!r}")
        for value in WRONG_SHAPES:
            self.assert_reported(path, {**original, "requires": [value]},
                                 f"requires = [{value!r}]")
            self.assert_reported(path, {**original, "expected_changes": {"x": value}},
                                 f"expected_changes.x = {value!r}")

    def test_an_id_or_a_type_of_the_wrong_shape_survives(self):
        for path in self.one_of_each_type():
            original = frontmatter(self.files[path])
            for field in ("id", "type"):
                for value in WRONG_SHAPES:
                    self.assert_reported(path, {**original, field: value},
                                         f"{field} = {value!r}")


class WhatAWrongShapeIsCalled(unittest.TestCase):
    """The error says what the field should have held, in words that fit."""

    NPC = "canon/npcs/cutter-jass.md"
    REPORT = "after-actions/e01-low-tide/aa-the-tax-collectors-ledger.md"
    MOD = "mods/tideward/blood-on-the-salt-stair.md"

    def errors_for(self, path, change):
        files = plotcanon.sample_world()
        fields = frontmatter(files[path])
        change(fields)
        files[path] = with_frontmatter(files[path], fields)
        return [e.message for e in plotcanon.load_world(files).errors if e.path == path]

    def test_the_tickets_own_case_names_the_file_and_the_field(self):
        errors = self.errors_for(self.NPC, lambda f: f.update(canon_changes=[1, {"entity": ["x"]}]))

        self.assertIn("canon_changes[0] must be a mapping", errors)
        self.assertIn("canon_changes[1].entity must be an id", errors)

    def test_a_mapping_where_one_id_belongs(self):
        errors = self.errors_for(self.REPORT, lambda f: f.update(mod={"a": "b"}))

        self.assertIn("`mod` must be one id", errors)

    def test_a_list_where_one_id_belongs(self):
        errors = self.errors_for(self.REPORT, lambda f: f.update(event=["e01-low-tide"]))

        self.assertIn("`event` must be one id, not a list", errors)

    def test_a_number_where_an_id_belongs(self):
        errors = self.errors_for(self.REPORT, lambda f: f.update(mod=7))

        self.assertIn("`mod` must be an id, got 7", errors)

    def test_a_list_inside_a_list_of_ids(self):
        def nest(fields):
            fields["features"]["npcs"] = [["ysolde-marr"]]

        errors = self.errors_for(self.MOD, nest)

        self.assertIn("`features.npcs` must be a list of ids", errors)

    def test_a_list_where_a_state_belongs_is_said_once(self):
        errors = self.errors_for(self.MOD, lambda f: f.update(state=["approved"]))

        self.assertEqual([e for e in errors if "state" in e],
                         ["`state` must be a single value, not a list"])

    def test_an_id_of_the_wrong_shape_is_said_once(self):
        errors = self.errors_for(self.NPC, lambda f: f.update(id=["cutter-jass"]))

        self.assertEqual([e for e in errors if "`id`" in e],
                         ["`id` must be a slug, got ['cutter-jass']"])


class ThingsAReviewFound(unittest.TestCase):
    """Inputs that once got past the checks and were only caught by the last
    resort, or cost far too much to check. Each is now an ordinary finding."""

    NPC = "canon/npcs/cutter-jass.md"
    MOD = "mods/tideward/blood-on-the-salt-stair.md"
    REPORT = "after-actions/e01-low-tide/aa-the-tax-collectors-ledger.md"

    def load(self, change, path=None):
        path = path or self.NPC
        files = plotcanon.sample_world()
        files[path] = change(files[path])
        report = plotcanon.load_world(files)
        self.assertEqual([f for f in report.findings if f.path == "(the World)"], [])
        report.text().encode("utf-8")  # What comes back can always be shown or stored.
        return report

    def errors(self, report, path=None):
        return [e.message for e in report.errors if e.path == (path or self.NPC)]

    def test_a_tag_that_does_not_fit_its_value(self):
        for extra in ("flag: !!bool foo\n", "when: !!timestamp foo\n", "n: !!int foo\n",
                      "f: !!float foo\n"):
            with self.subTest(extra):
                report = self.load(lambda t: t.replace("type: npc\n", "type: npc\n" + extra))
                [error] = self.errors(report)
                self.assertIn("frontmatter is not valid YAML", error)

    def test_a_number_too_large_to_be_meant(self):
        huge = "0x" + "F" * 5000
        for field in ("status", "as_of", "weight"):
            with self.subTest(field):
                def change(text, field=field):
                    if f"\n{field}: " in text:
                        return re.sub(rf"(?m)^{field}: .*$", f"{field}: {huge}", text)
                    return text.replace("type: npc\n", f"type: npc\n{field}: {huge}\n")

                report = self.load(change)
                self.assertTrue([e for e in self.errors(report) if "too large" in e],
                                self.errors(report))

    def test_an_id_made_of_thousands_of_digits(self):
        long_id = "aa-" + "9" * 5000
        files = plotcanon.sample_world()
        text = files.pop(self.REPORT).replace("id: aa-the-tax-collectors-ledger", f"id: {long_id}")
        files[f"after-actions/e01-low-tide/{long_id}.md"] = text

        report = plotcanon.load_world(files)

        self.assertEqual([f for f in report.findings if f.path == "(the World)"], [])
        self.assertTrue([e for e in report.errors if "is longer than" in e.message])

    def test_two_documents_sharing_a_name_when_one_has_no_id(self):
        files = plotcanon.sample_world()
        files["canon/npcs/nameless.md"] = files[self.NPC].replace("id: cutter-jass\n", "")

        report = plotcanon.load_world(files)

        self.assertEqual([f for f in report.findings if f.path == "(the World)"], [])
        self.assertFalse(report.ok)

    def test_an_event_whose_place_in_the_order_is_not_a_number(self):
        for ordinal in ("x", "[1]", "{a: 1}", "1.5", "true"):
            with self.subTest(ordinal):
                report = self.load(lambda t: t.replace("ordinal: 1\n", f"ordinal: {ordinal}\n"),
                                   path="canon/events/e01-low-tide.md")
                self.assertFalse(report.ok)

    def test_text_that_cannot_be_shown_is_refused_not_passed_on(self):
        for value in (r'"\ud800"', r'"a\0b"', r'"\e[31mred"'):
            with self.subTest(value):
                report = self.load(lambda t: t.replace('aliases: ["Cutter Jass", "Jass"]',
                                                       f'aliases: ["Cutter Jass", {value}]'))
                self.assertTrue([e for e in self.errors(report) if "cannot be shown" in e],
                                self.errors(report))

    def test_far_too_many_names_for_one_document(self):
        names = ", ".join(f'"Name {i}"' for i in range(2000))
        started = time.perf_counter()

        report = self.load(lambda t: t.replace('aliases: ["Cutter Jass", "Jass"]',
                                               f"aliases: [{names}]"))

        self.assertLess(time.perf_counter() - started, 3.0)
        self.assertTrue([e for e in self.errors(report) if "more than" in e], self.errors(report))

    def test_many_names_against_a_long_mod_are_checked_quickly(self):
        """Every name is looked for in every Mod's text. That must not be slow
        even with as many names and as much text as the limits allow."""
        files = plotcanon.sample_world()
        for number, path in enumerate(sorted(p for p in files if p.startswith("canon/npcs/"))):
            names = ", ".join(f'"Stranger {number} {i}"' for i in range(100))
            files[path] = files[path].replace("aliases: [", f"aliases: [{names}, ", 1)
        files[self.MOD] = files[self.MOD] + ("The stranger waits by the stair. " * 25_000)
        started = time.perf_counter()

        report = plotcanon.load_world(files)

        self.assertLess(time.perf_counter() - started, 5.0)
        self.assertEqual([f for f in report.findings if f.path == "(the World)"], [])

    def test_a_bad_requirement_does_not_renumber_the_ones_after_it(self):
        def change(text):
            return text.replace(
                "requires:\n", "requires:\n  - oops\n  - {entity: ysolde-marr, field: status, "
                                "equals: dead}\n", 1)

        report = self.load(change, path=self.MOD)
        findings = [f.message for f in report.findings if f.path == self.MOD]

        self.assertEqual(len([m for m in findings if m.startswith("requires[0]")]), 1, findings)
        self.assertTrue([m for m in findings if m.startswith("requires[1] expects")], findings)

    def test_a_malformed_canon_change_is_reported_once(self):
        for bad, expected in (("oops", "canon_changes[0] must be a mapping"),
                              ("{entity: [x], kind: narrative, decision: proposed, summary: s}",
                               "canon_changes[0].entity must be an id"),
                              ("{entity: clerk-pell, kind: [status], decision: proposed, "
                               "summary: s}", "canon_changes[0].kind must be a single value")):
            with self.subTest(bad):
                report = self.load(lambda t: t.replace("canon_changes:\n",
                                                       f"canon_changes:\n  - {bad}\n", 1),
                                   path=self.REPORT)
                about = [m for m in self.errors(report, self.REPORT)
                         if m.startswith("canon_changes[0]")]
                self.assertEqual(about, [expected])

    def test_a_list_of_ids_must_be_a_list(self):
        report = self.load(lambda t: t.replace("factions: []", "factions: harbour-wardens"))

        self.assertEqual([e for e in self.errors(report) if "factions" in e],
                         ["`factions` must be a list of ids"])

    def test_a_field_name_that_is_not_a_word(self):
        report = self.load(lambda t: t.replace("type: npc\n", "type: npc\n1: one\n~: nothing\n"))

        self.assertEqual(len([e for e in self.errors(report) if "is not a field name" in e]), 2)

    def test_frontmatter_that_is_a_value_and_not_fields(self):
        files = plotcanon.sample_world()
        for block in ("0", "[]", "false", '""'):
            with self.subTest(block):
                files[self.NPC] = f"---\n{block}\n---\n\nBody.\n"
                report = plotcanon.load_world(files)
                [error] = [e.message for e in report.errors if e.path == self.NPC]
                self.assertEqual(error, "frontmatter must be a mapping")


class TheLastResort(unittest.TestCase):
    def test_frontmatter_that_is_not_a_mapping_is_reported(self):
        files = plotcanon.sample_world()
        for block in ("- a\n- b\n", "just a string\n", "42\n", "\n"):
            with self.subTest(block):
                files["canon/npcs/cutter-jass.md"] = f"---\n{block}---\n\nBody.\n"
                report = plotcanon.load_world(files)
                self.assertFalse(report.ok)

    def test_yaml_only_tags_are_reported_or_stored_not_raised(self):
        files = plotcanon.sample_world()
        for extra in ("blob: !!binary aGVsbG8=\n", "keys: !!set {a, b}\n", "weight: .nan\n",
                      "when: 2026-05-02 10:00:00\n", "obj: !!python/object:os.system {}\n",
                      "? [a, b]\n: complex key\n", "1: a number as a key\n", "~: a null key\n"):
            with self.subTest(extra):
                files["canon/npcs/cutter-jass.md"] = self_files = plotcanon.sample_world()[
                    "canon/npcs/cutter-jass.md"].replace("type: npc\n", "type: npc\n" + extra)
                report = plotcanon.load_world(files)
                self.assertIsInstance(report.text(), str)
                self.assertIsInstance(
                    plotcanon.check_file(plotcanon.sample_world(), "canon/npcs/cutter-jass.md",
                                         self_files).text(), str)


if __name__ == "__main__":
    unittest.main()
