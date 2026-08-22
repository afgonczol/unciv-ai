"""
Model Context Protocol (MCP) Server for Unciv.
Exposes tools, resources, and prompts over standard MCP JSON-RPC protocol
for LLMs and AI agent frameworks (Claude Desktop, Cursor, Custom Agent loops).
"""

import json
import sys
import os
import argparse
from typing import Dict, Any, List, Optional
from unciv_engine import UncivEngine
from strategic_advisor import StrategicAdvisor
from civilopedia import Civilopedia

SERVER_INFO = {
    "name": "unciv-mcp-server",
    "version": "1.0.0"
}

PROTOCOL_VERSION = "2024-11-05"

class UncivMCPServer:
    """
    Implements the Model Context Protocol (MCP) server for Unciv.
    """

    def __init__(self, engine: Optional[UncivEngine] = None, advisor: Optional[StrategicAdvisor] = None):
        self.engine = engine or UncivEngine()
        self.advisor = advisor or StrategicAdvisor()
        self.civilopedia = Civilopedia(self.engine)

    def get_tools_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "unciv_get_game_overview",
                "description": "Returns a comprehensive overview of the active civilization, turn number, stats (gold, science, culture, faith, happiness, score), active research, policies, cities, and notifications.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "unciv_get_map_view",
                "description": "Fetches an ASCII map visualization and detailed tile information (terrain, features, resources, cities, units) within a given radius around specified coordinates.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "center_x": {"type": "integer", "description": "X coordinate for map center (default 0 or capital)"},
                        "center_y": {"type": "integer", "description": "Y coordinate for map center (default 0 or capital)"},
                        "radius": {"type": "integer", "description": "Radius in hex tiles (default 6)"}
                    }
                }
            },
            {
                "name": "unciv_get_city_details",
                "description": "Returns detailed statistics, construction queues, and buildable buildings/units for all player-owned cities or a specific city.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "city_name": {"type": "string", "description": "Optional city name to filter by"}
                    }
                }
            },
            {
                "name": "unciv_get_unit_list",
                "description": "Returns all owned military and civilian units with their IDs, coordinates, health, movement points, and available tactical actions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "unciv_unit_action",
                "description": "Executes a tactical action on a specific unit by its ID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "unit_id": {"type": "integer", "description": "Unique ID of the unit"},
                        "action": {
                            "type": "string",
                            "enum": ["move", "attack", "found_city", "improve_tile", "fortify", "sleep", "wake", "promote", "disband"],
                            "description": "Action to perform"
                        },
                        "target_x": {"type": "integer", "description": "Target X coordinate for move/attack"},
                        "target_y": {"type": "integer", "description": "Target Y coordinate for move/attack"},
                        "param": {"type": "string", "description": "Parameter (e.g. improvement name 'Farm'/'Mine', promotion name)"}
                    },
                    "required": ["unit_id", "action"]
                }
            },
            {
                "name": "unciv_city_action",
                "description": "Manages a city's construction queue, purchasing, or citizen focus.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "city_name": {"type": "string", "description": "Name of the target city"},
                        "action": {
                            "type": "string",
                            "enum": ["set_production", "add_to_queue", "purchase", "set_focus"],
                            "description": "Action to perform in the city"
                        },
                        "param": {"type": "string", "description": "Item to produce/purchase (e.g. 'Scout', 'Monument', 'Library') or focus ('Food', 'Production', 'Gold')"}
                    },
                    "required": ["city_name", "action", "param"]
                }
            },
            {
                "name": "unciv_choose_research",
                "description": "Selects a technology for active scientific research.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tech_name": {"type": "string", "description": "Name of the technology (e.g. 'Pottery', 'Writing', 'Archery')"}
                    },
                    "required": ["tech_name"]
                }
            },
            {
                "name": "unciv_choose_policy",
                "description": "Adopts an available social policy (e.g. 'Tradition', 'Liberty', 'Honor').",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "policy_name": {"type": "string", "description": "Name of the policy"}
                    },
                    "required": ["policy_name"]
                }
            },
            {
                "name": "unciv_diplomacy",
                "description": "Executes diplomatic relations with another known civilization.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_civ": {"type": "string", "description": "Name of the target civilization"},
                        "action": {
                            "type": "string",
                            "enum": ["declare_war", "make_peace"],
                            "description": "Diplomatic action"
                        }
                    },
                    "required": ["target_civ", "action"]
                }
            },
            {
                "name": "unciv_strategic_advisor",
                "description": "Runs tactical and strategic analysis on current empire state, returning military threat level, settling site recommendations, tech priority roadmap, and bottleneck warnings.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "unciv_set_strategic_directive",
                "description": "Configures dynamic user strategy and priorities (e.g. 'Focus on science and be aggressive against European nations'). This modifies advisor scoring and recommendations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "directive": {"type": "string", "description": "Natural language strategy prompt"}
                    },
                    "required": ["directive"]
                }
            },
            {
                "name": "unciv_end_turn",
                "description": "Advances the turn, simulates all other civilizations and barbarians, and returns new turn notifications.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "unciv_new_game",
                "description": "Starts a new game with specified civilization, difficulty, and ruleset.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "nation": {"type": "string", "description": "Civilization name (e.g. 'Rome', 'Greece', 'America')"},
                        "difficulty": {"type": "string", "description": "Difficulty (e.g. 'Settler', 'Chieftain', 'Warlord', 'Prince', 'King', 'Emperor', 'Immortal', 'Deity')", "default": "Prince"},
                        "ruleset": {"type": "string", "description": "Ruleset name", "default": "Civ V - Vanilla"},
                        "map_size": {"type": "string", "description": "Map size: 'Tiny', 'Small', 'Medium', 'Large', 'Huge'", "default": "Tiny"}
                    }
                }
            },
            {
                "name": "unciv_save_game",
                "description": "Serializes and returns the current game state as a save string.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "unciv_load_game",
                "description": "Restores a game from a save string.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "save_data": {"type": "string", "description": "Save data string"}
                    },
                    "required": ["save_data"]
                }
            },
            {
                "name": "unciv_civilopedia_lookup",
                "description": "Queries exact stats, costs, yields, prerequisites, and unique abilities for any unit, building, wonder, technology, policy, or civilization from the active game ruleset.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["unit", "building", "wonder", "tech", "policy", "nation", "improvement", "all"], "description": "Category to query"},
                        "name": {"type": "string", "description": "Specific item name (e.g. 'Legion', 'Library', 'Iron Working', 'Tradition', 'Rome')"}
                    }
                }
            },
            {
                "name": "unciv_civilopedia_search",
                "description": "Searches the active game ruleset (Civilopedia) for all items matching a keyword (e.g. 'science', 'happiness', 'defense', 'iron').",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "unciv_civilization_dossier",
                "description": "Generates a Civilization Strategic Dossier summarizing unique abilities, unique units, unique buildings, and traits for any civilization in the active ruleset.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "civilization": {"type": "string", "description": "Civilization name (e.g. 'Rome', 'Greece', 'China')"}
                    },
                    "required": ["civilization"]
                }
            }
        ]

    def get_resources_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "uri": "unciv://game/state",
                "name": "Current Unciv Game State",
                "description": "Real-time game state containing civ stats, tech tree, cities, units, diplomacy, and notifications.",
                "mimeType": "application/json"
            },
            {
                "uri": "unciv://game/advisor",
                "name": "Strategic AI Advisor Report",
                "description": "Strategic analysis, military threat radar, candidate city locations, and action recommendations.",
                "mimeType": "application/json"
            },
            {
                "uri": "unciv://game/map",
                "name": "Explored World Map",
                "description": "ASCII grid view and tile data of the explored map.",
                "mimeType": "text/plain"
            }
        ]

    def get_prompts_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "unciv_turn_planning",
                "description": "Evaluates current turn state, analyzes advisor recommendations, and plans optimal unit moves, city production, and research.",
                "arguments": []
            },
            {
                "name": "unciv_war_council",
                "description": "Conducts a military tactical assessment against rival civilizations and plans army movements and city captures.",
                "arguments": [
                    {"name": "target_civ", "description": "Civilization to target", "required": False}
                ]
            },
            {
                "name": "unciv_expansion_plan",
                "description": "Evaluates candidate settlement sites and designs an empire expansion roadmap.",
                "arguments": []
            }
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches a tool call to the engine or advisor.
        """
        try:
            if name == "unciv_get_game_overview":
                state = self.engine.get_state()
                return {
                    "content": [{"type": "text", "text": json.dumps(state, indent=2)}]
                }

            elif name == "unciv_get_map_view":
                cx = arguments.get("center_x", 0)
                cy = arguments.get("center_y", 0)
                r = arguments.get("radius", 6)
                map_res = self.engine.get_map(cx, cy, r)
                return {
                    "content": [
                        {"type": "text", "text": map_res.get("ascii_view", "")},
                        {"type": "text", "text": f"Tile Details ({len(map_res.get('tiles', []))} tiles):\n" + json.dumps(map_res.get("tiles", []), indent=2)}
                    ]
                }

            elif name == "unciv_get_city_details":
                state = self.engine.get_state()
                cities = state.get("cities", [])
                target = arguments.get("city_name")
                if target:
                    cities = [c for c in cities if c.get("name", "").lower() == target.lower()]
                return {
                    "content": [{"type": "text", "text": json.dumps(cities, indent=2)}]
                }

            elif name == "unciv_get_unit_list":
                state = self.engine.get_state()
                units = state.get("units", [])
                return {
                    "content": [{"type": "text", "text": json.dumps(units, indent=2)}]
                }

            elif name == "unciv_unit_action":
                res = self.engine.unit_action(
                    unit_id=arguments["unit_id"],
                    action=arguments["action"],
                    target_x=arguments.get("target_x", 0),
                    target_y=arguments.get("target_y", 0),
                    param=arguments.get("param", "")
                )
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_city_action":
                res = self.engine.city_action(
                    city_name=arguments["city_name"],
                    action=arguments["action"],
                    param=arguments.get("param", ""),
                    target_x=arguments.get("target_x", 0),
                    target_y=arguments.get("target_y", 0)
                )
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_choose_research":
                res = self.engine.choose_tech(arguments["tech_name"])
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_choose_policy":
                res = self.engine.adopt_policy(arguments["policy_name"])
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_diplomacy":
                res = self.engine.diplomacy_action(
                    target_civ=arguments["target_civ"],
                    action=arguments["action"]
                )
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_strategic_advisor":
                state = self.engine.get_state()
                map_res = self.engine.get_map(0, 0, 6)
                advice = self.advisor.analyze(state, map_res)
                return {
                    "content": [{"type": "text", "text": json.dumps(advice, indent=2)}]
                }

            elif name == "unciv_set_strategic_directive":
                directive = arguments.get("directive", "")
                self.advisor.set_directive(directive)
                return {
                    "content": [{"type": "text", "text": f"Strategic directive set to: '{directive}'. Advisor weights updated: {json.dumps(self.advisor.directive_weights)}"}]
                }

            elif name == "unciv_end_turn":
                res = self.engine.end_turn()
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_new_game":
                nation = arguments.get("nation", "")
                difficulty = arguments.get("difficulty", "Prince")
                ruleset = arguments.get("ruleset", "Civ V - Vanilla")
                map_size = arguments.get("map_size", "Tiny")
                res = self.engine.new_game(nation, difficulty, ruleset, map_size)
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_save_game":
                save_data = self.engine.save_game()
                return {
                    "content": [{"type": "text", "text": f"Game saved successfully. (Bytes: {len(save_data)})\nSaveData: {save_data}"}]
                }

            elif name == "unciv_load_game":
                res = self.engine.load_game(arguments["save_data"])
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_civilopedia_lookup":
                cat = arguments.get("category", "all")
                item = arguments.get("name", "")
                if item:
                    res = self.engine.query_civilopedia(category=cat, name=item)
                else:
                    res = self.engine.query_civilopedia(category=cat)
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_civilopedia_search":
                q = arguments.get("query", "")
                res = self.civilopedia.search(q)
                return {
                    "content": [{"type": "text", "text": json.dumps(res, indent=2)}]
                }

            elif name == "unciv_civilization_dossier":
                civ = arguments.get("civilization", "Rome")
                dossier = self.civilopedia.get_civ_dossier(civ)
                return {
                    "content": [{"type": "text", "text": json.dumps(dossier, indent=2)}]
                }

            else:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Unknown tool: {name}"}]
                }

        except Exception as e:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Error executing tool {name}: {e}"}]
            }

    def read_resource(self, uri: str) -> Dict[str, Any]:
        if uri == "unciv://game/state":
            state = self.engine.get_state()
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(state, indent=2)
                }]
            }
        elif uri == "unciv://game/advisor":
            state = self.engine.get_state()
            map_res = self.engine.get_map(0, 0, 6)
            advice = self.advisor.analyze(state, map_res)
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(advice, indent=2)
                }]
            }
        elif uri == "unciv://game/map":
            map_res = self.engine.get_map(0, 0, 8)
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": map_res.get("ascii_view", "")
                }]
            }
        else:
            raise ValueError(f"Resource not found: {uri}")

    def get_prompt(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        state = self.engine.get_state()
        map_res = self.engine.get_map(0, 0, 6)
        advice = self.advisor.analyze(state, map_res)

        if name == "unciv_turn_planning":
            return {
                "description": "Turn Planning Prompt",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"You are playing Civilization (Unciv). Current Turn: {state.get('turn')}, Civ: {state.get('active_civ')}.\n"
                                    f"Stats: Gold={state.get('stats', {}).get('gold')}, Science/Turn={state.get('stats', {}).get('science_per_turn')}, Happiness={state.get('stats', {}).get('happiness')}.\n\n"
                                    f"Strategic Advisor Recommendations:\n{json.dumps(advice.get('suggested_actions', []), indent=2)}\n\n"
                                    f"Bottlenecks/Alerts:\n{json.dumps(advice.get('bottlenecks_and_alerts', []), indent=2)}\n\n"
                                    f"Map View:\n{map_res.get('ascii_view', '')}\n\n"
                                    f"Decide on unit moves, city production, research, and call the appropriate MCP tools before finishing with unciv_end_turn."
                        }
                    }
                ]
            }
        elif name == "unciv_war_council":
            target = arguments.get("target_civ") or "Enemy Civilizations"
            mil = advice.get("military_assessment", {})
            return {
                "description": "War Council Prompt",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Military War Council: Target = {target}.\n"
                                    f"Military Units: {mil.get('military_units_count')}, Threat Level: {mil.get('threat_level')}, Active Wars: {mil.get('active_wars')}.\n"
                                    f"Units Overview:\n{json.dumps(state.get('units', []), indent=2)}\n\n"
                                    f"Formulate a battle plan to defeat hostile units and capture enemy cities using tactical maneuvers."
                        }
                    }
                ]
            }
        elif name == "unciv_expansion_plan":
            exp = advice.get("expansion_analysis", {})
            return {
                "description": "Expansion Planning Prompt",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Empire Expansion Plan:\nCurrent Cities: {exp.get('city_count')}, Settlers Available: {exp.get('settlers_available')}.\n"
                                    f"Candidate Settlement Spots:\n{json.dumps(exp.get('recommended_next_settle_spots', []), indent=2)}\n\n"
                                    f"Evaluate terrain yields, luxury/strategic resources, and defense to direct our settlers to prime locations."
                        }
                    }
                ]
            }
        else:
            raise ValueError(f"Prompt not found: {name}")

    def handle_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "serverInfo": SERVER_INFO,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False}
                    }
                }
            }

        elif method == "notifications/initialized":
            return None

        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {}
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tools_list()
                }
            }

        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {})
            res = self.call_tool(name, args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": res
            }

        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": self.get_resources_list()
                }
            }

        elif method == "resources/read":
            uri = params.get("uri", "")
            try:
                res = self.read_resource(uri)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": res
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": str(e)}
                }

        elif method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "prompts": self.get_prompts_list()
                }
            }

        elif method == "prompts/get":
            name = params.get("name", "")
            args = params.get("arguments", {})
            try:
                res = self.get_prompt(name, args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": res
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": str(e)}
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }

    def run_stdio(self):
        """Runs the MCP server over standard input and output."""
        sys.stderr.write("Starting Unciv MCP Server (stdio mode)...\n")
        sys.stderr.flush()

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
                res = self.handle_request(req)
                if res is not None:
                    sys.stdout.write(json.dumps(res) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                sys.stderr.write(f"Error handling MCP request: {e}\n")
                sys.stderr.flush()

if __name__ == "__main__":
    server = UncivMCPServer()
    server.run_stdio()
