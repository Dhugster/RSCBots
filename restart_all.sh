#!/bin/sh
cd "$(dirname "$0")"
echo "Stopping all bots..."
curl -s -X POST http://127.0.0.1:8000/api/stop-all || true
echo ""
echo "All bots stopped. Stop the server (Ctrl+C), then run ./run_app.sh again."
