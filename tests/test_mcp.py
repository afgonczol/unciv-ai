"""
Unit tests for Unciv Model Context Protocol (MCP) Server.
"""

import unittest
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unciv_engine import UncivEngine
from strategic_advisor import StrategicAdvisor
from unciv_mcp_server import UncivMCPServer

class TestUncivMCPServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = UncivEngine()
        cls.advisor = StrategicAdvisor()
        cls.server = UncivMCPServer(engine=cls.engine, advisor=cls.advisor)
        cls.server.call_tool("unciv_new_game", {"nation": "Rome", "difficulty": "Chieftain", "map_size": "Tiny"})

    @classmethod
    def tearDownClass(cls):
        if cls.engine:
            cls.engine.close()

    def test_01_initialize(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }
        res = self.server.handle_request(req)
        self.assertEqual(res.get("id"), 1)
        self.assertIn("serverInfo", res.get("result", {}))
        self.assertEqual(res["result"]["serverInfo"]["name"], "unciv-mcp-server")

    def test_02_tools_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        res = self.server.handle_request(req)
        tools = res.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        self.assertIn("unciv_get_game_overview", tool_names)
        self.assertIn("unciv_get_map_view", tool_names)
        self.assertIn("unciv_unit_action", tool_names)
        self.assertIn("unciv_city_action", tool_names)
        self.assertIn("unciv_choose_research", tool_names)
        self.assertIn("unciv_strategic_advisor", tool_names)
        self.assertIn("unciv_set_strategic_directive", tool_names)
        self.assertIn("unciv_end_turn", tool_names)

    def test_03_strategic_directive_tool(self):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "unciv_set_strategic_directive",
                "arguments": {
                    "directive": "Focus on science and be aggressive against players that control European nations"
                }
            }
        }
        res = self.server.handle_request(req)
        self.assertIn("Strategic directive set", res["result"]["content"][0]["text"])

    def test_04_strategic_advisor_tool(self):
        req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "unciv_strategic_advisor",
                "arguments": {}
            }
        }
        res = self.server.handle_request(req)
        advisor_json = json.loads(res["result"]["content"][0]["text"])
        self.assertIn("recommended_focus", advisor_json)
        self.assertIn("military_assessment", advisor_json)
        self.assertIn("technology_roadmap", advisor_json)

    def test_05_resources_and_prompts(self):
        # Resources list
        res_list = self.server.handle_request({"jsonrpc": "2.0", "id": 5, "method": "resources/list"})
        uris = [r["uri"] for r in res_list["result"]["resources"]]
        self.assertIn("unciv://game/state", uris)
        self.assertIn("unciv://game/advisor", uris)

        # Resource read
        res_read = self.server.handle_request({"jsonrpc": "2.0", "id": 6, "method": "resources/read", "params": {"uri": "unciv://game/state"}})
        self.assertIn("contents", res_read["result"])

        # Prompts list
        prompts = self.server.handle_request({"jsonrpc": "2.0", "id": 7, "method": "prompts/list"})
        p_names = [p["name"] for p in prompts["result"]["prompts"]]
        self.assertIn("unciv_turn_planning", p_names)
        self.assertIn("unciv_war_council", p_names)

if __name__ == "__main__":
    unittest.main()
