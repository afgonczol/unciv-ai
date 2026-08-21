"""
Play Against Unciv AI (Human vs. Strategic AI Mode)
Allows a human player to play against the Strategic AI Agent in the official Unciv game client.
Supports clipboard copy/paste, file synchronization, and auto-turn play.
"""

import os
import sys
import json
import time
import subprocess
import argparse
from typing import Optional

from unciv_engine import UncivEngine, UncivEngineError
from unciv_agent import UncivAgent

def get_clipboard() -> str:
    """Gets text from OS clipboard across Linux, Windows, and macOS."""
    # 1. Try tkinter (cross-platform standard library)
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        if text and len(text.strip()) > 10:
            return text.strip()
    except Exception:
        pass

    # 2. Try Linux xclip / wl-paste
    if sys.platform.startswith("linux"):
        for cmd in [["xclip", "-selection", "clipboard", "-o"], ["wl-paste"], ["xsel", "--clipboard", "--output"]]:
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            except Exception:
                continue

    # 3. Try Windows PowerShell
    if sys.platform.startswith("win"):
        try:
            res = subprocess.run(["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    return ""

def set_clipboard(text: str) -> bool:
    """Sets text to OS clipboard across Linux, Windows, and macOS."""
    # 1. Try tkinter
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception:
        pass

    # 2. Try Linux xclip / wl-copy
    if sys.platform.startswith("linux"):
        for cmd in [["xclip", "-selection", "clipboard"], ["wl-copy"], ["xsel", "--clipboard", "--input"]]:
            try:
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
                p.communicate(input=text, timeout=2)
                if p.returncode == 0:
                    return True
            except Exception:
                continue

    # 3. Try Windows clip.exe
    if sys.platform.startswith("win"):
        try:
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text, timeout=2)
            if p.returncode == 0:
                return True
        except Exception:
            pass

    return False

def play_one_ai_turn(save_str: str, strategy: str = "Balanced Strategy", ai_civ: str = "") -> Optional[str]:
    """
    Loads save string, executes one AI turn, and returns the updated save string for the human.
    """
    engine = UncivEngine()
    try:
        print("[1/3] Loading match state...", flush=True)
        res = engine.load_game(save_str)
        active_civ = res.get("active_civ", "Unknown")
        turn_num = res.get("turn", 0)
        print(f"      Active Civilization: {active_civ} (Turn {turn_num})", flush=True)

        if ai_civ and active_civ != ai_civ:
            print(f"⚠️ Warning: Current turn belongs to '{active_civ}', but expected AI '{ai_civ}'.")

        print(f"[2/3] AI Agent '{active_civ}' is planning and executing moves...", flush=True)
        agent = UncivAgent(engine=engine, strategy_directive=strategy)
        turn_res = agent.play_turn(interactive=False)

        print("[3/3] Saving match state for Human player...", flush=True)
        new_save = engine.save_game()
        state_after = engine.get_state()
        next_civ = state_after.get("active_civ", "Unknown")
        print(f"✅ AI turn completed! Turn passed to: {next_civ}\n", flush=True)
        return new_save
    finally:
        engine.close()

def main():
    parser = argparse.ArgumentParser(description="Play Against Unciv Strategic AI")
    parser.add_argument("--save", type=str, default="vs_player_save.json", help="Save file to read/write")
    parser.add_argument("--strategy", type=str, default="Balanced Strategy", help="Strategic directive for the AI agent")
    parser.add_argument("--civ", type=str, default="", help="Expected AI civilization name (e.g. Rome)")
    parser.add_argument("--auto-watch", action="store_true", help="Continuously watch clipboard/save file for turns")

    args = parser.parse_args()

    print("=" * 60)
    print("        ⚔️  HUMAN vs. STRATEGIC AI MATCH MODE  ⚔️")
    print("=" * 60)
    print("Instructions:")
    print(" 1. In Unciv: Start a Custom Game with 2+ Human players (You & AI)")
    print(" 2. Play your turn as your Civ, click 'Next Turn'")
    print(" 3. Copy save to clipboard (or save to 'vs_player_save.json')")
    print(" 4. Run this script -> The AI will play its turn and copy the save back!")
    print(" 5. In Unciv: Click 'Load game from clipboard' to play your next turn!")
    print("=" * 60 + "\n")

    # Read save string
    save_data = ""
    clip_text = get_clipboard()
    if clip_text.startswith("{") and "gameParameters" in clip_text:
        print("📋 Found Unciv game save in your clipboard!")
        save_data = clip_text
    elif os.path.exists(args.save):
        print(f"📁 Reading save data from '{args.save}'...")
        with open(args.save, "r", encoding="utf-8") as f:
            save_data = f.read()

    if not save_data:
        print("Please copy your Unciv game save to your clipboard (Menu -> Copy game to clipboard)")
        print("or paste the save JSON string below:")
        try:
            save_data = input("\nPaste save string and press Enter:\n").strip()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return

    if not (save_data.startswith("{") and ("gameParameters" in save_data or "turns" in save_data)):
        print("❌ Error: Invalid Unciv save format.")
        return

    # Execute AI turn
    new_save = play_one_ai_turn(save_data, strategy=args.strategy, ai_civ=args.civ)
    if new_save:
        with open(args.save, "w", encoding="utf-8") as out_f:
            out_f.write(new_save)
        
        copied = set_clipboard(new_save)
        if copied:
            print("📋 Updated save has been COPIED TO YOUR CLIPBOARD!")
            print("   👉 In Unciv: Click 'Load game from clipboard' to take your turn!")
        else:
            print(f"💾 Updated save saved to '{args.save}'.")

if __name__ == "__main__":
    main()
