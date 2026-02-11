# IdleRSC Manager

**IdleRSC Dashboard** – A persistent Dashboard for managing multiple [IdleRSC](https://gitlab.com/openrsc/idlersc) (Coleslaw/Uranium) bots: add and edit accounts, assign scripts or presets, start/stop bots, and view logs in one place.

**Open source** – Anyone can download, use, modify, and redistribute this software. Licensed under [GPL v3](LICENSE); see [LICENSE](LICENSE) for full terms.

This project is **unofficial and community-made**. It is not part of the official IdleRSC project. Credit to the [IdleRSC team](https://gitlab.com/openrsc/idlersc) for the client and game integration.

---

## Prerequisites

- **Python 3.10+**
- **Java 8** on PATH (for IdleRSC)
- **IdleRSC.jar** – e.g. on Desktop or a path you set in config
- **Node.js 18+** (for building the web dashboard; build uses `tsc` and Vite)

For Coleslaw: run `java -jar IdleRSC.jar --init-cache coleslaw` once before using the manager.

---

## Install

```bash
cd idlersc_manager
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

To build the web dashboard (required for the standalone web app):

```bash
cd web
npm ci
npm run build   # runs tsc && vite build
cd ..
```

---

## Configuration

- **config/settings.yaml** – `idlersc_jar_path` (e.g. `C:/Users/You/Desktop/IdleRSC.jar`), `java_path`, and optional log/health settings.
- **config/bots.yaml** – Your bot accounts (id, account, username, password, script, args). Copy from `config/bots.yaml.example` and fill in your own credentials. **Do not commit this file** (it holds passwords).
- **config/task_presets.yaml** – Named presets (e.g. Fishing, Mining) for quick script assignment in the Dashboard.

---

## Usage

### Web app (standalone, with graphics)

One command builds the web UI and starts the API; open the URL in your browser:

**Windows:** `run_app.bat`  
**Linux/macOS:** `./run_app.sh` (or `bash run_app.sh`)

Then open **http://127.0.0.1:8000** (the script may open it for you). You get a graphical dashboard: bot cards (start/stop, delete), presets, logs, and an “Add account” form.

**Dev mode (API + frontend separate):**
- Terminal 1: `python -m uvicorn api_server:app --reload --host 127.0.0.1 --port 8000`
- Terminal 2: `cd web && npm run dev` → open http://localhost:5173 (Vite proxies `/api` to the API)

**Note:** Always use `python -m uvicorn` (not `uvicorn` alone) so the correct Python and its packages are used. If you use a venv, activate it first in that terminal (e.g. `.venv\Scripts\activate` on Windows).

### Map: live bot positions (world map game layers)

The Map tab can show live bot icons on the **world map game layers** (Surface / 1st / 2nd / Dungeon). The map overlay uses the same coordinate space as `@2003scape/rsc-world-map`:

- **Coordinates**: `tile_x`, `tile_y` are **map pixel** coordinates in **0..2448** (X) and **0..2736** (Y).
- **Layer**: `layer` is one of `surface`, `floor1`, `floor2`, `dungeon`.
- **Game coords**: To send the client’s displayed coords (e.g. "Coords: 161 607"), use `"coordinate_system": "game_tile"`; the API converts to map pixels using the same convention as the rsc-world-map overlay.

To feed live positions from a script/client, POST to:

- `POST /api/bots/{bot_id}/position` with JSON body:
  - Map pixels: `{"tile_x":1234,"tile_y":567,"layer":"surface"}`
  - Game tiles (e.g. from client): `{"tile_x":161,"tile_y":607,"layer":"surface","coordinate_system":"game_tile"}`

---

### Terminal TUI

Run with no arguments to open the terminal Dashboard:

```bash
python bot_manager.py
```

In the Dashboard:

- **Setup view** – Add/edit/delete accounts, toggle selection, apply task presets, press **[P]** to start selected bots, **[L]** to switch to Live view.
- **Live view** – Bot status table and log panel; **[S]** back to Setup, **[Q]** Quit.

The Dashboard stays open while IdleRSC JAR clients run in separate windows.

**CLI subcommands** (for scripting and power users):

```bash
python bot_manager.py status
python bot_manager.py start-all
python bot_manager.py start <bot_id>
python bot_manager.py stop <bot_id>
python bot_manager.py stop-all
python bot_manager.py restart <bot_id>
python bot_manager.py logs --bot <bot_id> --tail 50
python bot_manager.py dashboard    # same as running with no args
python bot_manager.py launch       # same as dashboard (unified flow)
python bot_manager.py recover
```

Add a bot via CLI:

```bash
python bot_manager.py add-bot --account myacc --username user --password pass --script MiningBot --args iron,al_kharid --auto-start
```

---

## Troubleshooting

### "Uvicorn is not recognized" or "No module named 'uvicorn'"

This usually means the terminal is using a different Python than the one where you installed dependencies (e.g. system Python instead of your project venv after a restart).

- **Use the run script:** `run_app.bat` (Windows) or `./run_app.sh` (Linux/macOS) automatically use `.venv` if it exists, so running it from the project root should work.
- **If you start the server yourself:** Activate the venv in that terminal first, then run:
  ```bash
  .venv\Scripts\activate   # Windows
  # source .venv/bin/activate   # Linux/macOS
  python -m uvicorn api_server:app --host 127.0.0.1 --port 8000
  ```
- **Or install deps into the Python you're using:** `pip install -r requirements.txt`, then `python -m uvicorn api_server:app --host 127.0.0.1 --port 8000`.

---

## Layout

- **core/** – BotInstance, BotController, HealthMonitor, LogAggregator, RecoverySystem; controller loads/saves `bots.yaml` and task presets.
- **ui/** – Click CLI, unified Dashboard (Setup + Live), theme and widgets.
- **config/** – settings.yaml, bots.yaml (or bots.yaml.example), task_presets.yaml.
- **logs/** – Per-bot log files and bot state (created at runtime).

---

## License

This project is free and open source. You may download, use, modify, and redistribute it under the terms of the **GNU General Public License v3**. See [LICENSE](LICENSE) for the full text. No permission or payment is required to use this software.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to run from source, add presets, and report issues.
