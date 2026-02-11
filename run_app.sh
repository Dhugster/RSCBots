#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Use venv Python if present so "uvicorn not found" does not happen after restart
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python"
fi

echo "Building web app..."
(cd web && npm run build)
echo "Starting API server at http://127.0.0.1:8000"
echo "Open that URL in your browser."
open "http://127.0.0.1:8000" 2>/dev/null || xdg-open "http://127.0.0.1:8000" 2>/dev/null || true

if ! "$PY" -m uvicorn api_server:app --host 127.0.0.1 --port 8000; then
  echo ""
  echo "--- Uvicorn not found ---"
  echo "If you see 'No module named uvicorn', your shell may be using a different Python."
  echo ""
  echo "Fix: activate the project venv, then run this script again:"
  echo "  source .venv/bin/activate"
  echo "  ./run_app.sh"
  echo ""
  echo "Or install deps for the Python you are using:"
  echo "  pip install -r requirements.txt"
  echo "  ./run_app.sh"
  echo ""
  exit 1
fi
