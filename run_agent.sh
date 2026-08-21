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
    echo " [6] Run Engine Diagnostics"
    echo " [0] Exit"
    echo ""
    echo "============================================================"
    read -p "Select an option (0-6): " choice

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

            echo ""
            echo "Starting game as $userciv with directive: \"$userstrat\"..."
            echo ""
            python3 unciv_agent.py --civ "$userciv" --strategy "$userstrat"
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
            echo "Invalid choice. Please choose 0-6."
            sleep 1
            ;;
    esac
done
