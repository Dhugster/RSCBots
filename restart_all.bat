@echo off
cd /d "%~dp0"
echo Stopping all bots...
curl -s -X POST http://127.0.0.1:8000/api/stop-all 2>nul
if errorlevel 1 (
  echo Server may not be running. If it is, stop it with Ctrl+C then run run_app.bat
) else (
  echo All bots stopped. Stop the server (Ctrl+C in the server window), then run run_app.bat again.
)
