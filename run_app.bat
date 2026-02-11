@echo off
cd /d "%~dp0"
echo Building web app...
cd web && call npm run build && cd ..
if errorlevel 1 exit /b 1
echo Starting API server at http://127.0.0.1:8000
echo Open that URL in your browser.
start http://127.0.0.1:8000
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000
