#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "Building web app..."
(cd web && npm run build)
echo "Starting API server at http://127.0.0.1:8000"
echo "Open that URL in your browser."
open "http://127.0.0.1:8000" 2>/dev/null || xdg-open "http://127.0.0.1:8000" 2>/dev/null || true
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000
