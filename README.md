# IdleRSC Bot Management System

Python CLI/TUI for managing multiple IdleRSC (OpenRSC Coleslaw) bot instances: start/stop, health monitoring, log aggregation, and auto-recovery.

## Prerequisites

- **Python 3.10+**
- **Java 8** on PATH (for IdleRSC)
- **IdleRSC.jar** (path set in `config/settings.yaml`)
- For Coleslaw: run `java -jar IdleRSC.jar --init-cache coleslaw` once

## Install

```bash
cd idlersc_manager
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Configuration

- **config/settings.yaml** – Set `idlersc_jar_path` and `java_path` (and optionally `log_directory`, health/restart settings).
- **config/bots.yaml** – Define bots (id, account, username, password, script, args). Use your own credentials.

## Usage

Run from the project root (`idlersc_manager`):

```bash
python bot_manager.py status
python bot_manager.py start-all
python bot_manager.py start <bot_id>
python bot_manager.py stop <bot_id>
python bot_manager.py stop-all
python bot_manager.py restart <bot_id>
python bot_manager.py logs --bot <bot_id> --tail 50
python bot_manager.py dashboard
python bot_manager.py recover
```

Add a bot and optionally start it:

```bash
python bot_manager.py add-bot --account myacc --username user --password pass --script MiningBot --args iron,al_kharid --auto-start
```

Swarm mode (multiple bots, same script):

```bash
python bot_manager.py swarm --script FishingBot --args lobster,karamja --count 5
```

## Layout

- `core/` – BotInstance, BotController, HealthMonitor, LogAggregator, RecoverySystem
- `ui/` – Click CLI, Rich TUI dashboard
- `config/` – bots.yaml, settings.yaml
- `logs/` – Per-bot log files (created at runtime)
