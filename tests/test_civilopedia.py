import unittest
from unciv_engine import UncivEngine
from civilopedia import Civilopedia

class TestCivilopedia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = UncivEngine()
        cls.engine.new_game(nation="Rome", difficulty="Prince", map_size="Tiny", map_type="Pangaea")
        cls.cp = Civilopedia(cls.engine)
        cls.cp.load_active_ruleset()

    @classmethod
    def tearDownClass(cls):
        cls.engine.close()

    def test_01_query_units(self):
        units = self.engine.query_civilopedia(category="units")
        self.assertIn("units", units)
        self.assertTrue(len(units["units"]) > 10)
        legion = self.cp.get_unit("Legion")
        self.assertIsNotNone(legion)
        self.assertEqual(legion.get("name"), "Legion")
        self.assertEqual(legion.get("strength"), 13)

    def test_02_query_buildings(self):
        monument = self.cp.get_building("Monument")
        self.assertIsNotNone(monument)
        self.assertEqual(monument.get("culture"), 2)
        self.assertEqual(monument.get("cost"), 40)

    def test_03_query_techs(self):
        pottery = self.cp.get_tech("Pottery")
        self.assertIsNotNone(pottery)
        self.assertEqual(pottery.get("cost"), 35)
        self.assertIn("Granary", pottery.get("unlocked_buildings", []))

    def test_04_query_policies(self):
        tradition = self.cp.get_policy("Tradition")
        self.assertIsNotNone(tradition)
        self.assertTrue(len(tradition.get("uniques", [])) > 0)

    def test_05_civ_dossier(self):
        dossier = self.cp.get_civ_dossier("Rome")
        self.assertEqual(dossier.get("civilization"), "Rome")
        self.assertTrue(any(u["name"] == "Legion" for u in dossier.get("unique_units", [])))
        self.assertTrue(len(dossier.get("unique_ability_effects", [])) > 0)

    def test_06_annotation(self):
        ann_b = self.cp.annotate_item("building", "Monument")
        self.assertIn("Monument", ann_b)
        self.assertIn("+2 Culture", ann_b)

        ann_t = self.cp.annotate_item("tech", "Pottery")
        self.assertIn("Pottery", ann_t)
        self.assertIn("35 sci", ann_t)

    def test_07_search(self):
        results = self.cp.search("science")
        self.assertTrue(len(results) > 0)

if __name__ == "__main__":
    unittest.main()
