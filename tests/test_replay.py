import unittest
import os
import json
from replay_viewer import generate_replay_html

class TestReplayViewer(unittest.TestCase):

    def test_generate_replay_html(self):
        sample_history = {
            "civ": "Rome",
            "directive": "Focus on science",
            "total_turns": 2,
            "turns": [
                {
                    "turn": 0,
                    "civ_name": "Rome",
                    "stats": {"gold": 10, "gold_per_turn": 3, "science_per_turn": 4, "happiness": 9, "score": 10},
                    "tech": {"current_tech": "Pottery", "turns_to_finish": 5, "science_progress": 0, "science_cost": 25},
                    "cities": [{"name": "Rome", "location": [0, 0], "population": 1}],
                    "units": [{"name": "Warrior", "location": [1, 0], "is_military": True, "health": 100}],
                    "map": {
                        "tiles": [
                            {"x": 0, "y": 0, "terrain": "Grassland", "city": "Rome"},
                            {"x": 1, "y": 0, "terrain": "Plains", "military_unit": "Warrior"}
                        ]
                    },
                    "advisor": {"recommended_focus": "Science", "threat_level": "Low", "alerts": []},
                    "plan": {"reasoning": "Explore and grow."},
                    "execution": ["Unit Warrior moved towards (1, 0)"],
                    "notifications": ["Rome has been founded!"]
                },
                {
                    "turn": 1,
                    "civ_name": "Rome",
                    "stats": {"gold": 13, "gold_per_turn": 3, "science_per_turn": 5, "happiness": 9, "score": 35},
                    "tech": {"current_tech": "Pottery", "turns_to_finish": 4, "science_progress": 5, "science_cost": 25},
                    "cities": [{"name": "Rome", "location": [0, 0], "population": 1}],
                    "units": [{"name": "Warrior", "location": [2, 0], "is_military": True, "health": 100}],
                    "map": {
                        "tiles": [
                            {"x": 0, "y": 0, "terrain": "Grassland", "city": "Rome"},
                            {"x": 2, "y": 0, "terrain": "Plains", "military_unit": "Warrior"}
                        ]
                    },
                    "advisor": {"recommended_focus": "Science", "threat_level": "Low", "alerts": []},
                    "plan": {"reasoning": "Keep exploring."},
                    "execution": ["Unit Warrior moved towards (2, 0)"],
                    "notifications": []
                }
            ]
        }

        html = generate_replay_html(sample_history)
        self.assertIn("Unciv AI Replay Viewer - Rome", html)
        self.assertIn("Focus on science", html)
        self.assertIn("turnsData", html)
        self.assertIn("hex-canvas", html)
        self.assertIn("turn-slider", html)

if __name__ == "__main__":
    unittest.main()
