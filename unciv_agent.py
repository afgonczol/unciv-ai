"""
Unciv Strategic LLM Agent: Autonomous and Co-Pilot Game Playing Engine.
Supports OpenRouter, local llama.cpp server, Ollama, and OpenAI-compatible APIs.
Equipped with dynamic strategic directives, persistent scratchpad memory,
tactical tool execution, and rich ASCII terminal visualization.
"""

import json
import os
import sys
import time
import datetime
import argparse
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

from unciv_engine import UncivEngine, UncivEngineError
from strategic_advisor import StrategicAdvisor
from civilopedia import Civilopedia

class LLMClient:
    """
    Unified client supporting OpenRouter, llama.cpp server, Ollama, and OpenAI-compatible endpoints.
    """

    def __init__(self, api_base: str, api_key: str = "", model: str = ""):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        self.model = model or "meta-llama/llama-3.3-70b-instruct"

    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.4, max_tokens: int = 1500) -> str:
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if "openrouter" in self.api_base:
            headers["HTTP-Referer"] = "https://github.com/afgonczol/unciv-ai"
            headers["X-Title"] = "Unciv AI Strategic Agent"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                choices = res_json.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8") if e.fp else str(e)
            raise RuntimeError(f"HTTP {e.code} from LLM endpoint ({url}): {err_msg}")
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with LLM endpoint ({url}): {e}")

