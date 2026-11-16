"""The instructions for an Interview: the text an LLM is given to help a Mod
Writer write a Mod, or revise one the Plot Master sent back."""

import re
import unittest

import plotcanon

instructions = plotcanon.interview_instructions

KINDS = ("new-mod", "revise-mod")
SURFACES = ("web", "cli")

DRAFT = """\
---
id: the-salt-ledger
type: mod
title: "The Salt Ledger"
aliases: ["The Salt Ledger"]
mod_writer: mira
features:
  npcs: [harbour-clerk]
---

## Premise

A clerk keeps two ledgers.
"""

REASON = "The clerk needs a second way in, and the ending is decided in advance."
FLAGS = (("harbour-clerk", "The clerk was arrested at the last Event."),
         ("ledger-house", "The house was burned by an approved Canon Change."))


def revising(surface="web", **more):
    return instructions("revise-mod", surface, draft=DRAFT, sent_back_reason=REASON,
                        flags=FLAGS, **more)


def every_output(world=None):
    for surface in SURFACES:
        yield f"new-mod/{surface}", instructions("new-mod", surface, world=world)
        yield f"revise-mod/{surface}", revising(surface, world=world)


class KindsAndSurfaces(unittest.TestCase):
    def test_every_kind_on_every_surface_has_instructions(self):
        for name, text in every_output():
            with self.subTest(name):
                self.assertIsInstance(text, str)
                self.assertGreater(len(text.strip()), 0)

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            instructions("report", "web")

    def test_an_unknown_surface_is_refused(self):
        with self.assertRaises(ValueError):
            instructions("new-mod", "email")


class TheDryRunConvention(unittest.TestCase):
    def test_the_example_story_passes_the_dry_run_check(self):
        for name, text in every_output():
            with self.subTest(name):
                examples = re.findall(r"```markdown\n(.*?)```", text, re.S)
                story = [e for e in examples if "Sister Oleen calls a night vigil" in e]
                self.assertEqual(len(story), 1)

                told = plotcanon.story(story[0])

                self.assertTrue(told.structured)
                self.assertEqual(told.problems, ())
                self.assertEqual(told.gaps, ())
                self.assertTrue(any(p.contests for p in told.passages))
                self.assertTrue(any(e.players_do_nothing for p in told.passages
                                    for e in p.exits))

    def test_each_rule_the_check_enforces_is_named(self):
        rules = [
            "`## Premise` is where a Dry Run starts",          # no Premise: no Dry Run
            "Each bullet under `## Hooks` names the scene",    # the Premise leads nowhere
            "`**Leads to:**",                                 # a scene's exits
            "`**If players do nothing:**",
            "`**Contest:**",
            "Each `###` under `## Possible Outcomes` is an ending",
            "A link is the target's heading text",
            "A label may not contain `,` or `;`",
            "A link line is one line: it may not wrap",
            "Every link leads to a scene or outcome that exists",
            "No two scenes or outcomes have the same heading",
            "at least one Hook leads on from it",
            "Every scene has something linking to it",
            "Every scene has at least one exit or a Contest",
            "Every Contest names at least two results",
            "Every outcome can be reached from the Premise",
        ]
        for name, text in every_output():
            flat = " ".join(text.split())
            for rule in rules:
                with self.subTest(name, rule=rule):
                    self.assertIn(rule, flat)


def sample():
    return plotcanon.load_world(plotcanon.sample_world()).world


class WhatThePersonMayRead(unittest.TestCase):
    def test_with_a_world_every_slug_in_it_is_given(self):
        world = sample()
        for name, text in every_output(plotcanon.sample_world()):
            for document in world.documents:
                with self.subTest(name, slug=document.id):
                    self.assertIn(document.id, text)

    def test_a_world_is_taken_in_any_form_a_world_is(self):
        files = plotcanon.sample_world()

        self.assertEqual(instructions("new-mod", "web", world=sample()),
                         instructions("new-mod", "web", world=files))

    def test_with_no_world_no_slug_from_one_is_given(self):
        world = sample()
        for name, text in every_output():
            for document in world.documents:
                with self.subTest(name, slug=document.id):
                    self.assertNotRegex(text, rf"(?<![\w-]){re.escape(document.id)}(?![\w-])")

    def test_a_document_left_out_of_the_world_never_appears(self):
        world = sample()
        # A Mod nothing else in the World names, so only its own file could
        # put its id, title or text into the instructions.
        left_out = world.get("the-guildmasters-daughter")
        files = plotcanon.sample_world()
        del files[left_out.path]
        del files["canon/plots/feud-of-vale-and-marr.md"]   # it lists the Mod
        premise = "what happened the night her uncle drowned"

        for name, text in every_output(files):
            with self.subTest(name):
                self.assertNotIn(left_out.id, text)
                self.assertNotIn(left_out.fields["title"], text)
                self.assertNotIn(left_out.path, text)
                self.assertNotIn(premise, text)

    def test_with_a_world_existing_slugs_are_used_and_only_new_things_proposed(self):
        with_world = instructions("new-mod", "web", world=plotcanon.sample_world())
        without = instructions("new-mod", "cli")

        self.assertIn("only if the Mod needs an NPC, faction, location or plot that is truly new",
                      " ".join(with_world.split()))
        self.assertIn("including ones you are sure already exist", " ".join(without.split()))


class Revising(unittest.TestCase):
    def test_the_draft_its_send_back_reason_and_its_flags_are_given(self):
        for surface in SURFACES:
            with self.subTest(surface):
                text = revising(surface)

                self.assertIn("the-salt-ledger", text)
                self.assertIn("A clerk keeps two ledgers.", text)
                self.assertIn(REASON, text)
                for feature, message in FLAGS:
                    self.assertIn(feature, text)
                    self.assertIn(message, text)

    def test_the_draft_keeps_its_id(self):
        flat = " ".join(revising().split())

        self.assertIn("Keep `id: the-salt-ledger` exactly as it is", flat)

    def test_the_conversation_starts_with_the_reason_and_the_flags(self):
        flat = " ".join(revising().split())

        self.assertIn("Start the conversation by working through why the Plot Master sent "
                      "the draft back, and then each Flag on it", flat)

    def test_a_draft_may_come_back_with_no_reason_and_no_flags(self):
        text = instructions("revise-mod", "cli", draft=DRAFT)

        self.assertIn("the-salt-ledger", text)
        self.assertIn("The Plot Master gave no reason", text)
        self.assertIn("There are no open Flags on it", text)

    def test_revising_needs_a_draft(self):
        with self.assertRaises(ValueError):
            instructions("revise-mod", "web")

    def test_a_draft_with_no_id_is_refused(self):
        with self.assertRaises(ValueError):
            instructions("revise-mod", "web", draft="## Premise\n\nNo frontmatter.\n")

    def test_a_new_mod_has_no_draft(self):
        with self.assertRaises(ValueError):
            instructions("new-mod", "web", draft=DRAFT)
        with self.assertRaises(ValueError):
            instructions("new-mod", "web", flags=FLAGS)


class Wording(unittest.TestCase):
    def test_every_output_keeps_to_the_glossary(self):
        for world in (None, plotcanon.sample_world()):
            for name, text in every_output(world):
                with self.subTest(name, world=world is not None):
                    self.assertEqual(plotcanon.avoided_words(text), [])
