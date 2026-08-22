"""
Unciv AI Interactive Browser Replay Dashboard & Multi-Replay Manager
Automatically discovers, lists, and visualizes turn-by-turn match replays from the replays/ directory.
Defaults to the most recently created replay and allows instant switching between past games.
"""

import os
import sys
import json
import glob
import time
import argparse
import urllib.parse
import webbrowser
import http.server
import socketserver
import threading
from typing import Dict, Any, List, Optional, Tuple

def get_available_replays(replay_dir: str = "replays") -> List[Dict[str, Any]]:
    """
    Scans the replay directory and workspace for replay files, sorted by newest first.
    """
    files = []
    if os.path.exists(replay_dir):
        match_files = glob.glob(os.path.join(replay_dir, "replay_*.json"))
        if match_files:
            files.extend(match_files)
        else:
            files.extend(glob.glob(os.path.join(replay_dir, "*.json")))
    if not files and os.path.exists("replay_history.json"):
        files.append("replay_history.json")

    # Deduplicate and sort by modification time (descending)
    unique_files = list(dict.fromkeys([os.path.abspath(f) for f in files]))
    unique_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)

    replays_meta = []
    for filepath in unique_files:
        try:
            filename = os.path.basename(filepath)
            mtime = os.path.getmtime(filepath)
            time_str = time.strftime("%b %d %H:%M:%S", time.localtime(mtime))
            
            with open(filepath, "r", encoding="utf-8") as rf:
                data = json.load(rf)

            civ = data.get("civ", "Unknown")
            directive = data.get("directive", "Balanced Strategy")
            turns_count = len(data.get("turns", []))
            
            replays_meta.append({
                "path": filepath,
                "filename": filename,
                "civ": civ,
                "directive": directive,
                "turns_count": turns_count,
                "modified": time_str,
                "mtime": mtime
            })
        except Exception:
            continue

    return replays_meta

def get_latest_replay_path(replay_dir: str = "replays") -> Optional[str]:
    """
    Returns the path to the newest replay file.
    """
    replays = get_available_replays(replay_dir)
    return replays[0]["path"] if replays else None

