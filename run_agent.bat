@echo off
title Unciv AI Launcher
color 0A

:: Ensure script runs in its current directory
cd /d "%~dp0"

:MENU
cls
echo ============================================================
echo               🏛️  UNCIV AI STRATEGIC AGENT  🏛️
echo ============================================================
echo.
echo  [1] Resume Last Game (from autosave.json)
echo  [2] Start New Game - Rome (Science ^& Rapid Expansion)
echo  [3] Start New Game - Rome (Domination ^& Military Focus)
echo  [4] Start New Game - Custom Civ ^& Strategy
echo  [5] Launch Interactive Browser Replay Dashboard
echo  [6] Run Engine Diagnostics
echo  [0] Exit
echo.
echo ============================================================
set /p choice="Select an option (0-6): "

if "%choice%"=="1" goto RESUME
if "%choice%"=="2" goto NEW_SCIENCE
if "%choice%"=="3" goto NEW_MILITARY
if "%choice%"=="4" goto NEW_CUSTOM
if "%choice%"=="5" goto REPLAY
if "%choice%"=="6" goto DIAGNOSTICS
if "%choice%"=="0" goto EXIT
goto MENU

:RESUME
cls
echo Resuming game from autosave.json...
echo.
python unciv_agent.py --load autosave.json
echo.
pause
goto MENU

:NEW_SCIENCE
cls
echo Starting new game as Rome with Science focus...
echo.
python unciv_agent.py --civ Rome --strategy "Focus on science and expand rapidly"
echo.
pause
goto MENU

:NEW_MILITARY
cls
echo Starting new game as Rome with Domination focus...
echo.
python unciv_agent.py --civ Rome --strategy "Build a massive military and conquer our neighbors"
echo.
pause
goto MENU

:NEW_CUSTOM
cls
set /p userciv="Enter Civilization name (default Rome): "
if "%userciv%"=="" set userciv=Rome
set /p userstrat="Enter Strategic Directive (e.g. Focus on culture): "
if "%userstrat%"=="" set userstrat=Balanced Strategy
set /p usermapsize="Enter Map Size (Tiny, Small, Medium, Large, Huge - default Tiny): "
if "%usermapsize%"=="" set usermapsize=Tiny
set /p usermaptype="Enter Map Type (Pangaea, Continents, Archipelago, Lakes - default Pangaea): "
if "%usermaptype%"=="" set usermaptype=Pangaea
set /p userdiff="Enter Difficulty (Settler, Prince, King, Deity - default Prince): "
if "%userdiff%"=="" set userdiff=Prince

echo.
echo Starting game as %userciv% (%usermaptype% %usermapsize%, %userdiff%) with directive: "%userstrat%"...
echo.
python unciv_agent.py --civ "%userciv%" --strategy "%userstrat%" --map-size "%usermapsize%" --map-type "%usermaptype%" --difficulty "%userdiff%"
echo.
pause
goto MENU

:REPLAY
cls
echo Launching Interactive Browser Replay Viewer...
echo.
python replay_viewer.py
echo.
pause
goto MENU

:DIAGNOSTICS
cls
echo Running Unciv AI diagnostics...
echo.
python run_diagnostics.py
echo.
pause
goto MENU

:EXIT
exit /b 0
