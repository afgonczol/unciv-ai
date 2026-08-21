"""
Unit tests for StrategicAdvisor heuristics and dynamic directive evaluator.
"""

import unittest
from strategic_advisor import StrategicAdvisor

class TestStrategicAdvisor(unittest.TestCase):
    def setUp(self):
        self.advisor = StrategicAdvisor()

    def test_dynamic_directive_parsing_science_and_europe(self):
        directive = "Focus on science and be aggressive against players that control European nations"
        self.advisor.set_directive(directive)

        self.assertGreater(self.advisor.directive_weights["science"], 2.0)
        self.assertGreater(self.advisor.directive_weights["military"], 2.0)
        self.assertIn("Rome", self.advisor.target_civilizations)
        self.assertIn("Greece", self.advisor.target_civilizations)
        self.assertIn("England", self.advisor.target_civilizations)
        self.assertIn("France", self.advisor.target_civilizations)
        self.assertIn("Germany", self.advisor.target_civilizations)

    def test_directive_parsing_culture_and_expansion(self):
        directive = "Prioritize culture and rapid empire expansion"
        self.advisor.set_directive(directive)

        self.assertGreater(self.advisor.directive_weights["culture"], 1.5)
        self.assertGreater(self.advisor.directive_weights["expansion"], 1.5)

    def test_analysis_structure(self):
        self.advisor.set_directive("Focus on military domination against Asian nations")
        dummy_state = {
            "turn": 5,
            "active_civ": "Rome",
            "stats": {"gold": 100, "gold_per_turn": 5, "science_per_turn": 8, "happiness": 10, "score": 45},
            "technology": {
                "current_tech": "None",
                "turns_to_finish": 0,
                "researchable_techs": [
                    {"name": "Pottery", "cost": 35, "turns": 4},
                    {"name": "Archery", "cost": 35, "turns": 4},
                    {"name": "Writing", "cost": 55, "turns": 7}
                ]
            },
            "cities": [
                {
                    "name": "Rome",
                    "population": 2,
                    "food_per_turn": 3,
                    "production_per_turn": 4,
                    "current_construction": "",
                    "buildable_units": ["Warrior (40p)", "Scout (25p)"],
                    "buildable_buildings": ["Monument (40p)"]
                }
            ],
            "units": [
                {
                    "id": 1,
                    "name": "Warrior",
                    "location": [0, 0],
                    "movement": 2,
                    "is_military": True,
                    "is_idle": True
                }
            ],
            "known_civilizations": [
                {"civ_name": "China", "is_city_state": False, "is_alive": True, "is_at_war": False}
            ]
        }

        dummy_map = {
            "tiles": [
                {"x": 1, "y": 1, "terrain": "Grassland", "features": ["River"], "resource": "Wheat"},
                {"x": 0, "y": 0, "city": "Rome"}
            ]
        }

        report = self.advisor.analyze(dummy_state, dummy_map)

        self.assertIn("recommended_focus", report)
        self.assertIn("military_assessment", report)
        self.assertIn("expansion_analysis", report)
        self.assertIn("technology_roadmap", report)
        self.assertIn("suggested_actions", report)
        self.assertIn("bottlenecks_and_alerts", report)

        # Tech recommendations should prioritize Archery (military)
        techs = report["technology_roadmap"]["recommended_next_techs"]
        self.assertEqual(techs[0]["name"], "Archery")

        # Military target check
        mil = report["military_assessment"]
        self.assertIn("China", mil["target_civs_in_game"])

if __name__ == "__main__":
    unittest.main()