def generate_replay_html(history_data: Dict[str, Any], available_replays: List[Dict[str, Any]] = None) -> str:
    """
    Generates a standalone single-file HTML replay dashboard with embedded JSON data
    and an interactive match switcher dropdown.
    """
    turns = history_data.get("turns", [])
    total_turns = len(turns)
    civ_name = history_data.get("civ") or history_data.get("civilization") or (turns[0].get("civ_name") if turns else None) or "Rome"
    directive = history_data.get("directive", "Balanced Strategy")
    json_payload = json.dumps(history_data)
    replays_json = json.dumps(available_replays or [])

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unciv AI Replay Viewer - {civ_name}</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏛️</text></svg>">
    <style>
        :root {{
            --bg-primary: #121418;
            --bg-secondary: #1a1e24;
            --bg-card: #222730;
            --border-color: #313844;
            --accent-gold: #f59e0b;
            --accent-blue: #38bdf8;
            --accent-green: #22c55e;
            --accent-purple: #a855f7;
            --accent-red: #ef4444;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        /* Header */
        header {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 8px 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            z-index: 10;
            gap: 12px;
        }}

        .header-title {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-shrink: 0;
        }}

        .civ-badge {{
            background: var(--accent-gold);
            color: #000;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .replay-picker-wrap {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            color: var(--text-muted);
        }}

        button.spectator-btn {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s ease;
        }}

        button.spectator-btn:hover {{
            border-color: #c084fc;
        }}

        button.spectator-btn.active {{
            background: #9333ea;
            color: #ffffff;
            border-color: #c084fc;
            box-shadow: 0 0 12px rgba(147, 51, 234, 0.4);
        }}

        select.replay-select {{
            background: var(--bg-card);
            color: var(--text-main);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 13px;
            outline: none;
            cursor: pointer;
            max-width: 320px;
        }}

        select.replay-select:focus {{
            border-color: var(--accent-gold);
        }}

        .directive-tag {{
            font-size: 12px;
            color: var(--text-muted);
            background: var(--bg-card);
            padding: 4px 8px;
            border-radius: 4px;
            border: 1px solid var(--border-color);
            max-width: 320px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .stats-ticker {{
            display: flex;
            gap: 12px;
            font-size: 13px;
            font-weight: 500;
            flex-shrink: 0;
        }}

        .stat-item {{
            display: flex;
            align-items: center;
            gap: 4px;
            background: var(--bg-card);
            padding: 3px 8px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
        }}

        /* Main Workspace */
        .workspace {{
            flex: 1;
            display: flex;
            overflow: hidden;
            position: relative;
        }}

        /* Map Canvas */
        .map-container {{
            flex: 1;
            position: relative;
            background: #090b0e;
            overflow: hidden;
            cursor: grab;
        }}

        .map-container:active {{
            cursor: grabbing;
        }}

        canvas {{
            display: block;
        }}

        /* Map Legend Overlay */
        .map-legend {{
            position: absolute;
            top: 15px;
            left: 15px;
            background: rgba(26, 30, 36, 0.85);
            backdrop-filter: blur(8px);
            border: 1px solid var(--border-color);
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 12px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            pointer-events: none;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
        }}

        /* Tooltip */
        #map-tooltip {{
            position: absolute;
            display: none;
            background: rgba(18, 20, 24, 0.95);
            border: 1px solid var(--accent-gold);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            pointer-events: none;
            z-index: 100;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            max-width: 220px;
        }}

        /* Sidebar */
        aside {{
            width: 380px;
            background: var(--bg-secondary);
            border-left: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        .sidebar-section {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border-color);
        }}

        .sidebar-section h3 {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .advisor-box {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 13px;
            line-height: 1.4;
        }}

        .advisor-focus {{
            font-weight: 600;
            color: var(--accent-blue);
            margin-bottom: 4px;
        }}

        .engine-badge {{
            font-size: 10px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 4px;
            background: #334155;
            color: #94a3b8;
            letter-spacing: 0.3px;
        }}

        .engine-badge.llm {{
            background: #1e1b4b;
            color: #a5b4fc;
            border: 1px solid #6366f1;
        }}

        .raw-toggle-btn {{
            background: rgba(255,255,255,0.06);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 4px;
            cursor: pointer;
            width: 100%;
            text-align: center;
            transition: all 0.15s ease;
        }}

        .raw-toggle-btn:hover {{
            background: rgba(255,255,255,0.12);
            color: #ffffff;
            border-color: #6366f1;
        }}

        .tech-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 8px 12px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .tech-header {{
            display: flex;
            justify-content: space-between;
            font-weight: 600;
            font-size: 13px;
        }}

        .progress-bar {{
            height: 6px;
            background: #111;
            border-radius: 3px;
            overflow: hidden;
        }}

        .progress-fill {{
            height: 100%;
            background: var(--accent-blue);
            width: 0%;
            transition: width 0.3s ease;
        }}

        .log-container {{
            flex: 1;
            overflow-y: auto;
            padding: 10px 16px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            font-size: 12px;
        }}

        .log-entry {{
            background: var(--bg-card);
            padding: 6px 10px;
            border-radius: 6px;
            border-left: 3px solid var(--accent-gold);
            line-height: 1.3;
        }}

        .notif-entry {{
            background: rgba(56, 189, 248, 0.1);
            border-left: 3px solid var(--accent-blue);
            padding: 6px 10px;
            border-radius: 4px;
        }}

        /* Bottom Controls */
        footer {{
            background: var(--bg-secondary);
            border-top: 1px solid var(--border-color);
            padding: 10px 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .timeline-controls {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}

        .btn-group {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        button {{
            background: var(--bg-card);
            color: var(--text-main);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            transition: all 0.15s ease;
        }}

        button:hover {{
            background: var(--border-color);
            border-color: var(--accent-gold);
        }}

        button.primary {{
            background: var(--accent-gold);
            color: #000;
            border-color: var(--accent-gold);
            font-weight: 600;
        }}

        button.primary:hover {{
            background: #d97706;
        }}

        .slider-container {{
            flex: 1;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        input[type="range"] {{
            flex: 1;
            height: 6px;
            border-radius: 3px;
            background: var(--bg-card);
            outline: none;
            cursor: pointer;
            accent-color: var(--accent-gold);
        }}

        .turn-display {{
            font-size: 14px;
            font-weight: 700;
            color: var(--accent-gold);
            min-width: 110px;
            text-align: right;
        }}

        /* Graphs Modal */
        #charts-modal {{
            display: none;
            position: fixed;
            inset: 40px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.8);
            z-index: 200;
            flex-direction: column;
            padding: 24px;
        }}

        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}

        .chart-canvas-container {{
            flex: 1;
            position: relative;
            background: var(--bg-card);
            border-radius: 8px;
            border: 1px solid var(--border-color);
            padding: 10px;
        }}
    </style>
</head>
<body>

    <header>
        <div class="header-title">
            <span class="civ-badge" id="civ-badge">{civ_name}</span>
            
            <div class="replay-picker-wrap">
                <label for="replay-select">📁 Match:</label>
                <select id="replay-select" class="replay-select">
                    <!-- Populated dynamically -->
                </select>
            </div>

            <button id="btn-spectator" class="spectator-btn" title="Toggle Spectator Mode / Reveal All (Hotkey: V)">👁️ Spectator: OFF</button>

            <span class="directive-tag" id="header-directive" title="{directive}">🎯 {directive}</span>
        </div>

        <div class="stats-ticker">
            <div class="stat-item" title="Treasury Gold">🪙 <span id="stat-gold">0</span> (<span id="stat-gpt">+0</span>)</div>
            <div class="stat-item" title="Science Output">🔬 <span id="stat-science">+0</span></div>
            <div class="stat-item" title="Culture Output">🎭 <span id="stat-culture">+0</span></div>
            <div class="stat-item" title="Happiness">😊 <span id="stat-happiness">0</span></div>
            <div class="stat-item" title="Empire Score">⭐ <span id="stat-score">0</span></div>
        </div>
    </header>

    <div class="workspace">
        <div class="map-container" id="map-wrap">
            <canvas id="hex-canvas"></canvas>
            
            <div class="map-legend">
                <div class="legend-item"><div class="legend-color" style="background:#558b2f;"></div> Grassland / Plains</div>
                <div class="legend-item"><div class="legend-color" style="background:#d7ccc8;"></div> Desert / Dunes</div>
                <div class="legend-item"><div class="legend-color" style="background:#0277bd;"></div> Ocean / Coast</div>
                <div class="legend-item"><div class="legend-color" style="background:#546e7a;"></div> Mountain / Hills</div>
                <div class="legend-item"><div class="legend-color" style="background:#2e7d32;"></div> Forest / Jungle</div>
                <div class="legend-item"><div class="legend-color" style="background:#f59e0b; border-radius: 50%;"></div> [C] City / [u] Unit</div>
            </div>

            <div id="map-tooltip"></div>
        </div>

        <aside>
            <div class="sidebar-section">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <h3 style="margin-bottom: 0;">Decision Engine</h3>
                    <span id="engine-badge" class="engine-badge">⚡ Heuristics</span>
                </div>
                <div class="advisor-box">
                    <div class="advisor-focus" id="adv-focus">Balanced Growth</div>
                    <div id="adv-reasoning" style="color: #e2e8f0; font-size: 13px;">Analyzing map topology and expansion candidates...</div>

                    <div id="adv-strat-analysis-wrap" style="display:none; margin-top:8px; border-top:1px solid rgba(255,255,255,0.1); padding-top:6px;">
                        <div style="font-size:11px; font-weight:700; color:#a5b4fc; margin-bottom:2px;">🧠 Strategic Plan & Trajectory:</div>
                        <div id="adv-strat-analysis" style="font-size:12px; color:#cbd5e1; line-height:1.4;"></div>
                    </div>

                    <div id="adv-tactical-wrap" style="display:none; margin-top:8px; border-top:1px solid rgba(255,255,255,0.1); padding-top:6px;">
                        <div style="font-size:11px; font-weight:700; color:#38bdf8; margin-bottom:2px;">🎯 Tactical Intent:</div>
                        <div id="adv-tactical" style="font-size:12px; color:#cbd5e1; line-height:1.4;"></div>
                    </div>

                    <div id="adv-error-wrap" style="display:none; margin-top:8px; border-top:1px solid rgba(239,68,68,0.3); padding-top:6px;">
                        <div style="font-size:11px; font-weight:700; color:#f87171; margin-bottom:2px;">⚠️ LLM Notice:</div>
                        <div id="adv-error" style="font-size:11px; color:#fca5a5; line-height:1.3;"></div>
                    </div>

                    <div id="adv-raw-toggle-wrap" style="display:none; margin-top:10px;">
                        <button id="btn-toggle-raw" class="raw-toggle-btn">🔍 View Raw LLM Output</button>
                        <pre id="adv-raw-response" style="display:none; margin-top:6px; background:#0f172a; padding:8px; border-radius:4px; font-size:10px; color:#38bdf8; max-height:160px; overflow-y:auto; white-space:pre-wrap; border:1px solid rgba(255,255,255,0.1);"></pre>
                    </div>
                </div>
            </div>

            <div class="sidebar-section">
                <h3>Technology Research</h3>
                <div class="tech-card">
                    <div class="tech-header">
                        <span id="tech-name">None</span>
                        <span id="tech-turns">0 turns</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="tech-progress"></div>
                    </div>
                </div>
            </div>

            <div class="sidebar-section" style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
                <h3>Turn Decisions & Notifications</h3>
                <div class="log-container" id="turn-logs"></div>
            </div>
        </aside>
    </div>

    <footer>
        <div class="timeline-controls">
            <div class="btn-group">
                <button id="btn-prev" title="Previous Turn (Left Arrow)">⏮</button>
                <button id="btn-play" class="primary" title="Play / Pause (Spacebar)">▶ Play</button>
                <button id="btn-next" title="Next Turn (Right Arrow)">⏭</button>
            </div>

            <div class="slider-container">
                <input type="range" id="turn-slider" min="0" max="{max(0, total_turns-1)}" value="0">
                <div class="turn-display" id="turn-indicator">Turn 0 (1/{total_turns})</div>
            </div>

            <div class="btn-group">
                <button id="btn-speed">1.0x</button>
                <button id="btn-charts">📊 Charts</button>
            </div>
        </div>
    </footer>

    <!-- Historical Growth Charts Modal -->
    <div id="charts-modal">
        <div class="modal-header">
            <h2>Empire Growth & Metric Progression</h2>
            <button id="btn-close-charts">✕ Close</button>
        </div>
        <div class="chart-canvas-container">
            <canvas id="metrics-chart"></canvas>
        </div>
    </div>

    <script>
        let currentReplay = {json_payload};
        const availableReplays = {replays_json};
        let turnsData = currentReplay.turns || [];
        let currentTurnIdx = 0;
        let isPlaying = false;
        let playbackSpeed = 1.0;
        let playInterval = null;

        // Canvas & Hex Geometry
        const canvas = document.getElementById("hex-canvas");
        const ctx = canvas.getContext("2d");
        const tooltip = document.getElementById("map-tooltip");
        const mapWrap = document.getElementById("map-wrap");

        let hexSize = 34;
        let panX = 0;
        let panY = 0;
        let isDragging = false;
        let startDragX = 0;
        let startDragY = 0;

        // Populate Replay Selector
        const replaySelect = document.getElementById("replay-select");
        if (availableReplays.length > 0) {{
            replaySelect.innerHTML = "";
            availableReplays.forEach((rep, idx) => {{
                const opt = document.createElement("option");
                opt.value = rep.filename;
                opt.innerText = `${{rep.civ}} - ${{rep.turns_count}} turns (${{rep.modified}})`;
                replaySelect.appendChild(opt);
            }});
        }} else {{
            replaySelect.innerHTML = `<option value="">Current Match (${{turnsData.length}} turns)</option>`;
        }}

        replaySelect.addEventListener("change", async (e) => {{
            const selectedFilename = e.target.value;
            if (!selectedFilename) return;
            try {{
                const resp = await fetch(`/api/replay?file=${{encodeURIComponent(selectedFilename)}}`);
                if (resp.ok) {{
                    const newReplayData = await resp.json();
                    loadNewReplay(newReplayData);
                }}
            }} catch (err) {{
                console.warn("Could not load replay via API (static mode):", err);
            }}
        }});

        function loadNewReplay(newReplay) {{
            currentReplay = newReplay;
            turnsData = currentReplay.turns || [];
            
            document.getElementById("civ-badge").innerText = currentReplay.civ || "Unknown";
            document.getElementById("header-directive").innerText = "🎯 " + (currentReplay.directive || "Balanced Strategy");
            document.getElementById("header-directive").title = currentReplay.directive || "Balanced Strategy";
            
            const slider = document.getElementById("turn-slider");
            slider.min = 0;
            slider.max = Math.max(0, turnsData.length - 1);
            slider.value = 0;

            if (isPlaying) togglePlay();
            currentTurnIdx = 0;
            updateTurn(0);
        }}

        function resizeCanvas() {{
            canvas.width = mapWrap.clientWidth;
            canvas.height = mapWrap.clientHeight;
            if (panX === 0 && panY === 0) {{
                panX = canvas.width / 2;
                panY = canvas.height / 2;
            }}
            renderMap();
        }}
        window.addEventListener("resize", resizeCanvas);

        // Hex coordinate helpers (pointy-topped hexes)
        function hexToPixel(q, r) {{
            const x = hexSize * (Math.sqrt(3) * q + Math.sqrt(3)/2 * r);
            const y = hexSize * (3/2 * r);
            return {{ x: x + panX, y: y + panY }};
        }}

        function drawHexagon(cx, cy, radius, fillColor, strokeColor = "#222", lineWidth = 1) {{
            ctx.beginPath();
            for (let i = 0; i < 6; i++) {{
                const angle = (Math.PI / 180) * (60 * i - 30);
                const x = cx + radius * Math.cos(angle);
                const y = cy + radius * Math.sin(angle);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }}
            ctx.closePath();
            ctx.fillStyle = fillColor;
            ctx.fill();
            if (strokeColor) {{
                ctx.strokeStyle = strokeColor;
                ctx.lineWidth = lineWidth;
                ctx.stroke();
            }}
        }}

        function getTerrainColor(terrain, features, isHill, isExplored, isVisible) {{
            if (!isExplored) return "#0c1015";
            let baseCol = "#4caf50";
            if (!terrain) baseCol = "#212121";
            else if (terrain.includes("Ocean")) baseCol = "#0f2b48";
            else if (terrain.includes("Coast") || terrain.includes("Water")) baseCol = "#1976d2";
            else if (terrain.includes("Mountain")) baseCol = "#475569";
            else if (terrain.includes("Desert")) baseCol = "#d4ac0d";
            else if (terrain.includes("Tundra")) baseCol = "#78909c";
            else if (terrain.includes("Snow") || terrain.includes("Ice")) baseCol = "#e2e8f0";
            else if (terrain.includes("Grassland")) baseCol = "#2e7d32";
            else if (terrain.includes("Plains")) baseCol = "#7cb342";

            if (features) {{
                if (features.includes("Forest") || features.includes("Jungle")) baseCol = "#1b5e20";
                else if (features.includes("Flood plain") || features.includes("Flood Plains")) baseCol = "#558b2f";
                else if (features.includes("Marsh")) baseCol = "#33691e";
                else if (features.includes("Atoll")) baseCol = "#00838f";
            }}

            if (isHill && !terrain.includes("Mountain") && !terrain.includes("Water")) {{
                baseCol = "#5c8d37";
            }}

            return baseCol;
        }}

        function getResourceIcon(resource) {{
            if (!resource) return "";
            const map = {{
                "Wheat": "🌾", "Iron": "⛏️", "Horses": "🐎", "Gems": "💎", "Gold": "🪙",
                "Silver": "🥈", "Coal": "⬛", "Oil": "🛢️", "Aluminum": "⚙️", "Uranium": "☢️",
                "Cattle": "🐄", "Sheep": "🐑", "Deer": "🦌", "Fish": "🐟", "Whale": "🐋",
                "Crab": "🦀", "Cotton": "🧶", "Silk": "👘", "Sugar": "🍬", "Spices": "🌿",
                "Wine": "🍷", "Marble": "🏛️", "Ivory": "🐘", "Furs": "🧥", "Dyes": "🎨",
                "Copper": "🟤", "Salt": "🧂", "Truffles": "🍄", "Citrus": "🍊", "Banana": "🍌"
            }};
            for (let [k, icon] of Object.entries(map)) {{
                if (resource.includes(k)) return icon;
            }}
            return "✨";
        }}

        let hoveredTile = null;
        let spectatorMode = false;

        const specBtn = document.getElementById("btn-spectator");
        specBtn.addEventListener("click", toggleSpectator);

        function toggleSpectator() {{
            spectatorMode = !spectatorMode;
            specBtn.classList.toggle("active", spectatorMode);
            specBtn.innerText = spectatorMode ? "👁️ Spectator: ON" : "👁️ Spectator: OFF";
            renderMap();
        }}

        function getCivColor(civName) {{
            if (!civName) return "#64748b";
            if (civName.includes("Rome")) return "#f59e0b";
            if (civName.includes("Greece")) return "#06b6d4";
            if (civName.includes("Persia")) return "#ec4899";
            if (civName.includes("Egypt")) return "#eab308";
            if (civName.includes("America")) return "#3b82f6";
            if (civName.includes("Germany")) return "#64748b";
            if (civName.includes("Spain")) return "#f43f5e";
            if (civName.includes("Barbarian")) return "#dc2626";
            return "#10b981";
        }}

        function renderMap() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            if (turnsData.length === 0) return;

            const turn = turnsData[currentTurnIdx];
            const tiles = (turn.map && turn.map.tiles) ? turn.map.tiles : [];
            const playerCities = turn.cities || [];
            const playerUnits = turn.units || [];

            // 1. Draw Hex Grid & Biomes
            tiles.forEach(t => {{
                const pos = hexToPixel(t.x, t.y);
                const isExplored = spectatorMode ? true : (t.explored !== false);
                const isVisible = spectatorMode ? true : (t.visible !== false);
                const col = getTerrainColor(t.terrain, t.features, t.is_hill, isExplored, isVisible);
                
                const strokeCol = isExplored ? "rgba(0,0,0,0.3)" : "rgba(255,255,255,0.03)";
                drawHexagon(pos.x, pos.y, hexSize, col, strokeCol, 1.2);

                if (!isExplored) return;

                // Fog of War overlay (disabled in spectator mode)
                if (!isVisible && !spectatorMode) {{
                    drawHexagon(pos.x, pos.y, hexSize, "rgba(0,0,0,0.35)", null);
                }}

                // Mountain Peak 3D Rendering
                if (t.terrain && t.terrain.includes("Mountain")) {{
                    ctx.beginPath();
                    ctx.moveTo(pos.x, pos.y - hexSize * 0.55);
                    ctx.lineTo(pos.x + hexSize * 0.45, pos.y + hexSize * 0.4);
                    ctx.lineTo(pos.x - hexSize * 0.45, pos.y + hexSize * 0.4);
                    ctx.closePath();
                    ctx.fillStyle = "#334155";
                    ctx.fill();
                    ctx.strokeStyle = "#1e293b";
                    ctx.lineWidth = 1;
                    ctx.stroke();

                    // Snow cap on mountain peak
                    ctx.beginPath();
                    ctx.moveTo(pos.x, pos.y - hexSize * 0.55);
                    ctx.lineTo(pos.x + hexSize * 0.15, pos.y - hexSize * 0.25);
                    ctx.lineTo(pos.x - hexSize * 0.15, pos.y - hexSize * 0.25);
                    ctx.closePath();
                    ctx.fillStyle = "#ffffff";
                    ctx.fill();
                }}

                // Hills 3D contour ridges
                if (t.is_hill && !t.terrain.includes("Mountain")) {{
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y + 4, hexSize * 0.35, Math.PI, 0);
                    ctx.strokeStyle = "rgba(0,0,0,0.3)";
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }}

                // Forest / Jungle Canopy
                if (t.features && (t.features.includes("Forest") || t.features.includes("Jungle"))) {{
                    ctx.font = "10px sans-serif";
                    ctx.textAlign = "center";
                    ctx.fillText("🌲", pos.x, pos.y - 2);
                }}

                // River overlay
                if (t.has_river) {{
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, hexSize * 0.85, 0, Math.PI * 2);
                    ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }}

                // Territory border
                if (t.owner) {{
                    const ownerCol = getCivColor(t.owner);
                    drawHexagon(pos.x, pos.y, hexSize - 1, "transparent", ownerCol, 2);
                }}

                // Resource Icon
                if (t.resource) {{
                    const icon = getResourceIcon(t.resource);
                    ctx.font = "12px sans-serif";
                    ctx.textAlign = "center";
                    ctx.fillText(icon, pos.x, pos.y + 12);
                }}

                // Natural Wonder Glowing Star
                if (t.natural_wonder) {{
                    drawHexagon(pos.x, pos.y, hexSize * 0.8, "transparent", "#a855f7", 2.5);
                    ctx.font = "14px sans-serif";
                    ctx.textAlign = "center";
                    ctx.fillText("⭐", pos.x, pos.y + 2);
                }}

                // Improvement Marker
                if (t.improvement && !t.city) {{
                    ctx.fillStyle = "rgba(255,255,255,0.75)";
                    ctx.font = "9px sans-serif";
                    ctx.textAlign = "center";
                    ctx.fillText(t.improvement.substring(0, 4), pos.x, pos.y - 12);
                }}
            }});

            // 2. Draw Cities (Spectator draws all world cities, Player draws friendly/seen)
            const drawnCityCoords = new Set();
            tiles.forEach(t => {{
                if (t.city && (spectatorMode || t.explored !== false)) {{
                    const pos = hexToPixel(t.x, t.y);
                    const cityCol = getCivColor(t.owner);
                    drawnCityCoords.add(`${{t.x}},${{t.y}}`);

                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, hexSize * 0.68, 0, Math.PI * 2);
                    ctx.fillStyle = cityCol;
                    ctx.fill();
                    ctx.strokeStyle = "#ffffff";
                    ctx.lineWidth = 2;
                    ctx.stroke();

                    ctx.fillStyle = "#ffffff";
                    ctx.font = "bold 11px sans-serif";
                    ctx.textAlign = "center";
                    ctx.fillText("🏛️ " + t.city, pos.x, pos.y - 3);
                    ctx.font = "bold 9px sans-serif";
                    ctx.fillText("Pop " + (t.city_pop || 1), pos.x, pos.y + 9);
                }}
            }});

            // Draw player cities fallback if not already drawn
            playerCities.forEach(c => {{
                const loc = c.location || [0, 0];
                if (drawnCityCoords.has(`${{loc[0]}},${{loc[1]}}`)) return;
                const pos = hexToPixel(loc[0], loc[1]);
                
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, hexSize * 0.68, 0, Math.PI * 2);
                ctx.fillStyle = "#d97706";
                ctx.fill();
                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 2;
                ctx.stroke();

                ctx.fillStyle = "#ffffff";
                ctx.font = "bold 11px sans-serif";
                ctx.textAlign = "center";
                ctx.fillText("🏛️ " + c.name, pos.x, pos.y - 3);
                ctx.font = "bold 9px sans-serif";
                ctx.fillText("Pop " + (c.population || 1), pos.x, pos.y + 9);
            }});

            // 3. Draw Units
            if (spectatorMode) {{
                // Spectator: Draw all world units across all tiles
                tiles.forEach(t => {{
                    const pos = hexToPixel(t.x, t.y);
                    if (t.military_unit) {{
                        const civCol = getCivColor(t.military_civ || t.owner);
                        ctx.beginPath();
                        ctx.arc(pos.x + 10, pos.y + 10, 11, 0, Math.PI * 2);
                        ctx.fillStyle = civCol;
                        ctx.fill();
                        ctx.strokeStyle = "#ffffff";
                        ctx.lineWidth = 1.8;
                        ctx.stroke();

                        ctx.fillStyle = "#ffffff";
                        ctx.font = "bold 9px sans-serif";
                        ctx.textAlign = "center";
                        ctx.fillText("⚔️", pos.x + 10, pos.y + 13);
                    }}
                    if (t.civilian_unit) {{
                        const civCol = getCivColor(t.civilian_civ || t.owner);
                        ctx.beginPath();
                        ctx.arc(pos.x - 10, pos.y + 10, 11, 0, Math.PI * 2);
                        ctx.fillStyle = civCol;
                        ctx.fill();
                        ctx.strokeStyle = "#ffffff";
                        ctx.lineWidth = 1.8;
                        ctx.stroke();

                        ctx.fillStyle = "#ffffff";
                        ctx.font = "bold 9px sans-serif";
                        ctx.textAlign = "center";
                        ctx.fillText("🔨", pos.x - 10, pos.y + 13);
                    }}
                }});
            }} else {{
                // Player mode: Draw player units + visible units
                playerUnits.forEach(u => {{
                    const loc = u.location || [0, 0];
                    const pos = hexToPixel(loc[0], loc[1]);
                    const isMil = u.is_military;
                    
                    ctx.beginPath();
                    ctx.arc(pos.x + 10, pos.y + 10, 11, 0, Math.PI * 2);
                    ctx.fillStyle = isMil ? "#ef4444" : "#0284c7";
                    ctx.fill();
                    ctx.strokeStyle = "#ffffff";
                    ctx.lineWidth = 2;
                    ctx.stroke();

                    ctx.fillStyle = "#ffffff";
                    ctx.font = "bold 9px sans-serif";
                    ctx.textAlign = "center";
                    ctx.fillText(isMil ? "⚔️" : "🔨", pos.x + 10, pos.y + 13);
                }});
            }}

            // 4. Highlight Hovered Tile
            if (hoveredTile) {{
                const hPos = hexToPixel(hoveredTile.x, hoveredTile.y);
                drawHexagon(hPos.x, hPos.y, hexSize + 1, "rgba(245, 158, 11, 0.2)", "#f59e0b", 2.5);
            }}
        }}

        // Mouse Hover & Tooltip
        mapWrap.addEventListener("mousemove", (e) => {{
            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left - panX;
            const mouseY = e.clientY - rect.top - panY;

            // Approximate pixel to axial hex coord
            const q = (Math.sqrt(3)/3 * mouseX - 1/3 * mouseY) / hexSize;
            const r = (2/3 * mouseY) / hexSize;
            const rx = Math.round(q);
            const ry = Math.round(r);

            if (turnsData.length === 0) return;
            const turn = turnsData[currentTurnIdx];
            const tiles = (turn.map && turn.map.tiles) ? turn.map.tiles : [];
            const tile = tiles.find(t => t.x === rx && t.y === ry);

            if (tile && (spectatorMode || tile.explored !== false)) {{
                hoveredTile = tile;
                tooltip.style.display = "block";
                tooltip.style.left = (e.clientX + 15) + "px";
                tooltip.style.top = (e.clientY + 15) + "px";

                let info = `<strong>Hex (${{tile.x}}, ${{tile.y}})</strong><br>`;
                info += `Terrain: ${{tile.terrain || 'Plain'}}`;
                if (tile.features && tile.features.length) info += ` (${{tile.features.join(', ')}})`;
                if (tile.is_hill) info += ` [Hill]`;
                info += `<br>`;
                if (tile.resource) info += `Resource: ${{getResourceIcon(tile.resource)}} ${{tile.resource}}<br>`;
                if (tile.improvement) info += `Improvement: ${{tile.improvement}}<br>`;
                if (tile.natural_wonder) info += `Wonder: ⭐ ${{tile.natural_wonder}}<br>`;
                if (tile.owner) info += `Territory: 🏛️ ${{tile.owner}}<br>`;
                if (tile.city) info += `City: 🏛️ ${{tile.city}} (Pop ${{tile.city_pop || 1}})<br>`;
                if (tile.military_unit) info += `Military: ⚔️ ${{tile.military_unit}}<br>`;
                if (tile.civilian_unit) info += `Civilian: 🔨 ${{tile.civilian_unit}}<br>`;

                tooltip.innerHTML = info;
            }} else {{
                hoveredTile = null;
                tooltip.style.display = "none";
            }}
            renderMap();
        }});

        mapWrap.addEventListener("mouseleave", () => {{
            hoveredTile = null;
            tooltip.style.display = "none";
            renderMap();
        }});

        // Mouse Drag to Pan
        mapWrap.addEventListener("mousedown", (e) => {{
            isDragging = true;
            startDragX = e.clientX - panX;
            startDragY = e.clientY - panY;
        }});

        window.addEventListener("mousemove", (e) => {{
            if (isDragging) {{
                panX = e.clientX - startDragX;
                panY = e.clientY - startDragY;
                renderMap();
            }}
        }});

        window.addEventListener("mouseup", () => {{ isDragging = false; }});

        // Mouse Wheel to Zoom
        mapWrap.addEventListener("wheel", (e) => {{
            e.preventDefault();
            const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
            hexSize = Math.max(16, Math.min(80, hexSize * zoomFactor));
            renderMap();
        }});

        // Update UI
        function updateTurn(turnIdx) {{
            if (turnIdx < 0 || turnIdx >= turnsData.length) return;
            currentTurnIdx = turnIdx;
            document.getElementById("turn-slider").value = turnIdx;

            const data = turnsData[turnIdx];
            if (!data) return;

            const actualTurnNum = (data && data.turn !== undefined) ? data.turn : turnIdx;
            document.getElementById("turn-indicator").innerText = `Turn ${{actualTurnNum}} (${{turnIdx + 1}}/${{turnsData.length}})`;

            // Stats
            const stats = data.stats || {{}};
            document.getElementById("stat-gold").innerText = stats.gold || 0;
            document.getElementById("stat-gpt").innerText = (stats.gold_per_turn >= 0 ? "+" : "") + (stats.gold_per_turn || 0);
            document.getElementById("stat-science").innerText = "+" + (stats.science_per_turn || 0);
            document.getElementById("stat-culture").innerText = "+" + (stats.culture_per_turn || 0);
            document.getElementById("stat-happiness").innerText = stats.happiness || 0;
            document.getElementById("stat-score").innerText = stats.score || 0;

            // Tech
            const tech = data.tech || {{}};
            document.getElementById("tech-name").innerText = tech.current_tech || "None";
            document.getElementById("tech-turns").innerText = (tech.turns_to_finish ? tech.turns_to_finish + " turns" : "—");
            const progress = (tech.science_cost > 0) ? (tech.science_progress / tech.science_cost) * 100 : 0;
            document.getElementById("tech-progress").style.width = Math.min(100, progress) + "%";

            // Decision Engine & LLM badge
            const isLlm = data.decision_mode === "LLM" || !!data.llm_model || (data.plan && data.plan.reasoning && !data.plan.reasoning.includes("Advisor heuristic"));
            const engineBadge = document.getElementById("engine-badge");
            if (isLlm) {{
                const modelName = data.llm_model ? data.llm_model.split("/").pop() : "LLM";
                engineBadge.innerText = "🤖 " + modelName;
                engineBadge.className = "engine-badge llm";
            }} else {{
                engineBadge.innerText = "⚡ Heuristics";
                engineBadge.className = "engine-badge";
            }}

            // Advisor & Plan
            const adv = data.advisor || {{}};
            document.getElementById("adv-focus").innerText = adv.recommended_focus || "Balanced Growth";
            const plan = data.plan || {{}};
            document.getElementById("adv-reasoning").innerText = plan.reasoning || data.llm_reasoning || "Tactical progression.";

            // Grand Strategy / Strategic Analysis
            const stratAnalysis = plan.strategic_analysis || data.strategic_analysis;
            const stratWrap = document.getElementById("adv-strat-analysis-wrap");
            if (stratAnalysis) {{
                stratWrap.style.display = "block";
                document.getElementById("adv-strat-analysis").innerText = stratAnalysis;
            }} else {{
                stratWrap.style.display = "none";
            }}

            // Tactical Intent
            const tactical = plan.tactical_intent || data.tactical_intent;
            const tactWrap = document.getElementById("adv-tactical-wrap");
            if (tactical) {{
                tactWrap.style.display = "block";
                document.getElementById("adv-tactical").innerText = tactical;
            }} else {{
                tactWrap.style.display = "none";
            }}

            // LLM Notice / Error
            const errWrap = document.getElementById("adv-error-wrap");
            if (data.llm_error) {{
                errWrap.style.display = "block";
                document.getElementById("adv-error").innerText = data.llm_error;
            }} else {{
                errWrap.style.display = "none";
            }}

            // Raw LLM Output Toggle
            const rawWrap = document.getElementById("adv-raw-toggle-wrap");
            const rawEl = document.getElementById("adv-raw-response");
            if (data.raw_llm_response) {{
                rawWrap.style.display = "block";
                rawEl.innerText = typeof data.raw_llm_response === 'string' ? data.raw_llm_response : JSON.stringify(data.raw_llm_response, null, 2);
            }} else {{
                rawWrap.style.display = "none";
                rawEl.style.display = "none";
            }}

            // Logs
            const logsContainer = document.getElementById("turn-logs");
            logsContainer.innerHTML = "";
            (data.execution || []).forEach(log => {{
                const el = document.createElement("div");
                el.className = "log-entry";
                el.innerText = log;
                logsContainer.appendChild(el);
            }});
            (data.notifications || []).forEach(notif => {{
                const el = document.createElement("div");
                el.className = "notif-entry";
                el.innerText = "📢 " + notif;
                logsContainer.appendChild(el);
            }});

            renderMap();
        }}

        // Playback Controls
        function togglePlay() {{
            if (turnsData.length <= 1) {{
                const toast = document.createElement("div");
                toast.style.cssText = "position:fixed;top:60px;left:50%;transform:translateX(-50%);background:#f59e0b;color:#000;padding:8px 16px;border-radius:6px;font-weight:600;z-index:999;box-shadow:0 4px 12px rgba(0,0,0,0.5);";
                toast.innerText = "Only 1 turn snapshot in this replay file. Run unciv_agent.py with --turns 10+ to record a multi-turn animation!";
                document.body.appendChild(toast);
                setTimeout(() => toast.remove(), 4000);
                return;
            }}
            isPlaying = !isPlaying;
            const btn = document.getElementById("btn-play");
            if (isPlaying) {{
                btn.innerText = "⏸ Pause";
                if (currentTurnIdx >= turnsData.length - 1) {{
                    currentTurnIdx = -1;
                }}
                playInterval = setInterval(() => {{
                    if (currentTurnIdx >= turnsData.length - 1) {{
                        togglePlay();
                    }} else {{
                        updateTurn(currentTurnIdx + 1);
                    }}
                }}, 1000 / playbackSpeed);
            }} else {{
                btn.innerText = "▶ Play";
                clearInterval(playInterval);
            }}
        }}

        document.getElementById("btn-play").addEventListener("click", togglePlay);
        document.getElementById("btn-prev").addEventListener("click", () => updateTurn(currentTurnIdx - 1));
        document.getElementById("btn-next").addEventListener("click", () => updateTurn(currentTurnIdx + 1));
        document.getElementById("turn-slider").addEventListener("input", (e) => updateTurn(parseInt(e.target.value)));

        const rawToggleBtn = document.getElementById("btn-toggle-raw");
        if (rawToggleBtn) {{
            rawToggleBtn.addEventListener("click", () => {{
                const rawEl = document.getElementById("adv-raw-response");
                rawEl.style.display = (rawEl.style.display === "none" || !rawEl.style.display) ? "block" : "none";
                rawToggleBtn.innerText = (rawEl.style.display === "block") ? "✖ Hide Raw LLM Output" : "🔍 View Raw LLM Output";
            }});
        }}

        document.getElementById("btn-speed").addEventListener("click", () => {{
            const speeds = [0.5, 1.0, 2.0, 5.0];
            const nextIdx = (speeds.indexOf(playbackSpeed) + 1) % speeds.length;
            playbackSpeed = speeds[nextIdx];
            document.getElementById("btn-speed").innerText = playbackSpeed + "x";
            if (isPlaying) {{
                clearInterval(playInterval);
                playInterval = setInterval(() => {{
                    if (currentTurnIdx >= turnsData.length - 1) togglePlay();
                    else updateTurn(currentTurnIdx + 1);
                }}, 1000 / playbackSpeed);
            }}
        }});

        // Keyboard navigation
        window.addEventListener("keydown", (e) => {{
            if (e.code === "KeyV" || e.code === "KeyF") {{
                toggleSpectator();
            }} else if (e.code === "Space") {{
                e.preventDefault();
                togglePlay();
            }} else if (e.code === "ArrowLeft") {{
                updateTurn(currentTurnIdx - 1);
            }} else if (e.code === "ArrowRight") {{
                updateTurn(currentTurnIdx + 1);
            }}
        }});

        // Charts Modal
        const chartsModal = document.getElementById("charts-modal");
        document.getElementById("btn-charts").addEventListener("click", () => {{
            chartsModal.style.display = "flex";
            drawCharts();
        }});
        document.getElementById("btn-close-charts").addEventListener("click", () => {{
            chartsModal.style.display = "none";
        }});

        function drawCharts() {{
            const cCanvas = document.getElementById("metrics-chart");
            const cCtx = cCanvas.getContext("2d");
            cCanvas.width = cCanvas.parentElement.clientWidth - 20;
            cCanvas.height = cCanvas.parentElement.clientHeight - 20;
            cCtx.clearRect(0, 0, cCanvas.width, cCanvas.height);

            const scores = turnsData.map(t => (t.stats && t.stats.score) || 0);
            const sciences = turnsData.map(t => (t.stats && t.stats.science_per_turn) || 0);
            const maxVal = Math.max(...scores, ...sciences, 50);

            function drawLine(data, color, label) {{
                if (data.length < 2) return;
                cCtx.beginPath();
                cCtx.strokeStyle = color;
                cCtx.lineWidth = 2.5;
                const stepX = cCanvas.width / (data.length - 1);
                data.forEach((val, i) => {{
                    const x = i * stepX;
                    const y = cCanvas.height - (val / maxVal) * (cCanvas.height - 40) - 20;
                    if (i === 0) cCtx.moveTo(x, y);
                    else cCtx.lineTo(x, y);
                }});
                cCtx.stroke();
            }}

            drawLine(scores, "#f59e0b", "Score");
            drawLine(sciences, "#38bdf8", "Science / Turn");

            cCtx.font = "bold 12px sans-serif";
            cCtx.fillStyle = "#f59e0b";
            cCtx.fillText("— Score", 20, 25);
            cCtx.fillStyle = "#38bdf8";
            cCtx.fillText("— Science / Turn", 100, 25);
        }}

        // Initial setup
        resizeCanvas();
        updateTurn(0);
    </script>
