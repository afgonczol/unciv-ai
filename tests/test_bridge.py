"""
Unit tests for the Unciv Java Bridge and Python SDK.
"""

import unittest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unciv_engine import UncivEngine, UncivEngineError

class TestUncivBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = UncivEngine()

    @classmethod
    def tearDownClass(cls):
        if cls.engine:
            cls.engine.close()

    def test_01_ping(self):
        self.assertTrue(self.engine.ping())

    def test_02_new_game(self):
        res = self.engine.new_game(nation="Rome", difficulty="Chieftain", ruleset="Civ V - Vanilla", map_size="Tiny")
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("active_civ"), "Rome")
        self.assertEqual(res.get("turn"), 0)

    def test_03_get_state(self):
        state = self.engine.get_state()
        self.assertEqual(state.get("active_civ"), "Rome")
        self.assertIn("stats", state)
        self.assertIn("technology", state)
        self.assertIn("policies", state)
        self.assertIn("units", state)
        self.assertGreater(len(state.get("units", [])), 0)

    def test_04_get_map(self):
        map_data = self.engine.get_map(0, 0, 4)
        self.assertIn("ascii_view", map_data)
        self.assertIn("tiles", map_data)
        self.assertGreater(len(map_data.get("tiles", [])), 0)

    def test_05_choose_tech(self):
        state = self.engine.get_state()
        techs = [t["name"] for t in state.get("technology", {}).get("researchable_techs", [])]
        self.assertIn("Pottery", techs)
        res = self.engine.choose_tech("Pottery")
        self.assertEqual(res.get("status"), "ok")

        state = self.engine.get_state()
        self.assertEqual(state.get("technology", {}).get("current_tech"), "Pottery")

    def test_06_unit_action_and_found_city(self):
        state = self.engine.get_state()
        units = state.get("units", [])
        settler = next((u for u in units if u.get("name") == "Settler"), None)
        self.assertIsNotNone(settler)

        res = self.engine.unit_action(settler["id"], "found_city")
        self.assertEqual(res.get("status"), "ok")
        self.assertIn("City founded", res.get("message", ""))

        state = self.engine.get_state()
        cities = state.get("cities", [])
        self.assertGreaterEqual(len(cities), 1)

    def test_07_city_action(self):
        state = self.engine.get_state()
        cities = state.get("cities", [])
        self.assertGreaterEqual(len(cities), 1)
        city_name = cities[0]["name"]

        res = self.engine.city_action(city_name, "set_production", "Scout")
        self.assertEqual(res.get("status"), "ok")

        state = self.engine.get_state()
        self.assertEqual(state["cities"][0].get("current_construction"), "Scout")

    def test_08_end_turn(self):
        res = self.engine.end_turn()
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("old_turn"), 0)
        self.assertEqual(res.get("new_turn"), 1)

    def test_09_save_and_load(self):
        save_data = self.engine.save_game()
        self.assertGreater(len(save_data), 50)

        load_res = self.engine.load_game(save_data)
        self.assertEqual(load_res.get("status"), "ok")
        self.assertEqual(load_res.get("turn"), 1)

if __name__ == "__main__":
    unittest.main()
