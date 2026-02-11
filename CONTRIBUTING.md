# Contributing to IdleRSC Manager

Thanks for your interest in contributing. This project is an unofficial dashboard for [IdleRSC](https://gitlab.com/openrsc/idlersc).

## Running from source

### Requirements

- **Python 3.10+** and **pip**
- **Node.js 18+** and **npm** (for the web dashboard)
- **Java 8** (for IdleRSC client)

### Setup

1. Clone the repo and enter the project directory.
2. Create a virtual environment and install Python dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```
3. Build the web dashboard (TypeScript + Vite):
   ```bash
   cd web
   npm ci
   npm run build   # tsc && vite build
   cd ..
   ```
4. Copy `config/bots.yaml.example` to `config/bots.yaml` and add your own account details (do not commit `bots.yaml`).
5. Set `idlersc_jar_path` in `config/settings.yaml` to your IdleRSC.jar path.
6. Run the Dashboard: `python bot_manager.py` (TUI) or use `run_app.bat` / `run_app.sh` (web).

## Adding a task preset

Edit `config/task_presets.yaml` and add an entry under `task_presets`:

```yaml
- name: "YourPreset"
  script: "ScriptName"
  args: ["arg1", "arg2"]
```

Restart the Dashboard; the new preset will appear in the Setup view and can be applied to selected bots with the number keys (1–9).

## Where config lives

- **config/settings.yaml** – JAR path, Java path, log dir, health/restart options.
- **config/bots.yaml** – Your accounts (id, username, password, script, args). Keep this file out of version control.
- **config/task_presets.yaml** – Named script presets for the Dashboard.
- **config/launcher_assignments.json** – Last-used script/args per bot (optional; created at runtime).

## Reporting issues

Open an issue in the project’s repository (e.g. GitLab/GitHub) with:

- What you did (e.g. “Pressed P to start 2 bots”).
- What you expected.
- What happened (error message or behavior).
- Your environment (OS, Python version, IdleRSC version if relevant).

Do not paste passwords or full contents of `bots.yaml`.
