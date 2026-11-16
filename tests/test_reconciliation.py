"""The instructions for a Reconciliation, and reading what the LLM writes:
the app's LLM checks a draft Mod against the World's Canon and the other
drafts waiting for approval, and reports to the Plot Master."""

import unittest

import plotcanon

instructions = plotcanon.reconciliation_instructions

SURFACES = ("web", "cli")

DRAFT = """\
---
id: the-salt-ledger
type: mod
title: "The Salt Ledger"
aliases: ["The Salt Ledger"]
mod_writer: mira
events: [e03-storm-moon]
features:
  npcs: [harbour-clerk, ysolde-marr]
---

## Premise

A clerk keeps two ledgers, and the captain wants one of them burned.
"""

OTHER = """\
---
id: the-captains-last-order
type: mod
title: "The Captain's Last Order"
mod_writer: kay
events: [e03-storm-moon]
features:
  npcs: [ysolde-marr]
---

## Premise

The captain sails at dusk and does not come back.
"""

FINDINGS = (plotcanon.Finding("warning", "inbox/the-salt-ledger.md",
                              "features.npcs: 'harbour-clerk' is not in the World"),)


def reconciling(surface="web", **more):
    given = dict(draft=DRAFT, world=plotcanon.sample_world(), other_drafts=[OTHER],
                 findings=FINDINGS)
    given.update(more)
    return instructions(surface, **given)


class TheInstructions(unittest.TestCase):
    def test_both_surfaces_name_every_section_in_order(self):
        for surface in SURFACES:
            with self.subTest(surface):
                text = reconciling(surface)
                places = [text.find(f"## {heading}\n")
                          for heading in plotcanon.RECONCILIATION_SECTIONS]

                self.assertNotIn(-1, places)
                self.assertEqual(places, sorted(places))

    def test_the_sections_are_the_ones_the_plot_master_reads(self):
        self.assertEqual(plotcanon.RECONCILIATION_SECTIONS, (
            "Conflicts", "Warnings", "Missing links", "Slug mapping", "New entities",
            "Player agency", "Other drafts", "Proposed changes"))

    def test_the_draft_the_world_and_the_other_drafts_are_given(self):
        text = reconciling()

        self.assertIn("A clerk keeps two ledgers", text)
        self.assertIn("The captain sails at dusk and does not come back.", text)
        for document in plotcanon.load_world(plotcanon.sample_world()).world.documents:
            with self.subTest(document.id):
                self.assertIn(document.id, text)

    def test_with_no_other_drafts_it_says_there_are_none(self):
        text = reconciling(other_drafts=[])

        self.assertNotIn("The captain sails at dusk", text)
        self.assertIn("No other drafts are waiting for approval.", text)

    def test_the_check_findings_are_given_so_they_are_not_repeated(self):
        text = reconciling()

        self.assertIn("features.npcs: 'harbour-clerk' is not in the World", text)
        self.assertIn("Do not repeat", text)

    def test_findings_may_be_given_as_text(self):
        text = reconciling(findings=["WARN the clerk is unknown"])

        self.assertIn("WARN the clerk is unknown", text)

    def test_conflicts_are_judged_as_of_the_mods_earliest_event(self):
        flat = " ".join(reconciling().split())

        self.assertIn("A status is a claim about a point in time", flat)
        self.assertIn("earliest Event", flat)

    def test_it_keeps_the_rules_on_what_not_to_do(self):
        flat = " ".join(reconciling().split())
        for rule in ("Do not rewrite the Mod", "Do not choose a side",
                     "Do not invent Canon"):
            with self.subTest(rule):
                self.assertIn(rule, flat)

    def test_it_is_one_report_not_a_conversation(self):
        flat = " ".join(reconciling().split())

        self.assertIn("one report, not a conversation", flat)

    def test_on_the_cli_the_world_and_drafts_may_be_read_from_files(self):
        text = instructions("cli")
        flat = " ".join(text.split())

        self.assertIn("`inbox/`", text)
        self.assertIn("plotcanon validate", flat)

    def test_it_keeps_to_the_glossary(self):
        for surface in SURFACES:
            with self.subTest(surface):
                self.assertEqual(plotcanon.avoided_words(reconciling(surface)), [])
                self.assertEqual(plotcanon.avoided_words(instructions("cli")), [])


class WhatIsRefused(unittest.TestCase):
    def test_an_unknown_surface_is_refused(self):
        with self.assertRaises(ValueError):
            reconciling("email")

    def test_the_web_needs_the_draft_and_the_world(self):
        with self.assertRaises(ValueError):
            reconciling(draft=None)
        with self.assertRaises(ValueError):
            reconciling(world=None)

    def test_a_draft_or_other_draft_with_no_id_is_refused(self):
        with self.assertRaises(ValueError):
            reconciling(draft="no frontmatter")
        with self.assertRaises(ValueError):
            reconciling(other_drafts=["no frontmatter"])

    def test_values_of_the_wrong_type_raise_type_error(self):
        with self.assertRaises(TypeError):
            reconciling(draft=3)
        with self.assertRaises(TypeError):
            reconciling(other_drafts=OTHER)
        with self.assertRaises(TypeError):
            reconciling(findings="one finding")


if __name__ == "__main__":
    unittest.main()
