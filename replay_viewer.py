"""
Unciv AI Interactive Browser Replay Dashboard & Local Viewer Server
Generates a standalone, self-contained HTML5 Canvas/SVG dashboard to visually scrub,
play, and inspect turn-by-turn Unciv AI matches.
"""

import os
import sys
import json
import argparse
import webbrowser
import http.server
import socketserver
import threading
from typing import Dict, Any, List, Optional

def generate_replay_html(history_data: Dict[str, Any]) -> str:
    """
    Generates a standalone single-file HTML replay dashboard with embedded JSON data.
    """
    civ_name = history_data.get("civ", "Unknown")
    directive = history_data.get("directive", "Balanced Strategy")
    turns = history_data.get("turns", [])
    total_turns = len(turns)
    json_payload = json.dumps(history_data)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unciv AI Replay Viewer - {civ_name}</title>
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
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            z-index: 10;
        }}

        .header-title {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .civ-badge {{
            background: var(--accent-gold);
            color: #000;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .directive-tag {{
            font-size: 13px;
            color: var(--text-muted);
            background: var(--bg-card);
            padding: 4px 10px;
            border-radius: 4px;
            border: 1px solid var(--border-color);
            max-width: 400px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .stats-ticker {{
            display: flex;
            gap: 16px;
            font-size: 14px;
            font-weight: 500;
        }}

        .stat-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            background: var(--bg-card);
            padding: 4px 10px;
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
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
        }}

        .sidebar-section h3 {{
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .advisor-box {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px;
            font-size: 13px;
            line-height: 1.4;
        }}

        .advisor-focus {{
            font-weight: 600;
            color: var(--accent-blue);
            margin-bottom: 4px;
        }}

        .tech-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 12px;
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
            padding: 12px 16px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 12px;
        }}

        .log-entry {{
            background: var(--bg-card);
            padding: 8px 10px;
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
            padding: 12px 24px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .timeline-controls {{
            display: flex;
            align-items: center;
            gap: 16px;
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
            padding: 6px 14px;
            font-size: 14px;
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
            font-size: 15px;
            font-weight: 700;
            color: var(--accent-gold);
            min-width: 90px;
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
            <span class="civ-badge">{civ_name}</span>
            <span class="directive-tag" title="{directive}">🎯 {directive}</span>
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
                <h3>Strategic Advisor</h3>
                <div class="advisor-box">
                    <div class="advisor-focus" id="adv-focus">Balanced Growth</div>
                    <div id="adv-reasoning">Analyzing map topology and expansion candidates...</div>
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
                <div class="turn-display" id="turn-indicator">Turn 0 / {max(0, total_turns-1)}</div>
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
        const REPLAY_DATA = {json_payload};
        const turnsData = REPLAY_DATA.turns || [];
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

        function getTerrainColor(terrain, features) {{
            if (!terrain) return "#212121";
            if (terrain.includes("Ocean")) return "#01579b";
            if (terrain.includes("Coast") || terrain.includes("Water")) return "#0288d1";
            if (terrain.includes("Mountain")) return "#455a64";
            if (terrain.includes("Desert")) return "#d7ccc8";
            if (terrain.includes("Tundra")) return "#90a4ae";
            if (features && (features.includes("Forest") || features.includes("Jungle"))) return "#2e7d32";
            if (features && features.includes("Hill")) return "#689f38";
            if (terrain.includes("Grassland")) return "#558b2f";
            if (terrain.includes("Plains")) return "#7cb342";
            return "#4caf50";
        }}

        function renderMap() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            if (turnsData.length === 0) return;

            const turn = turnsData[currentTurnIdx];
            const tiles = (turn.map && turn.map.tiles) ? turn.map.tiles : [];
            const cities = turn.cities || [];
            const units = turn.units || [];

            // Draw hex tiles
            tiles.forEach(t => {{
                const pos = hexToPixel(t.x, t.y);
                const col = getTerrainColor(t.terrain, t.features);
                drawHexagon(pos.x, pos.y, hexSize, col, "rgba(0,0,0,0.35)", 1.5);

                // Resource text
                if (t.resource) {{
                    ctx.fillStyle = "#ffffff";
                    ctx.font = "10px sans-serif";
                    ctx.textAlign = "center";
                    ctx.fillText(t.resource.substring(0, 4), pos.x, pos.y + 12);
                }}
            }});

            // Draw cities
            cities.forEach(c => {{
                const loc = c.location || [0, 0];
                const pos = hexToPixel(loc[0], loc[1]);
                
                // City territory circle / banner
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, hexSize * 0.7, 0, Math.PI * 2);
                ctx.fillStyle = "rgba(245, 158, 11, 0.85)";
                ctx.fill();
                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 2;
                ctx.stroke();

                ctx.fillStyle = "#000000";
                ctx.font = "bold 11px sans-serif";
                ctx.textAlign = "center";
                ctx.fillText("🏛️ " + c.name, pos.x, pos.y - 4);
                ctx.font = "9px sans-serif";
                ctx.fillText("Pop " + (c.population || 1), pos.x, pos.y + 8);
            }});

            // Draw units
            units.forEach(u => {{
                const loc = u.location || [0, 0];
                const pos = hexToPixel(loc[0], loc[1]);
                const isMil = u.is_military;
                
                ctx.beginPath();
                ctx.arc(pos.x + 8, pos.y + 8, 10, 0, Math.PI * 2);
                ctx.fillStyle = isMil ? "#ef4444" : "#38bdf8";
                ctx.fill();
                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 1.5;
                ctx.stroke();

                ctx.fillStyle = "#ffffff";
                ctx.font = "bold 9px sans-serif";
                ctx.textAlign = "center";
                ctx.fillText(isMil ? "u" : "s", pos.x + 8, pos.y + 11);
            }});
        }}

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

            // Advisor
            const adv = data.advisor || {{}};
            document.getElementById("adv-focus").innerText = adv.recommended_focus || "Balanced Growth";
            const plan = data.plan || {{}};
            document.getElementById("adv-reasoning").innerText = plan.reasoning || "Tactical progression.";

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
            if (e.code === "Space") {{
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

            // Draw line helper
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

            // Legend
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

def start_replay_server(replay_file: str, port: int = 8000, open_browser: bool = True):
    """
    Loads match history and serves the interactive replay dashboard over a local HTTP server.
    """
    if not os.path.exists(replay_file):
        print(f"Error: Replay history file '{replay_file}' not found.")
        print("Run a match first with 'python3 unciv_agent.py --civ Rome --turns 10' to record a replay!")
        return

    with open(replay_file, "r", encoding="utf-8") as f:
        history_data = json.load(f)

    html_content = generate_replay_html(history_data)
    output_html_path = os.path.abspath("replay.html")
    with open(output_html_path, "w", encoding="utf-8") as out:
        out.write(html_content)

    print(f"Compiled standalone replay dashboard to: {output_html_path}")

    class ReplayHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/replay" or self.path == "/replay.html":
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))
            else:
                super().do_GET()

    url = f"http://127.0.0.1:{port}"
    print(f"Serving interactive replay dashboard at: {url}")
    print("Press Ctrl+C to stop the replay server.")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    with socketserver.TCPServer(("127.0.0.1", port), ReplayHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nReplay server stopped.")

def main():
    parser = argparse.ArgumentParser(description="Unciv AI Interactive Browser Replay Dashboard")
    parser.add_argument("--file", type=str, default="replay_history.json", help="Replay history JSON file to load (default: replay_history.json)")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve replay dashboard on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    parser.add_argument("--export-only", action="store_true", help="Only export standalone replay.html without starting server")

    args = parser.parse_args()

    if args.export_only:
        if not os.path.exists(args.file):
            print(f"Error: '{args.file}' does not exist.")
            return
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        html = generate_replay_html(data)
        out_path = os.path.abspath("replay.html")
        with open(out_path, "w", encoding="utf-8") as out:
            out.write(html)
        print(f"Successfully exported standalone replay dashboard: {out_path}")
    else:
        start_replay_server(replay_file=args.file, port=args.port, open_browser=not args.no_browser)

if __name__ == "__main__":
    main()
