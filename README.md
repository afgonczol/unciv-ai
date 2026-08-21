# Unciv AI: Strategic LLM Game-Playing Engine & Model Context Protocol (MCP) Server

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Java](https://img.shields.io/badge/Java-21%2B-orange.svg)](https://openjdk.org/)
[![MCP](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An autonomous and interactive AI agent system for **[Unciv](https://github.com/yairm210/Unciv)** (the open-source remake of Civilization V). It connects Large Language Models to the native Unciv engine using the **Model Context Protocol (MCP)**, equipped with a **Strategic AI Advisor & Heuristics Engine**, multi-provider LLM support (**OpenRouter**, **local llama.cpp**, **Ollama**, and **OpenAI-compatible endpoints**), and dynamic natural language strategic directive configuration.

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                          LLM Client / MCP Host                                 │
│  (Claude Desktop, Cursor, OpenRouter, llama.cpp server, Ollama, Custom Agents) │
└───────────────────────────────▲────────────────────────────────────────────────┘
                                │ JSON-RPC 2.0 / MCP Protocol
┌───────────────────────────────▼────────────────────────────────────────────────┐
│                     unciv_mcp_server.py (MCP Server)                           │
│   • Tools (14): get_overview, map_view, unit/city actions, tech, diplomacy... │
│   • Resources: unciv://game/state, unciv://game/advisor, unciv://game/map      │
│   • Prompts: unciv_turn_planning, unciv_war_council, unciv_expansion_plan     │
└───────▲────────────────────────────────────────────────────────────────────────┘
        │
┌───────┴───────────────────────────────┐   ┌────────────────────────────────────┐
│      strategic_advisor.py             │   │        unciv_agent.py              │
│  • Dynamic User Directive Parsing     │   │  • Autonomous & Co-Pilot CLI agent │
│  • Military Threat Radar              │   │  • Dual Backend (Cloud + Local)    │
│  • City Settling Site Scoring         │   │  • Strategic Scratchpad Memory     │
│  • Tech Tree Pathfinder               │   │  • ASCII Map Visualizer            │
│  • Empire Bottleneck Diagnostic       │   │  • Per-Turn Auto-Save & Resume     │
└───────▲───────────────────────────────┘   └──────────────────▲─────────────────┘
        │                                                      │
┌───────┴──────────────────────────────────────────────────────┴─────────────────┐
│                       unciv_engine.py (Python SDK)                             │
│   • Thread-safe TCP loopback IPC, automatic daemon management, error handling │
└───────────────────────────────────────▲────────────────────────────────────────┘
                                        │ High-Speed TCP Socket (127.0.0.1)
┌───────────────────────────────────────▼────────────────────────────────────────┐
│                      bridge/UncivBridge.java (Headless JVM)                    │
│   • Direct native Unciv execution with Unciv.jar                               │
│   • GameStarter, CityFounder, Pathing, TechManager, Diplomacy, Turn Simulation │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

- 🎯 **Dynamic Strategic Directives**: Configure high-level natural language instructions on the fly (e.g. *"Focus on science and expand rapidly"*, *"Build a massive military and conquer our neighbors"*). The advisor dynamically recalculates mathematical priority weights, military targets, and tech preferences.
- 🔌 **Model Context Protocol (MCP)**: Full MCP server implementation exposing 14 tools, resources, and pre-built prompt templates. Seamlessly connect to Claude Desktop, Cursor, or any MCP-compatible client.
- 🧠 **Strategic AI Advisor & Heuristics**: Ingests the full game state and terrain topology to compute:
  - **Military Threat Radar**: Analyzes enemy proximity, barbarian encampments, and calculates priority target nations.
  - **Expansion Site Scoring**: Evaluates map tiles for fresh water, hills, luxury/strategic resources, and optimal distances for new cities.
  - **Technology Roadmaps**: Dynamically scores researchable technologies according to active goals (Science, Domination, Culture, Economy).
  - **Empire Bottleneck Diagnostic**: Detects unhappiness deficits, treasury bleed, unassigned city production, and idle units.
- 🌐 **Dual Backend LLM Support**:
  - **Cloud APIs**: OpenRouter (Claude 3.5 Sonnet, Llama 3.3 70B, GPT-4o, DeepSeek V3, Gemini Pro) and standard OpenAI-compatible endpoints.
  - **Local Inference**: `llama.cpp` server (`http://localhost:8080/v1`) and Ollama (`http://localhost:11434/v1`) for private, offline gameplay.
- 💾 **Endurance Resilience & Auto-Save**: Auto-saves match state to `autosave.json` after every turn. Easily resume matches with `--load autosave.json` even across system sleep or restarts.
- 🗺️ **ASCII Map Visualization**: Renders axial hex map topology, terrain symbols, cities, and units directly in terminal or prompt context.
- 🎮 **Autonomous & Interactive Modes**: Run unattended autonomous play for hundreds of turns or interactive co-pilot mode with step-by-step confirmation and custom action overrides.

---

## 🚀 Quickstart

### Prerequisites
- **Java 21+** (`java -version`)
- **Python 3.10+**
- Pre-compiled `Unciv.jar` (included in repository root)

### Installation

```bash
git clone https://github.com/your-username/unciv-ai.git
cd unciv-ai
pip install -r requirements.txt
```

### 1. Run Diagnostics

Verify your Python environment, Java JRE, bridge socket, and map generator:

```bash
python3 run_diagnostics.py
```

### 2. Autonomous Play (Built-in Heuristic Mode)

Run a continuous match with Rome using heuristic AI decision-making (press `Ctrl+C` anytime to pause):

```bash
python3 unciv_agent.py --civ Rome --strategy "Focus on science and expand rapidly"
```

To run a fixed turn window (e.g. 50 turns):

```bash
python3 unciv_agent.py --civ Rome --strategy "Build a massive military and conquer our neighbors" --turns 50
```

### 3. Resume a Saved Game

```bash
python3 unciv_agent.py --load autosave.json
```

---

## 🤖 Playing with LLMs

### OpenRouter / Cloud API

```bash
export OPENROUTER_API_KEY="your_api_key_here"

python3 unciv_agent.py \
  --civ Rome \
  --api-base "https://openrouter.ai/api/v1" \
  --api-key "$OPENROUTER_API_KEY" \
  --model "meta-llama/llama-3.3-70b-instruct" \
  --strategy "Focus on science and be aggressive against European nations"
```

### Local llama.cpp or Ollama

Start your local `llama.cpp` server:
```bash
./llama-server -m your-model.gguf --port 8080
```

Then run the agent against localhost:
```bash
python3 unciv_agent.py \
  --civ Greece \
  --api-base "http://localhost:8080/v1" \
  --model "local-model" \
  --strategy "Prioritize culture and rapid expansion"
```

### Interactive Co-Pilot Mode

Add `--interactive` to review action proposals each turn, execute custom commands, or override moves:

```bash
python3 unciv_agent.py --civ Rome --interactive
```

---

## 🔌 Model Context Protocol (MCP) Setup

You can run the Unciv MCP server to let Claude Desktop or Cursor play Unciv as an external tool!

### Claude Desktop Configuration

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "unciv": {
      "command": "python3",
      "args": [
        "/path/to/unciv-ai/unciv_mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/path/to/unciv-ai"
      }
    }
  }
}
```

### Available MCP Tools (14)

| Tool | Description |
|------|-------------|
| `unciv_new_game` | Start a new match with civilization, difficulty, ruleset, and map size |
| `unciv_get_overview` | Full empire state (stats, cities, units, tech, diplomatic relations) |
| `unciv_map_view` | ASCII hex grid map centered on coordinates or cities with fog-of-war |
| `unciv_strategic_advice` | Run heuristic engine for military threats, expansion spots, and tech paths |
| `unciv_unit_move` | Move a unit toward target coordinates $(x, y)$ |
| `unciv_unit_attack` | Command a military unit to attack an enemy tile |
| `unciv_found_city` | Command a Settler to found a new city |
| `unciv_unit_action` | Perform unit actions (`fortify`, `sleep`, `wake`, `automate`, `disband`) |
| `unciv_city_production`| Set active construction in a city (units, buildings, wonders) |
| `unciv_choose_tech` | Select active technology to research |
| `unciv_adopt_policy` | Adopt a social policy branch |
| `unciv_diplomacy` | Propose peace, declare war, or demand tribute |
| `unciv_end_turn` | End current turn and simulate all AI opponent moves |
| `unciv_save_game` / `unciv_load_game` | Save or restore full match state |

---

## 🧪 Testing

Run the comprehensive unit test suite:

```bash
python3 -m unittest discover -s tests
```

---

## 📂 Project Structure

```
├── README.md               # Project documentation
├── requirements.txt        # Python dependencies
├── LICENSE                 # MIT License
├── .gitignore              # Git ignore rules
├── run_diagnostics.py      # Diagnostic startup and socket tracer
├── strategic_advisor.py    # Strategic heuristics and threat evaluator
├── unciv_agent.py          # Autonomous / interactive CLI agent
├── unciv_engine.py         # Thread-safe Python SDK for Unciv engine
├── unciv_mcp_server.py     # Model Context Protocol (MCP) server
├── Unciv.jar               # Headless Unciv engine jar
├── bridge/
│   └── UncivBridge.java    # Native Java/Kotlin JSON-RPC socket server
└── tests/                  # Automated test suite
```

---

## 📄 License

This project is licensed under the MIT License. Unciv is an open-source game created by Yair Morgenstern and contributors under the Mozilla Public License 2.0.
