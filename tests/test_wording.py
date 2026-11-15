"""The words the schema uses.

Both projects share one vocabulary (the glossary in rpg-plot-helper), and each
term there lists the words not to use for it. Everything this package ships
that a person reads — the schema docs, the validator's messages and the sample
World — keeps to it, so nobody has to learn that an "author" is a Mod Writer.
"""

import re
import unittest

import plotcanon

avoided_words = plotcanon.avoided_words


class Wording(unittest.TestCase):
    def assert_keeps_to_the_glossary(self, files):
        for name, text in files.items():
            with self.subTest(name):
                self.assertEqual(avoided_words(text), [])

    def test_the_schema_docs_keep_to_the_glossary(self):
        self.assert_keeps_to_the_glossary(plotcanon.schema_files())

    def test_the_sample_world_keeps_to_the_glossary(self):
        self.assert_keeps_to_the_glossary(plotcanon.sample_world())
        self.assert_keeps_to_the_glossary({s.path: s.text for s in plotcanon.sample_script()})

    def test_an_avoided_word_is_found_and_named(self):
        found = plotcanon.avoided_words("The Author sent a module to the plot lead.")

        self.assertEqual(found, ["'Author' (use Mod Writer)", "'module' (use Mod)",
                                 "'plot lead' (use Plot Master)"])

    def test_ordinary_text_and_hyphenated_words_are_left_alone(self):
        self.assertEqual(plotcanon.avoided_words(
            "A session-wide rule. The Mod Writer is authoring a threadbare gameplay loop."), [])

    def test_a_role_playing_game_and_a_game_master_are_not_events(self):
        self.assertEqual(plotcanon.avoided_words(
            "Tabletop role-playing games. Ask the Game Master. A Game Master's notes."), [])

    def test_a_phrase_is_found_across_a_line_break_or_a_hyphen(self):
        self.assertEqual(plotcanon.avoided_words("Tell the plot\nlead, or any plot-lead."),
                         ["'plot lead' (use Plot Master)", "'plot-lead' (use Plot Master)"])

    def test_words_with_no_ordinary_use_here_are_on_the_list(self):
        for word in ("tenant", "superuser", "universe", "chronicle"):
            with self.subTest(word):
                self.assertTrue(plotcanon.avoided_words(f"The {word} is ready."))

    def test_the_schema_docs_name_roles_the_same_way_throughout(self):
        for name, text in plotcanon.schema_files().items():
            with self.subTest(name):
                self.assertEqual(re.findall(r"\bmod (?:writer|runner)s?\b", text), [])

    def test_the_validators_messages_keep_to_the_glossary(self):
        """A draft whose slugs do not resolve, claiming to be canon: the two
        places the validator used to talk about "authors"."""
        files = plotcanon.sample_world()
        draft = files["inbox/the-guildmasters-daughter.md"]
        files["inbox/the-guildmasters-daughter.md"] = (
            draft.replace("npcs: [mirelle-vale,", "npcs: [nobody-yet, mirelle-vale,")
            .replace("canon: proposed", "canon: approved")
            .replace("{entity: ysolde-marr, field: status", "{entity: someone-new, field: status"))

        report = plotcanon.load_world(files)

        self.assertEqual(len(report.findings), 3, report.text())
        self.assertEqual(avoided_words(report.text()), [])
        self.assertIn("Mod Writer", report.text())


if __name__ == "__main__":
    unittest.main()
