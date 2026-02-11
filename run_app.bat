@echo off
cd /d "%~dp0"

REM Use venv Python if present so "uvicorn not found" does not happen after restart
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo Building web app...
cd web && call npm run build && cd ..
if errorlevel 1 exit /b 1

echo Starting API server at http://127.0.0.1:8000
echo Open that URL in your browser.
start http://127.0.0.1:8000

%PY% -m uvicorn api_server:app --host 127.0.0.1 --port 8000
if errorlevel 1 (
  echo.
  echo --- Uvicorn not found ---
  echo If you see "uvicorn is not recognized" or "No module named uvicorn",
  echo your terminal may be using a different Python than where you installed deps.
  echo.
  echo Fix: activate the project venv, then run this script again:
  echo   .venv\Scripts\activate
  echo   run_app.bat
  echo.
  echo Or install deps for the Python you are using:
  echo   pip install -r requirements.txt
  echo   run_app.bat
  echo.
  exit /b 1
)