class UncivAgent:
    """
    Strategic LLM Agent playing Unciv autonomously or in Co-Pilot mode.
    """

    def __init__(self, engine: Optional[UncivEngine] = None, llm_client: Optional[LLMClient] = None,
                 strategy_directive: str = "", record_file: str = "replay_history.json", resume_history: bool = False):
        self.engine = engine or UncivEngine()
        self.advisor = StrategicAdvisor()
        self.civilopedia = Civilopedia(self.engine)
        self.llm = llm_client
        self.record_file = record_file
        self.history: List[Dict[str, Any]] = []
        if resume_history and self.record_file and os.path.exists(self.record_file):
            try:
                with open(self.record_file, "r", encoding="utf-8") as rf:
                    existing = json.load(rf)
                    if isinstance(existing, dict) and "turns" in existing:
                        self.history = existing["turns"]
            except Exception:
                pass
        self.scratchpad: Dict[str, Any] = {
            "grand_strategy": "",
            "active_military_campaign": "",
            "settlement_plan": "",
            "civilization_dossier": {},
            "turn_history": []
        }
        if strategy_directive:
            self.set_directive(strategy_directive)

    def set_directive(self, directive: str):
        self.advisor.set_directive(directive)
        self.scratchpad["grand_strategy"] = directive

    def play_turn(self, interactive: bool = False) -> Dict[str, Any]:
        """
        Executes one full strategic turn:
        1. Queries state, map, and strategic advisor
        2. Prompts LLM for decisions
        3. Parses and executes action plan
        4. Advances turn
        """
        state = self.engine.get_state()
        turn_num = state.get("turn", 0)
        civ_name = state.get("active_civ", "Unknown")

        # Cache Civilization Dossier in scratchpad (Turn 0 or initial load)
        if not self.scratchpad.get("civilization_dossier"):
            self.scratchpad["civilization_dossier"] = self.civilopedia.get_civ_dossier(civ_name)

        # Check if match has concluded
        if state.get("is_game_over"):
            winner = state.get("winner", "Unknown")
            v_type = state.get("victory_type", "Victory")
            print(f"\n{'='*60}")
            if winner == civ_name:
                print(f" 🏆 VICTORY! {civ_name} achieved {v_type} on Turn {turn_num}!")
            else:
                print(f" 🏁 GAME OVER: {winner} achieved victory via {v_type} on Turn {turn_num}.")
            print(f"{'='*60}\n")
            return {
                "turn": turn_num,
                "game_over": True,
                "winner": winner,
                "victory_type": v_type
            }

        # Extract full world map topology for replay and centered map for terminal
        full_map_res = self.engine.get_map(0, 0, -1)
        map_res = self.engine.get_map(0, 0, 6)
        advisor_report = self.advisor.analyze(state, full_map_res if full_map_res.get("tiles") else map_res)

        print(f"\n{'='*60}")
        print(f" TURN {turn_num} | Civilization: {civ_name} | Score: {state.get('stats', {}).get('score', 0)}")
        print(f"{'='*60}")
        print(f"Stats: Gold={state.get('stats', {}).get('gold')} ({state.get('stats', {}).get('gold_per_turn'):+} gpt) | "
              f"Science=+{state.get('stats', {}).get('science_per_turn')} | Happiness={state.get('stats', {}).get('happiness')}")
        print(f"Active Research: {state.get('technology', {}).get('current_tech')} ({state.get('technology', {}).get('turns_to_finish', 0)} turns)")
        print(f"Directive: {self.advisor.user_directive or 'Balanced Strategy'}")
        print(f"Advisor Focus: {advisor_report.get('recommended_focus')} | Threat: {advisor_report.get('military_assessment', {}).get('threat_level')}")

        if map_res.get("ascii_view"):
            print("\n" + map_res["ascii_view"])

        if advisor_report.get("bottlenecks_and_alerts"):
            print("\n[ALERTS]:")
            for alert in advisor_report["bottlenecks_and_alerts"]:
                print(f" - {alert}")

        # Build prompt for LLM
        system_prompt = (
            "You are an expert grand-strategy AI playing Civilization V (Unciv).\n"
            "Your objective is to win the game while strictly adhering to the player's strategic directive.\n"
            "Analyze the state, formulate multi-turn grand strategy, and output actionable commands for this turn.\n"
            "Respond ONLY with a valid JSON object in the following format:\n"
            "{\n"
            "  \"reasoning\": \"1-2 sentence high level summary of this turn's actions\",\n"
            "  \"strategic_analysis\": \"Detailed strategic breakdown: multi-turn roadmap, tech goals, expansion targets, threat mitigations, and alignment with the directive\",\n"
            "  \"tactical_intent\": \"Tactical explanation of specific unit movements, scouting angles, and city construction choices\",\n"
            "  \"choose_tech\": \"TechName\" or null,\n"
            "  \"adopt_policy\": \"PolicyName\" or null,\n"
            "  \"city_actions\": [\n"
            "    {\"city_name\": \"CityName\", \"action\": \"set_production\"|\"set_focus\", \"param\": \"ItemName\"}\n"
            "  ],\n"
            "  \"unit_actions\": [\n"
            "    {\"unit_id\": 123, \"action\": \"move\"|\"attack\"|\"found_city\"|\"improve_tile\"|\"fortify\"|\"sleep\", \"target_x\": 0, \"target_y\": 0, \"param\": \"\"}\n"
            "  ],\n"
            "  \"diplomacy\": [\n"
            "    {\"target_civ\": \"CivName\", \"action\": \"declare_war\"|\"make_peace\"}\n"
            "  ]\n"
            "}"
        )

        # Annotate choices with compact live ruleset data (Civilopedia)
        tech_data = state.get("technology", {})
        res_techs = tech_data.get("researchable_techs", [])
        annotated_techs = [
            self.civilopedia.annotate_item("tech", t.get("name") if isinstance(t, dict) else t)
            for t in res_techs[:6]
        ]
        
        pol_data = state.get("policies", {})
        adoptable_pols = pol_data.get("adoptable_policies", [])
        annotated_policies = [
            self.civilopedia.annotate_item("policy", p)
            for p in adoptable_pols[:6]
        ]

        annotated_cities = []
        for c in state.get("cities", []):
            b_units = [self.civilopedia.annotate_item("unit", u) for u in c.get("buildable_units", [])[:6]]
            b_buildings = [self.civilopedia.annotate_item("building", b) for b in c.get("buildable_buildings", [])[:6]]
            annotated_cities.append({
                "name": c["name"],
                "pop": c["population"],
                "cur_construction": c.get("current_construction"),
                "buildable_units": b_units,
                "buildable_buildings": b_buildings
            })

        user_content = {
            "current_turn": turn_num,
            "civilization": civ_name,
            "civilization_dossier": self.scratchpad.get("civilization_dossier", {}),
            "strategic_directive": self.advisor.user_directive,
            "stats": state.get("stats"),
            "technology": {
                "current_tech": tech_data.get("current_tech"),
                "turns_to_finish": tech_data.get("turns_to_finish"),
                "researchable_techs_with_unlocks": annotated_techs
            },
            "policies": {
                "adopted_policies": pol_data.get("adopted_policies", []),
                "adoptable_policies_with_effects": annotated_policies
            },
            "cities": annotated_cities,
            "units": [
                {
                    "id": u["id"],
                    "name": u["name"],
                    "location": u["location"],
                    "movement": u["movement"],
                    "is_military": u.get("is_military", False),
                    "is_idle": u.get("is_idle", False),
                    "health": u.get("health", 100)
                }
                for u in state.get("units", [])
            ],
            "known_civilizations": state.get("known_civilizations"),
            "advisor_recommendations": advisor_report.get("suggested_actions"),
            "expansion_candidate_spots": advisor_report.get("expansion_analysis", {}).get("recommended_next_settle_spots"),
            "military_assessment": advisor_report.get("military_assessment")
        }

        plan = None
        raw_response = None
        llm_error_str = None
        is_llm_used = False

        if self.llm:
            print(f"\nConsulting Strategic LLM ({self.llm.model})...")
            try:
                raw_response = self.llm.chat_completion([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_content, indent=2)}
                ])
                plan = self._extract_json(raw_response)
                if plan:
                    is_llm_used = True
                else:
                    llm_error_str = "Could not parse JSON from LLM response."
            except Exception as e:
                llm_error_str = str(e)
                print(f"LLM consultation error: {e}")
                print("Falling back to Strategic Advisor heuristic decisions.")

        if not plan:
            # Fallback heuristic plan from strategic advisor
            plan = self._build_heuristic_plan(state, advisor_report)

        print("\n=== Strategic Decision Plan ===")
        engine_label = f"🤖 LLM ({self.llm.model})" if is_llm_used else "⚡ Strategic Heuristics"
        print(f"Engine: {engine_label}")
        print(f"Reasoning: {plan.get('reasoning', 'Executing tactical and economic development.')}")
        if plan.get("strategic_analysis"):
            print(f"Strategic Analysis: {plan['strategic_analysis']}")
        if plan.get("tactical_intent"):
            print(f"Tactical Intent: {plan['tactical_intent']}")

        if interactive:
            print("\nAction Proposals:")
            if plan.get("choose_tech"):
                print(f" - Research Tech: {plan['choose_tech']}")
            for ca in plan.get("city_actions", []):
                print(f" - City [{ca.get('city_name')}]: {ca.get('action')} -> {ca.get('param')}")
            for ua in plan.get("unit_actions", []):
                print(f" - Unit (ID {ua.get('unit_id')}): {ua.get('action')} target=({ua.get('target_x')},{ua.get('target_y')}) {ua.get('param')}")

            choice = input("\n[Enter] to execute, [s] to skip actions and end turn, or type custom command: ").strip()
            if choice.lower() == 's':
                print("Skipping actions...")
                end_res = self.engine.end_turn()
                return {"turn": turn_num, "status": "skipped", "end_turn": end_res}

        # Execute actions
        execution_log = self._execute_plan(plan)
        for log_entry in execution_log:
            print(f" > {log_entry}")

        # End turn
        print("Advancing turn (simulating AI opponents and barbarians)...", flush=True)
        t_turn_start = time.time()
        end_res = self.engine.end_turn()
        t_turn_elapsed = time.time() - t_turn_start
        print(f"      Turn advanced in {t_turn_elapsed:.1f}s", flush=True)
        notifs = end_res.get("notifications", [])
        if notifs:
            print("[Turn Notifications]:")
            for n in notifs:
                print(f" * {n}")

        # Snapshot for replay
        snapshot = {
            "turn": turn_num,
            "civ_name": civ_name,
            "decision_mode": "LLM" if is_llm_used else "Heuristic",
            "llm_model": self.llm.model if (self.llm and is_llm_used) else None,
            "llm_error": llm_error_str,
            "stats": state.get("stats", {}),
            "tech": state.get("technology", {}),
            "policies": state.get("policies", {}),
            "cities": state.get("cities", []),
            "units": state.get("units", []),
            "map": full_map_res if (isinstance(full_map_res, dict) and full_map_res.get("tiles")) else map_res,
            "advisor": {
                "recommended_focus": advisor_report.get("recommended_focus"),
                "threat_level": advisor_report.get("threat_level"),
                "alerts": advisor_report.get("alerts", [])
            },
            "plan": plan,
            "raw_llm_response": raw_response if is_llm_used else None,
            "execution": execution_log,
            "notifications": notifs
        }
        # Upsert snapshot and sort history
        existing_idx = next((i for i, s in enumerate(self.history) if s.get("turn") == turn_num), None)
        if existing_idx is not None:
            self.history[existing_idx] = snapshot
        else:
            self.history.append(snapshot)
        self.history.sort(key=lambda s: s.get("turn", 0))

        if self.record_file:
            try:
                data_to_write = {
                    "civ": civ_name,
                    "directive": self.advisor.user_directive or "Balanced Strategy",
                    "total_turns": len(self.history),
                    "recorded_at": datetime.datetime.now().isoformat(),
                    "turns": self.history
                }
                with open(self.record_file, "w", encoding="utf-8") as rf:
                    json.dump(data_to_write, rf, indent=2)

                # Mirror to replays/latest.json and replay_history.json
                latest_path = os.path.join("replays", "latest.json")
                if os.path.abspath(self.record_file) != os.path.abspath(latest_path):
                    with open(latest_path, "w", encoding="utf-8") as lf:
                        json.dump(data_to_write, lf, indent=2)
                with open("replay_history.json", "w", encoding="utf-8") as rh:
                    json.dump(data_to_write, rh, indent=2)
            except Exception:
                pass

        return {
            "turn": turn_num,
            "plan": plan,
            "execution": execution_log,
            "notifications": notifs
        }

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    pass
        return None

    def _build_heuristic_plan(self, state: Dict[str, Any], advisor_report: Dict[str, Any]) -> Dict[str, Any]:
        plan: Dict[str, Any] = {
            "reasoning": f"Advisor heuristic execution focusing on {advisor_report.get('recommended_focus')}.",
            "choose_tech": None,
            "adopt_policy": None,
            "city_actions": [],
            "unit_actions": [],
            "diplomacy": []
        }

        # Tech
        tech = state.get("technology", {})
        if not tech.get("current_tech") or tech.get("current_tech") == "None":
            rec_techs = advisor_report.get("technology_roadmap", {}).get("recommended_next_techs", [])
            if rec_techs:
                plan["choose_tech"] = rec_techs[0]["name"]

        # Cities
        for ca in advisor_report.get("city_management_advice", []):
            if "IDLE" in ca.get("current_construction", ""):
                recs = ca.get("recommended_constructions", ["Scout"])
                raw_rec = recs[0] if recs else "Scout"
                item = raw_rec.split(" (")[0].replace("Construct ", "").replace("Produce ", "").strip()
                plan["city_actions"].append({
                    "city_name": ca["name"],
                    "action": "set_production",
                    "param": item
                })

        # Units
        for u in state.get("units", []):
            u_id = u["id"]
            u_name = u["name"]
            mov = u.get("movement", 0)
            if mov <= 0:
                continue

            if u_name == "Settler":
                loc = u.get("location", [0, 0])
                cities = state.get("cities", [])
                on_city = any(c.get("location") == loc for c in cities)
                if not cities:
                    plan["unit_actions"].append({
                        "unit_id": u_id,
                        "action": "found_city"
                    })
                elif on_city:
                    plan["unit_actions"].append({
                        "unit_id": u_id,
                        "action": "move",
                        "target_x": loc[0] + 2,
                        "target_y": loc[1] + 1
                    })
                else:
                    plan["unit_actions"].append({
                        "unit_id": u_id,
                        "action": "found_city"
                    })
            elif u.get("is_military") and u.get("is_idle"):
                # Move military towards exploration or priority target
                loc = u.get("location", [0, 0])
                plan["unit_actions"].append({
                    "unit_id": u_id,
                    "action": "move",
                    "target_x": loc[0] + 1,
                    "target_y": loc[1]
                })
            elif u_name == "Worker" and u.get("is_idle"):
                plan["unit_actions"].append({
                    "unit_id": u_id,
                    "action": "automate"
                })

        return plan

    def _execute_plan(self, plan: Dict[str, Any]) -> List[str]:
        log = []

        # Tech
        if plan.get("choose_tech"):
            tech_name = plan["choose_tech"]
            try:
                res = self.engine.choose_tech(tech_name)
                log.append(f"Researched: {tech_name} ({res.get('message', 'OK')})")
            except Exception as e:
                log.append(f"Failed to research {tech_name}: {e}")

        # Policy
        if plan.get("adopt_policy"):
            pol_name = plan["adopt_policy"]
            try:
                res = self.engine.adopt_policy(pol_name)
                log.append(f"Adopted Policy: {pol_name} ({res.get('message', 'OK')})")
            except Exception as e:
                log.append(f"Failed policy {pol_name}: {e}")

        # Cities
        for ca in plan.get("city_actions", []):
            try:
                res = self.engine.city_action(
                    city_name=ca["city_name"],
                    action=ca["action"],
                    param=ca.get("param", ""),
                    target_x=ca.get("target_x", 0),
                    target_y=ca.get("target_y", 0)
                )
                log.append(f"City [{ca['city_name']}]: {res.get('message', 'OK')}")
            except Exception as e:
                log.append(f"City action failed [{ca.get('city_name')}]: {e}")

        # Units
        for ua in plan.get("unit_actions", []):
            try:
                res = self.engine.unit_action(
                    unit_id=ua["unit_id"],
                    action=ua["action"],
                    target_x=ua.get("target_x", 0),
                    target_y=ua.get("target_y", 0),
                    param=ua.get("param", "")
                )
                log.append(f"Unit (ID {ua['unit_id']}): {res.get('message', 'OK')}")
            except Exception as e:
                log.append(f"Unit action failed (ID {ua.get('unit_id')}): {e}")

        # Diplomacy
        for d in plan.get("diplomacy", []):
            try:
                res = self.engine.diplomacy_action(
                    target_civ=d["target_civ"],
                    action=d["action"]
                )
                log.append(f"Diplomacy [{d['target_civ']}]: {res.get('message', 'OK')}")
            except Exception as e:
                log.append(f"Diplomacy failed [{d.get('target_civ')}]: {e}")

        return log

