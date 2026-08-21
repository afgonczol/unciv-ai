#!/usr/bin/env bash

# Unciv AI Linux / macOS Launcher Script
cd "$(dirname "$0")"

while true; do
    clear
    echo "============================================================"
    echo "              🏛️  UNCIV AI STRATEGIC AGENT  🏛️"
    echo "============================================================"
    echo ""
    echo " [1] Resume Last Game (from autosave.json)"
    echo " [2] Start New Game - Rome (Science & Rapid Expansion)"
    echo " [3] Start New Game - Rome (Domination & Military Focus)"
    echo " [4] Start New Game - Custom Civ & Strategy"
    echo " [5] Launch Interactive Browser Replay Dashboard"
    echo " [6] Play Against Strategic AI (Human vs. AI Mode)"
    echo " [7] Launch Official Unciv Game GUI (Unciv.jar)"
    echo " [8] Run Engine Diagnostics"
    echo " [0] Exit"
    echo ""
    echo "============================================================"
    read -p "Select an option (0-8): " choice

    case $choice in
        1)
            clear
            echo "Resuming game from autosave.json..."
            echo ""
            python3 unciv_agent.py --load autosave.json
            read -p "Press [Enter] to return to menu..."
            ;;
        2)
            clear
            echo "Starting new game as Rome with Science focus..."
            echo ""
            python3 unciv_agent.py --civ Rome --strategy "Focus on science and expand rapidly"
            read -p "Press [Enter] to return to menu..."
            ;;
        3)
            clear
            echo "Starting new game as Rome with Domination focus..."
            echo ""
            python3 unciv_agent.py --civ Rome --strategy "Build a massive military and conquer our neighbors"
            read -p "Press [Enter] to return to menu..."
            ;;
        4)
            clear
            read -p "Enter Civilization name (default Rome): " userciv
            userciv=${userciv:-Rome}
            read -p "Enter Strategic Directive (default 'Balanced Strategy'): " userstrat
            userstrat=${userstrat:-"Balanced Strategy"}
            read -p "Enter Map Size (Tiny, Small, Medium, Large, Huge - default Tiny): " usermapsize
            usermapsize=${usermapsize:-Tiny}
            read -p "Enter Map Type (Pangaea, Continents, Archipelago, Lakes, Inner Sea - default Pangaea): " usermaptype
            usermaptype=${usermaptype:-Pangaea}
            read -p "Enter Difficulty (Settler, Prince, King, Deity - default Prince): " userdiff
            userdiff=${userdiff:-Prince}

            echo ""
            echo "Starting game as $userciv ($usermaptype $usermapsize, $userdiff) with directive: \"$userstrat\"..."
            echo ""
            python3 unciv_agent.py --civ "$userciv" --strategy "$userstrat" --map-size "$usermapsize" --map-type "$usermaptype" --difficulty "$userdiff"
            read -p "Press [Enter] to return to menu..."
            ;;
        5)
            clear
            echo "Launching Interactive Browser Replay Viewer..."
            echo ""
            python3 replay_viewer.py
            read -p "Press [Enter] to return to menu..."
            ;;
        6)
            clear
            python3 play_vs_ai.py
            read -p "Press [Enter] to return to menu..."
            ;;
        7)
            clear
            echo "Launching Unciv Desktop GUI (Unciv.jar)..."
            echo ""
            java -jar Unciv.jar &
            echo "Unciv launched in background!"
            sleep 1.5
            ;;
        8)
            clear
            echo "Running Unciv AI diagnostics..."
            echo ""
            python3 run_diagnostics.py
            read -p "Press [Enter] to return to menu..."
            ;;
        0)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid choice. Please choose 0-8."
            sleep 1
            ;;
    esac
done
