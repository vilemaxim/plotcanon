"""Which values in a document name other documents, and which documents name
a given one. A web app uses this to turn ids into links without guessing."""

import unittest

import plotcanon
from plotcanon import Reference


def sample():
    return plotcanon.load_world(plotcanon.sample_world()).world


class TheReferencesADocumentMakes(unittest.TestCase):
    def test_a_mod_refers_to_its_campaign_events_and_features(self):
        mod = sample().get("the-low-tide-market")

        self.assertEqual(plotcanon.references(mod), [
            Reference("campaign", "tideward"),
            Reference("events", "e01-low-tide", position=0),
            Reference("features", "ysolde-marr", position=0, part="npcs"),
            Reference("features", "tobren-vale", position=1, part="npcs"),
            Reference("features", "harbour-wardens", position=0, part="factions"),
            Reference("features", "salt-guild", position=1, part="factions"),
            Reference("features", "brackwater-harbour", position=0, part="locations"),
            Reference("features", "the-salt-tax-revolt", position=0, part="plots"),
        ])

    def test_a_persons_handle_is_not_a_reference_even_when_it_is_an_id(self):
        files = plotcanon.sample_world()
        files["canon/npcs/mira.md"] = files["canon/npcs/cutter-jass.md"].replace(
            "id: cutter-jass", "id: mira")
        world = plotcanon.load_world(files).world
        self.assertIsNotNone(world.get("mira"))

        mod = world.get("the-low-tide-market")

        self.assertEqual(mod.fields["mod_writer"], "mira")
        self.assertNotIn("mira", [ref.id for ref in plotcanon.references(mod)])
        self.assertNotIn(mod, plotcanon.referrers(world, "mira"))

    def test_a_report_refers_to_its_mod_event_pcs_and_the_entities_it_changed(self):
        report = sample().get("aa-the-tax-collectors-ledger")

        self.assertEqual(plotcanon.references(report), [
            Reference("mod", "the-tax-collectors-ledger"),
            Reference("event", "e01-low-tide"),
            Reference("pcs", "pc-wren-halloway", position=0),
            Reference("pcs", "pc-dask-orrin", position=1),
            Reference("canon_changes", "clerk-pell", position=0, part="entity"),
            Reference("canon_changes", "harrow-dunmore", position=1, part="entity"),
        ])

    def test_a_change_of_status_names_words_not_documents(self):
        files = plotcanon.sample_world()
        files["canon/npcs/alive.md"] = files["canon/npcs/cutter-jass.md"].replace(
            "id: cutter-jass", "id: alive")
        report = plotcanon.load_world(files).world.get("aa-the-tax-collectors-ledger")

        self.assertNotIn("alive", [ref.id for ref in plotcanon.references(report)])

    def test_a_change_of_location_names_the_places_moved_between(self):
        path = "after-actions/e01-low-tide/aa-the-tax-collectors-ledger.md"
        files = plotcanon.sample_world()
        files[path] = files[path].replace(
            "kind: status\n    decision: approved\n    from: alive\n    to: missing",
            "kind: location\n    decision: proposed\n"
            "    from: brackwater-harbour\n    to: the-salt-stair")
        report = plotcanon.check_file(files, path, files[path]).document

        self.assertEqual(
            [ref for ref in plotcanon.references(report) if ref.field == "canon_changes"], [
                Reference("canon_changes", "clerk-pell", position=0, part="entity"),
                Reference("canon_changes", "brackwater-harbour", position=0, part="from"),
                Reference("canon_changes", "the-salt-stair", position=0, part="to"),
                Reference("canon_changes", "harrow-dunmore", position=1, part="entity"),
            ])

    def test_an_npc_refers_to_its_factions_place_plots_and_events(self):
        npc = sample().get("tobren-vale")

        self.assertEqual(plotcanon.references(npc), [
            Reference("factions", "salt-guild", position=0),
            Reference("location", "the-salt-stair"),
            Reference("plots", "the-salt-tax-revolt", position=0),
            Reference("plots", "feud-of-vale-and-marr", position=1),
            Reference("as_of", "e01-low-tide"),
            Reference("first_seen", "e01-low-tide"),
        ])

    def test_first_seen_before_the_campaign_is_not_a_reference(self):
        npc = plotcanon.Document("canon/npcs/x.md", "npc", "x",
                                 {"first_seen": "pre-campaign", "as_of": "e01-low-tide"}, "")

        self.assertEqual(plotcanon.references(npc), [Reference("as_of", "e01-low-tide")])

    def test_a_timeline_entry_refers_to_its_event_and_what_it_involves(self):
        entry = plotcanon.Document("canon/timeline/x.md", "timeline", "x", {
            "event": "e01-low-tide", "era": "the-drowning",
            "involves": {"npcs": ["old-fenn"], "locations": ["saint-oreths-light"]}}, "")

        self.assertEqual(plotcanon.references(entry), [
            Reference("event", "e01-low-tide"),
            Reference("involves", "old-fenn", position=0, part="npcs"),
            Reference("involves", "saint-oreths-light", position=0, part="locations"),
        ])


class TheDocumentsThatReferToOne(unittest.TestCase):
    def test_an_npc_is_referred_to_by_the_mods_featuring_them_and_the_reports_changing_them(self):
        world = sample()

        ids = [d.id for d in plotcanon.referrers(world, world.get("tobren-vale"))]

        self.assertEqual(ids, [
            "salt-guild",                      # a member
            "feud-of-vale-and-marr",           # plots naming him
            "the-salt-tax-revolt",
            "the-guildmasters-daughter",       # Mods featuring him
            "the-wardens-ball",
            "the-low-tide-market",
            "the-tax-collectors-ledger",
            "aa-the-low-tide-market",          # the report that changed him
        ])

    def test_an_id_does_as_well_as_the_document(self):
        world = sample()

        self.assertEqual(plotcanon.referrers(world, "clerk-pell"),
                         plotcanon.referrers(world, world.get("clerk-pell")))

    def test_a_document_nothing_names_has_no_referrers(self):
        self.assertEqual(plotcanon.referrers(sample(), "no-such-id"), [])


class WhatToCallADocument(unittest.TestCase):
    def test_its_title_then_its_first_alias(self):
        world = sample()

        self.assertEqual(plotcanon.name_of(world, world.get("the-low-tide-market")),
                         "The Low Tide Market")
        self.assertEqual(plotcanon.name_of(world, world.get("tobren-vale")), "Tobren Vale")

    def test_a_report_after_its_mod_and_event(self):
        world = sample()

        self.assertEqual(plotcanon.name_of(world, world.get("aa-the-low-tide-market")),
                         "The Low Tide Market at Low Tide")

    def test_its_id_when_it_has_no_name(self):
        bare = plotcanon.Document("canon/npcs/x.md", "npc", "x", {"aliases": []}, "")

        self.assertEqual(plotcanon.name_of(sample(), bare), "x")


class WhichFieldsHoldAVocabularyValue(unittest.TestCase):
    def test_a_mods_state_canon_and_visibility(self):
        mod = sample().get("the-low-tide-market")

        self.assertEqual(plotcanon.vocabulary_fields(mod),
                         {"state": "mod_state", "canon": "canon", "visibility": "visibility"})

    def test_a_report_has_none_of_its_own(self):
        self.assertEqual(plotcanon.vocabulary_fields("after-action"), {})


if __name__ == "__main__":
    unittest.main()
