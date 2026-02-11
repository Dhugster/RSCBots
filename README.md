# IdleRSC Manager

**IdleRSC Dashboard** – A persistent Dashboard for managing multiple [IdleRSC](https://gitlab.com/openrsc/idlersc) (Coleslaw/Uranium) bots: add and edit accounts, assign scripts or presets, start/stop bots, and view logs in one place.

This project is **unofficial and community-made**. It is not part of the official IdleRSC project. Credit to the [IdleRSC team](https://gitlab.com/openrsc/idlersc) for the client and game integration.

---

## Prerequisites

- **Python 3.10+**
- **Java 8** on PATH (for IdleRSC)
- **IdleRSC.jar** – e.g. on Desktop or a path you set in config

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
- Terminal 1: `uvicorn api_server:app --reload --host 127.0.0.1 --port 8000`
- Terminal 2: `cd web && npm run dev` → open http://localhost:5173 (Vite proxies `/api` to the API)

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

## Layout

- **core/** – BotInstance, BotController, HealthMonitor, LogAggregator, RecoverySystem; controller loads/saves `bots.yaml` and task presets.
- **ui/** – Click CLI, unified Dashboard (Setup + Live), theme and widgets.
- **config/** – settings.yaml, bots.yaml (or bots.yaml.example), task_presets.yaml.
- **logs/** – Per-bot log files and bot state (created at runtime).

---

## License

GPL v3 – same as IdleRSC where applicable. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to run from source, add presets, and report issues.