</body>
</html>"""
    return html_template

def start_replay_server(target_file: Optional[str] = None, port: int = 8000, open_browser: bool = True):
    """
    Starts local replay HTTP server with dynamic API endpoints and multi-replay switching.
    """
    replays = get_available_replays("replays")
    
    if target_file and os.path.exists(target_file):
        active_filepath = os.path.abspath(target_file)
    elif replays:
        active_filepath = replays[0]["path"]
    else:
        print("No replay files found in 'replays/' or workspace.")
        print("Run a match first with 'python3 unciv_agent.py --civ Rome --turns 10'!")
        return

    with open(active_filepath, "r", encoding="utf-8") as f:
        history_data = json.load(f)

    html_content = generate_replay_html(history_data, replays)
    output_html_path = os.path.abspath("replay.html")
    with open(output_html_path, "w", encoding="utf-8") as out:
        out.write(html_content)

    print(f"Loaded most recent replay: {os.path.basename(active_filepath)} ({len(history_data.get('turns', []))} turns)")
    print(f"Found {len(replays)} total replay file(s) available in dropdown switcher.")

    class ReplayMultiHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            try:
                if parsed.path == "/favicon.ico":
                    self.send_response(204)
                    self.end_headers()
                    return

                if parsed.path in ("/", "/replay", "/replay.html"):
                    # Regenerate fresh HTML with newest replay scan
                    fresh_replays = get_available_replays("replays")
                    content = generate_replay_html(history_data, fresh_replays)
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(content.encode("utf-8"))

                elif parsed.path == "/api/replays":
                    fresh_replays = get_available_replays("replays")
                    self.send_response(200)
                    self.send_header("Content-type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(fresh_replays).encode("utf-8"))

                elif parsed.path == "/api/replay":
                    query = urllib.parse.parse_qs(parsed.query)
                    req_file = query.get("file", [""])[0]
                    
                    # Look in replays/ or root
                    target = os.path.join("replays", req_file) if not os.path.exists(req_file) else req_file
                    if os.path.exists(target):
                        with open(target, "r", encoding="utf-8") as rf:
                            rep_data = rf.read()
                        self.send_response(200)
                        self.send_header("Content-type", "application/json; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(rep_data.encode("utf-8"))
                    else:
                        self.send_response(404)
                        self.end_headers()
                else:
                    super().do_GET()
            except (BrokenPipeError, ConnectionResetError):
                pass

    url = f"http://127.0.0.1:{port}"
    print(f"Serving replay dashboard at: {url}")
    print("Press Ctrl+C to stop the replay server.")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    with socketserver.TCPServer(("127.0.0.1", port), ReplayMultiHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nReplay server stopped.")

def main():
    parser = argparse.ArgumentParser(description="Unciv AI Interactive Browser Replay Dashboard")
    parser.add_argument("--file", type=str, default="", help="Specific replay JSON file to load (default: most recent file in replays/)")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve replay dashboard on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    parser.add_argument("--export-only", action="store_true", help="Export standalone replay.html without starting server")

    args = parser.parse_args()

    if args.export_only:
        replays = get_available_replays("replays")
        target_path = args.file if args.file and os.path.exists(args.file) else (replays[0]["path"] if replays else "replay_history.json")
        if not os.path.exists(target_path):
            print("Error: No replay files found.")
            return
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        html = generate_replay_html(data, replays)
        out_path = os.path.abspath("replay.html")
        with open(out_path, "w", encoding="utf-8") as out:
            out.write(html)
        print(f"Successfully exported standalone replay dashboard: {out_path}")
    else:
        start_replay_server(target_file=args.file, port=args.port, open_browser=not args.no_browser)

if __name__ == "__main__":
    main()
