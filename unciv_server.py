"""
Unciv Local Multi-AI & Human vs. AI Server
A zero-friction local multiplayer server that lets humans play against Strategic AI agents
inside the official Unciv Desktop GUI without copying or pasting anything.
Also enables multi-AI battles (e.g. Llama 3.3 vs. llama.cpp vs. Ollama vs. Heuristics).
"""

import os
import sys
import json
import time
import argparse
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

from unciv_engine import UncivEngine, UncivEngineError
from unciv_agent import UncivAgent, LLMClient

# In-memory and on-disk game storage
GAMES_DB: Dict[str, str] = {}
GAMES_LOCK = threading.Lock()
AI_CONFIGS: Dict[str, Dict[str, Any]] = {}
ENGINE_LOCK = threading.Lock()

class UncivMultiplayerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean custom logging
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("/isalive", ""):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"authVersion": 0}')
            return

        if path.startswith("/files/"):
            game_id = path.split("/files/", 1)[1]
            with GAMES_LOCK:
                game_data = GAMES_DB.get(game_id)
                if not game_data and os.path.exists(os.path.join("multiplayer_saves", f"{game_id}.json")):
                    try:
                        with open(os.path.join("multiplayer_saves", f"{game_id}.json"), "r", encoding="utf-8") as f:
                            game_data = f.read()
                            GAMES_DB[game_id] = game_data
                    except Exception:
                        pass

            if game_data:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(game_data.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()
            return

        if path == "/auth":
            self.send_response(200)
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/files/"):
            game_id = path.split("/files/", 1)[1]
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            with GAMES_LOCK:
                GAMES_DB[game_id] = body
                os.makedirs("multiplayer_saves", exist_ok=True)
                with open(os.path.join("multiplayer_saves", f"{game_id}.json"), "w", encoding="utf-8") as f:
                    f.write(body)

            self.send_response(200)
            self.end_headers()

            # Trigger asynchronous AI Turn Processor
            threading.Thread(target=process_turns_until_human, args=(game_id,), daemon=True).start()
            return

        if path == "/auth":
            self.send_response(200)
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.startswith("/files/"):
            game_id = path.split("/files/", 1)[1]
            with GAMES_LOCK:
                GAMES_DB.pop(game_id, None)
                save_p = os.path.join("multiplayer_saves", f"{game_id}.json")
                if os.path.exists(save_p):
                    try:
                        os.remove(save_p)
                    except Exception:
                        pass
            self.send_response(200)
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

def process_turns_until_human(game_id: str, max_ai_streak: int = 20):
    """
    Checks if the active turn belongs to an AI civilization.
    If so, executes the AI turn, saves the state, and repeats until it is a Human player's turn.
    """
    with ENGINE_LOCK:
        time.sleep(0.1)
        with GAMES_LOCK:
            current_save = GAMES_DB.get(game_id)
        if not current_save:
            return

        engine = UncivEngine()
        try:
            res = engine.load_game(current_save)
            active_civ = res.get("active_civ", "")
            turn_num = res.get("turn", 0)

            streak = 0
            while streak < max_ai_streak:
                state = engine.get_state()
                active_civ = state.get("active_civ", "")
                turn_num = state.get("turn", 0)

                # Determine if this civ is controlled by Human or AI
                # In Unciv, human players have playerType == Human
                # If civ is configured in AI_CONFIGS or isn't the primary human, AI plays it!
                is_ai_civ = False
                ai_conf = AI_CONFIGS.get(active_civ)

                if ai_conf:
                    is_ai_civ = True
                elif active_civ and active_civ not in AI_CONFIGS.get("__HUMAN_CIVS__", []):
                    # Default: if civilization is not human, AI takes turn
                    is_ai_civ = True

                if not is_ai_civ:
                    print(f"🎯 Turn {turn_num} passed to Human player ({active_civ})! Ready in Unciv GUI.", flush=True)
                    break

                print(f"🤖 [Turn {turn_num}] AI Turn for '{active_civ}' is playing...", flush=True)
                strategy = (ai_conf and ai_conf.get("strategy")) or "Balanced Strategy"
                llm = (ai_conf and ai_conf.get("llm_client")) or get_default_llm_client()

                agent = UncivAgent(engine=engine, llm_client=llm, strategy_directive=strategy)
                agent.play_turn(interactive=False)

                streak += 1
                updated_save = engine.save_game()

                with GAMES_LOCK:
                    GAMES_DB[game_id] = updated_save
                    os.makedirs("multiplayer_saves", exist_ok=True)
                    with open(os.path.join("multiplayer_saves", f"{game_id}.json"), "w", encoding="utf-8") as f:
                        f.write(updated_save)

                # Check state after turn
                after_state = engine.get_state()
                next_civ = after_state.get("active_civ", "")
                if next_civ in AI_CONFIGS.get("__HUMAN_CIVS__", []):
                    print(f"🎯 Turn {after_state.get('turn')} passed to Human player ({next_civ})! Ready in Unciv GUI.", flush=True)
                    break

        except Exception as e:
            print(f"⚠️ Error processing AI turn for match {game_id}: {e}", flush=True)
        finally:
            engine.close()

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

def get_default_llm_client() -> Optional[LLMClient]:
    """Creates a default LLMClient from .env variables if configured."""
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    api_base = os.environ.get("LLM_API_BASE")
    if not api_base and api_key and ("sk-or-" in api_key or os.environ.get("OPENROUTER_API_KEY")):
        api_base = "https://openrouter.ai/api/v1"

    model = os.environ.get("OPENROUTER_MODEL") or os.environ.get("LLM_MODEL")
    if not model and api_base and "openrouter" in api_base:
        model = "meta-llama/llama-3.3-70b-instruct:free"

    if api_base:
        return LLMClient(api_base=api_base, api_key=api_key, model=model)
    return None

def main():
    load_env_file()

    parser = argparse.ArgumentParser(description="Unciv Local Multi-AI & Human vs. AI Server")
    parser.add_argument("--port", type=int, default=8088, help="Server port (default: 8088)")
    parser.add_argument("--human", type=str, default="Greece", help="Human civilization name(s) separated by comma (default: Greece)")
    parser.add_argument("--ai", action="append", help="Configure AI player: 'CivName:strategy' or 'CivName:strategy:api_base:model:api_key'")

    args = parser.parse_args()

    human_civs = [c.strip() for c in args.human.split(",") if c.strip()]
    AI_CONFIGS["__HUMAN_CIVS__"] = human_civs

    default_llm = get_default_llm_client()

    if args.ai:
        for entry in args.ai:
            parts = entry.split(":")
            civ_name = parts[0].strip()
            strat = parts[1].strip() if len(parts) > 1 else "Balanced Strategy"
            llm_c = None
            if len(parts) >= 4:
                api_base = parts[2].strip()
                model = parts[3].strip()
                api_key = parts[4].strip() if len(parts) > 4 else ""
                llm_c = LLMClient(api_base=api_base, api_key=api_key, model=model)
            
            AI_CONFIGS[civ_name] = {
                "strategy": strat,
                "llm_client": llm_c
            }

    server_url = f"http://127.0.0.1:{args.port}"
    print("=" * 65)
    print("       🏛️  UNCIV LOCAL MULTI-AI & ZERO-FRICTION SERVER  🏛️")
    print("=" * 65)
    print(f" Server running at: {server_url}")
    print(f" Human Civilization(s): {', '.join(human_civs)}")
    if args.ai:
        print(" Configured AI Agents:")
        for civ, cfg in AI_CONFIGS.items():
            if not civ.startswith("__"):
                llm_info = f" (LLM: {cfg['llm_client'].model})" if cfg.get("llm_client") else " (Heuristic)"
                print(f"  • {civ}: \"{cfg['strategy']}\"{llm_info}")
    else:
        print(" All other civilizations will be played automatically by Strategic AI!")
    print("\nHow to Play in Unciv Desktop GUI:")
    print(f" 1. Open Unciv -> Settings -> Multiplayer -> Server: set to '{server_url}'")
    print(" 2. Click Multiplayer -> New Online Game")
    print(" 3. Choose your Civilization (Human) and add your AI opponents!")
    print(" 4. Play your turn and click 'Next Turn'. The AI will play instantly!")
    print("=" * 65 + "\n")

    httpd = HTTPServer(("127.0.0.1", args.port), UncivMultiplayerHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
