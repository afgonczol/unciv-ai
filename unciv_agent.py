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
import threading
import argparse
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

from unciv_engine import UncivEngine
from strategic_advisor import StrategicAdvisor

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
                 strategy_directive: str = ""):
        self.engine = engine or UncivEngine()
        self.advisor = StrategicAdvisor()
        self.llm = llm_client
        self.scratchpad: Dict[str, Any] = {
            "grand_strategy": "",
            "active_military_campaign": "",
            "settlement_plan": "",
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
        map_res = self.engine.get_map(0, 0, 6)
        advisor_report = self.advisor.analyze(state, map_res)

        turn_num = state.get("turn", 0)
        civ_name = state.get("active_civ", "Unknown")

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
            "Respond ONLY with a JSON object specifying your strategic reasoning and actionable decisions for this turn.\n"
            "JSON Format:\n"
            "{\n"
            "  \"reasoning\": \"Brief strategic summary of current turn priorities\",\n"
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

        user_content = {
            "current_turn": turn_num,
            "civilization": civ_name,
            "strategic_directive": self.advisor.user_directive,
            "stats": state.get("stats"),
            "technology": state.get("technology"),
            "policies": state.get("policies"),
            "cities": [
                {
                    "name": c["name"],
                    "pop": c["population"],
                    "cur_construction": c.get("current_construction"),
                    "buildable_units": c.get("buildable_units", [])[:5],
                    "buildable_buildings": c.get("buildable_buildings", [])[:5]
                }
                for c in state.get("cities", [])
            ],
            "units": [
                {
                    "id": u["id"],
                    "name": u["name"],
                    "location": u["location"],
                    "movement": u["movement"],
                    "is_military": u.get("is_military"),
                    "is_idle": u.get("is_idle"),
                    "available_actions": u.get("available_actions", [])
                }
                for u in state.get("units", [])
            ],
            "known_civilizations": state.get("known_civilizations"),
            "advisor_recommendations": advisor_report.get("suggested_actions"),
            "expansion_candidate_spots": advisor_report.get("expansion_analysis", {}).get("recommended_next_settle_spots"),
            "military_assessment": advisor_report.get("military_assessment")
        }

        plan = None
        if self.llm:
            print("\nConsulting Strategic LLM...")
            try:
                raw_response = self.llm.chat_completion([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_content, indent=2)}
                ])
                plan = self._extract_json(raw_response)
            except Exception as e:
                print(f"LLM consultation error: {e}")
                print("Falling back to Strategic Advisor heuristic decisions.")

        if not plan:
            # Fallback heuristic plan from strategic advisor
            plan = self._build_heuristic_plan(state, advisor_report)

        print("\n=== Strategic Decision Plan ===")
        print(f"Reasoning: {plan.get('reasoning', 'Executing tactical and economic development.')}")

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
        print("Advancing turn...", flush=True)
        end_res = self.engine.end_turn()
        notifs = end_res.get("notifications", [])
        if notifs:
            print("[Turn Notifications]:")
            for n in notifs:
                print(f" * {n}")

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

def main():
    parser = argparse.ArgumentParser(description="Unciv LLM Strategic Agent")
    parser.add_argument("--strategy", type=str, default="", help="Strategic directive (e.g. 'Focus on science and be aggressive against European nations')")
    parser.add_argument("--civ", type=str, default="Rome", help="Civilization to play (e.g. Rome, Greece, America)")
    parser.add_argument("--difficulty", type=str, default="Prince", help="Difficulty level")
    parser.add_argument("--map-size", type=str, default="Tiny", help="Map size: Tiny, Small, Medium, Large, Huge")
    parser.add_argument("--turns", type=int, default=0, help="Number of turns to play (default: 0 = play until game ends or Ctrl+C)")
    parser.add_argument("--load", type=str, default="", help="Path to save file to load (e.g. autosave.json)")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive co-pilot mode")
    parser.add_argument("--api-base", type=str, default="", help="LLM API base URL (e.g. https://openrouter.ai/api/v1 or http://localhost:8080/v1)")
    parser.add_argument("--api-key", type=str, default="", help="API key for LLM provider")
    parser.add_argument("--model", type=str, default="", help="Model name (e.g. meta-llama/llama-3.3-70b-instruct or local model)")

    args = parser.parse_args()

    print("[1/3] Initializing Unciv engine daemon...", flush=True)
    t0 = time.time()
    engine = UncivEngine()
    print(f"      Daemon initialized in {time.time()-t0:.1f}s", flush=True)

    if args.load and os.path.exists(args.load):
        print(f"[2/3] Loading saved game from {args.load}...", flush=True)
        with open(args.load, "r", encoding="utf-8") as f:
            save_content = f.read()
        res = engine.load_game(save_content)
        print(f"      Game loaded successfully!", flush=True)
    else:
        print(f"[2/3] Generating new game map ({args.civ}, Difficulty: {args.difficulty}, MapSize: {args.map_size})...", flush=True)
        t0 = time.time()
        res = engine.new_game(nation=args.civ, difficulty=args.difficulty, map_size=args.map_size)
        print(f"      Map generated in {time.time()-t0:.1f}s", flush=True)

    print(f"[3/3] Match ready! Playing as: {res.get('active_civ', args.civ)} (Turn {res.get('turn', 0)})\n", flush=True)

    llm_client = None
    if args.api_base:
        llm_client = LLMClient(api_base=args.api_base, api_key=args.api_key, model=args.model)

    agent = UncivAgent(engine=engine, llm_client=llm_client, strategy_directive=args.strategy)

    turn_count = 0
    max_turns = args.turns if args.turns > 0 else float("inf")
    if args.turns <= 0:
        print("Starting continuous game session (press Ctrl+C anytime to pause/stop)...\n", flush=True)

    try:
        while turn_count < max_turns:
            agent.play_turn(interactive=args.interactive)
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
    except KeyboardInterrupt:
        print(f"\nGame paused by user after {turn_count} turns (saved to autosave.json).", flush=True)
    finally:
        print("\nGame session completed!", flush=True)
        engine.close()

if __name__ == "__main__":
    main()