def load_env_file():
    """Loads key-value pairs from .env into os.environ if present."""
    if not os.path.exists(".env"):
        return
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Unciv LLM Strategic Agent")
    parser.add_argument("--strategy", type=str, default="", help="Strategic directive (e.g. 'Focus on science and be aggressive against European nations')")
    parser.add_argument("--civ", type=str, default="Rome", help="Civilization to play (e.g. Rome, Greece, America)")
    parser.add_argument("--ruleset", type=str, default="Civ V - Gods & Kings", help="Ruleset: 'Civ V - Gods & Kings' (default), 'Civ V - Vanilla', or custom mod name")
    parser.add_argument("--difficulty", type=str, default="Prince", help="Difficulty: Settler, Chieftain, Warlord, Prince, King, Emperor, Immortal, Deity")
    parser.add_argument("--map-size", type=str, default="Tiny", help="Map size: Tiny, Small, Medium, Large, Huge")
    parser.add_argument("--map-type", type=str, default="Pangaea", help="Map type: Pangaea, Continents, Archipelago, Inner Sea, Lakes, Four Corners, Fractal, etc.")
    parser.add_argument("--speed", type=str, default="Standard", help="Game speed: Quick, Standard, Epic, Marathon")
    parser.add_argument("--opponents", type=int, default=3, help="Number of AI opponents (default: 3)")
    parser.add_argument("--city-states", type=int, default=-1, help="Number of city-states (-1 = default for map size)")
    parser.add_argument("--barbarians", type=str, default="Normal", help="Barbarians: Normal, None, Raging")
    parser.add_argument("--turns", type=int, default=0, help="Number of turns to play (default: 0 = play until game ends or Ctrl+C)")
    parser.add_argument("--load", type=str, default="", help="Path to save file to load (e.g. autosave.json)")
    parser.add_argument("--record", type=str, default="", help="Path to record turn-by-turn replay history (default: auto-generated timestamp in replays/)")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive co-pilot mode")
    parser.add_argument("--api-base", type=str, default="", help="LLM API base URL (e.g. https://openrouter.ai/api/v1 or http://localhost:8080/v1)")
    parser.add_argument("--api-key", type=str, default="", help="API key for LLM provider (or set OPENROUTER_API_KEY in .env)")
    parser.add_argument("--model", type=str, default="", help="Model name (e.g. meta-llama/llama-3.3-70b-instruct:free or local model)")

    args = parser.parse_args()

    os.makedirs("replays", exist_ok=True)
    if args.record:
        record_path = args.record
    else:
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "resumed" if args.load else "match"
        record_path = os.path.join("replays", f"replay_{args.civ}_{prefix}_{timestamp_str}.json")

    # Determine LLM configuration from CLI or .env
    api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    api_base = args.api_base or os.environ.get("LLM_API_BASE")
    if not api_base and api_key and ("sk-or-" in api_key or os.environ.get("OPENROUTER_API_KEY")):
        api_base = "https://openrouter.ai/api/v1"

    model = args.model or os.environ.get("OPENROUTER_MODEL") or os.environ.get("LLM_MODEL")
    if not model and api_base and "openrouter" in api_base:
        model = "meta-llama/llama-3.3-70b-instruct:free"

    llm_client = None
    if api_base:
        llm_client = LLMClient(api_base=api_base, api_key=api_key, model=model)

    print("[1/3] Initializing Unciv engine daemon...", flush=True)
    t0 = time.time()
    engine = UncivEngine()
    print(f"      Daemon initialized in {time.time()-t0:.1f}s", flush=True)

    # Normalize ruleset name
    ruleset_name = args.ruleset
    if ruleset_name.lower() in ("gods and kings", "gods & kings", "gnk", "g&k"):
        ruleset_name = "Civ V - Gods & Kings"
    elif ruleset_name.lower() in ("vanilla", "civ v - vanilla"):
        ruleset_name = "Civ V - Vanilla"

    if args.load and os.path.exists(args.load):
        print(f"[2/3] Loading saved game from {args.load}...", flush=True)
        with open(args.load, "r", encoding="utf-8") as f:
            save_content = f.read()
        res = engine.load_game(save_content)
        print(f"      Game loaded successfully!", flush=True)
    else:
        print(f"[2/3] Generating new game map ({args.civ}, Ruleset: {ruleset_name}, Difficulty: {args.difficulty}, Map: {args.map_type} {args.map_size}, Speed: {args.speed}, Opponents: {args.opponents})...", flush=True)
        t0 = time.time()
        res = engine.new_game(
            nation=args.civ,
            difficulty=args.difficulty,
            ruleset=ruleset_name,
            map_size=args.map_size,
            map_type=args.map_type,
            speed=args.speed,
            opponents=args.opponents,
            city_states=args.city_states,
            barbarians=args.barbarians
        )
        print(f"      Map generated in {time.time()-t0:.1f}s", flush=True)

    print(f"[3/3] Match ready! Playing as: {res.get('active_civ', args.civ)} (Turn {res.get('turn', 0)})", flush=True)
    if llm_client:
        print(f"      🤖 LLM Strategic AI: {llm_client.model} ({llm_client.api_base})\n", flush=True)
    else:
        print(f"      ⚡ Advisor Engine: Built-in Strategic Heuristics\n", flush=True)

    agent = UncivAgent(
        engine=engine,
        llm_client=llm_client,
        strategy_directive=args.strategy,
        record_file=record_path,
        resume_history=bool(args.load)
    )

    turn_count = 0
    max_turns = args.turns if args.turns > 0 else float("inf")
    if args.turns <= 0:
        print("Starting continuous game session (press Ctrl+C anytime to pause/stop)...\n", flush=True)

    try:
        while turn_count < max_turns:
            try:
                turn_res = agent.play_turn(interactive=args.interactive)
                if turn_res and turn_res.get("game_over"):
                    break
                turn_count += 1
                # Autosave game state after every turn
                try:
                    save_str = engine.save_game()
                    if save_str:
                        with open("autosave.json", "w", encoding="utf-8") as sf:
                            sf.write(save_str)
                except Exception:
                    pass
                time.sleep(0.3)
            except UncivEngineError as e:
                print(f"\n⚠️ Engine communication warning on turn {turn_count}: {e}", flush=True)
                if os.path.exists("autosave.json"):
                    print("🔄 Automatically restarting engine daemon and resuming from autosave.json...", flush=True)
                    try:
                        engine.close()
                        time.sleep(1.0)
                        engine = UncivEngine()
                        with open("autosave.json", "r", encoding="utf-8") as sf:
                            saved = sf.read()
                        engine.load_game(saved)
                        agent.engine = engine
                        print("✅ Game state restored! Continuing match...\n", flush=True)
                        continue
                    except Exception as rec_err:
                        print(f"❌ Failed to auto-recover: {rec_err}", flush=True)
                        raise e
                else:
                    raise e
    except KeyboardInterrupt:
        print(f"\nGame paused by user after {turn_count} turns (saved to autosave.json and {record_path}).", flush=True)
    finally:
        print(f"\nGame session completed! Replay data saved to '{record_path}'.", flush=True)
        engine.close()

if __name__ == "__main__":
    main()
