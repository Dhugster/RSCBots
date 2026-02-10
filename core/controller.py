"""Main bot controller - manages multiple bot instances."""
import os
import subprocess
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import psutil

from .bot_instance import BotInstance, BotStatus
from .health_monitor import HealthMonitor
from .log_aggregator import LogAggregator
from .recovery import RecoverySystem


class BotController:
    """Central controller for managing multiple IdleRSC bot instances."""

    def __init__(self, config_path: str = "config/bots.yaml") -> None:
        self.config_path = Path(config_path).resolve()
        self.root = self.config_path.parent.parent
        self.state_path = self.root / "logs" / "bot_state.json"
        self.config = self._load_config()
        self.settings = self._load_settings()

        self.bots: Dict[str, BotInstance] = {}
        self.health_monitor = HealthMonitor(self)
        self.log_aggregator = LogAggregator(self)
        self.recovery_system = RecoverySystem(self)

        self._load_bots_from_config()
        # #region agent log
        try:
            import json
            _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
            _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "controller.py:BotController.__init__", "message": "init", "data": {"config_path": str(self.config_path), "root": str(self.root), "bots_count": len(self.bots), "config_has_bots": len(self.config.get("bots", []))}, "hypothesisId": "H1"}) + "\n")
            _f.close()
        except Exception:
            pass
        # #endregion

        # Load any persisted PID state for cross-process control
        for bot_id, pid in self._load_pid_state().items():
            bot = self.bots.get(bot_id)
            if not bot:
                continue
            # Only keep PID if process is still alive
            try:
                p = psutil.Process(pid)
                if p.is_running():
                    bot.external_pid = pid
            except Exception:
                continue

    def _load_config(self) -> dict:
        """Load bot configurations from YAML."""
        if not self.config_path.exists():
            return {"bots": []}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"bots": []}

    def _load_settings(self) -> dict:
        """Load system settings."""
        settings_path = self.config_path.parent / "settings.yaml"
        if not settings_path.exists():
            return self._get_default_settings()
        with open(settings_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or self._get_default_settings()

    def _get_default_settings(self) -> dict:
        """Default system settings."""
        return {
            "idlersc_jar_path": "./IdleRSC.jar",
            "java_path": "java",
            "log_directory": "./logs",
            "health_check_interval": 30,
            "restart_cooldown": 60,
            "max_restart_attempts": 3,
            "enable_graphics": False,
            "show_side_panel": False,
        }

    def get_task_presets(self) -> List[dict]:
        """Load task presets from config/task_presets.yaml. Returns list of {name, script, args}."""
        path = self.config_path.parent / "task_presets.yaml"
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            presets = data.get("task_presets", [])
            return [
                {"name": p.get("name", ""), "script": p.get("script", ""), "args": p.get("args", [])}
                for p in presets
            ]
        except Exception:
            return []

    def _load_bots_from_config(self) -> None:
        """Load all bots from configuration file."""
        for bot_config in self.config.get("bots", []):
            bot = self._create_bot_from_config(bot_config)
            self.bots[bot.bot_id] = bot

    def _create_bot_from_config(self, config: dict) -> BotInstance:
        """Create a BotInstance from configuration."""
        return BotInstance(
            bot_id=config["id"],
            account_name=config["account"],
            username=config["username"],
            password=config["password"],
            script_name=config.get("script") or "",
            script_args=config.get("args", []),
            auto_restart=config.get("auto_restart", True),
            max_runtime_hours=config.get("max_runtime"),
            health_check_interval=config.get("health_check_interval", 30),
        )

    def _load_pid_state(self) -> Dict[str, int]:
        """Load persisted bot PID state from disk."""
        if not self.state_path.exists():
            return {}
        try:
            import json

            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            # Expect mapping bot_id -> pid (int)
            return {k: int(v) for k, v in data.items()}
        except Exception:
            return {}

    def _save_pid_state(self, state: Dict[str, int]) -> None:
        """Persist bot PID state to disk."""
        try:
            import json

            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception:
            pass

    def add_bot(self, bot_config: dict) -> BotInstance:
        """Add a new bot to the controller."""
        bot = self._create_bot_from_config(bot_config)
        self.bots[bot.bot_id] = bot
        return bot

    def remove_bot(self, bot_id: str) -> bool:
        """Remove a bot from the controller (e.g. for UI delete). Returns True if removed."""
        if bot_id not in self.bots:
            return False
        if self.bots[bot_id].is_running:
            self.stop_bot(bot_id)
        del self.bots[bot_id]
        return True

    def save_bots_to_config(self) -> None:
        """Persist current controller.bots to config file (bots.yaml)."""
        bots_list = []
        for bot in self.bots.values():
            bots_list.append({
                "id": bot.bot_id,
                "account": bot.account_name,
                "username": bot.username,
                "password": bot.password,
                "script": bot.script_name,
                "args": bot.script_args,
                "auto_restart": bot.auto_restart,
                "max_runtime": bot.max_runtime_hours,
                "health_check_interval": bot.health_check_interval,
            })
        self.config["bots"] = bots_list
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)

    def get_bot(self, bot_id: str) -> Optional[BotInstance]:
        """Get a bot by ID."""
        return self.bots.get(bot_id)

    def _build_java_command(self, bot: BotInstance) -> List[str]:
        """Build the java -jar IdleRSC.jar command."""
        jar_path = Path(self.settings["idlersc_jar_path"])
        if not jar_path.is_absolute():
            jar_path = self.root / jar_path
        cmd = [
            self.settings["java_path"],
            "-jar",
            str(jar_path.resolve()),
            "--auto-start",
            "--auto-login",
            "--username",
            bot.username,
            "--password",
            bot.password,
            "--script-name",
            bot.script_name,
        ]
        if bot.script_args:
            cmd.extend(["--script-arguments", ",".join(bot.script_args)])
        if not self.settings.get("enable_graphics", False):
            cmd.append("--disable-gfx")
        if not self.settings.get("show_side_panel", False):
            cmd.append("--hide-side-panel")
        return cmd

    def start_bot(self, bot_id: str) -> bool:
        """Start a specific bot."""
        bot = self.get_bot(bot_id)
        if not bot:
            raise ValueError(f"Bot not found: {bot_id}")

        if bot.is_running:
            bot.add_log("Already running", "CONTROLLER")
            return False

        cmd = self._build_java_command(bot)
        log_dir = Path(self.settings["log_directory"])
        if not log_dir.is_absolute():
            log_dir = self.root / log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        # #region agent log
        try:
            import json
            _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
            _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "controller.py:start_bot.entry", "message": "start_bot", "data": {"bot_id": bot_id, "cmd_len": len(cmd)}, "hypothesisId": "H2"}) + "\n")
            _f.close()
        except Exception:
            pass
        # #endregion
        try:
            bot.add_log(f"Starting: {' '.join(cmd)}", "CONTROLLER")
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

            bot.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                cwd=str(self.root),
            )

            bot.status = BotStatus.RUNNING
            bot.start_time = datetime.now()
            bot.stop_time = None
            bot.add_log("Started successfully", "CONTROLLER")

            self.log_aggregator.start_log_capture(bot_id)

            if not self.health_monitor.running:
                self.health_monitor.start_monitoring()

            # Persist PID for cross-process control
            state = self._load_pid_state()
            if getattr(bot.process, "pid", None) is not None:
                state[bot_id] = int(bot.process.pid)
                self._save_pid_state(state)

            # #region agent log
            try:
                import json
                _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
                _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "controller.py:start_bot.success", "message": "start_bot ok", "data": {"bot_id": bot_id, "pid": getattr(bot.process, "pid", None)}, "hypothesisId": "H2"}) + "\n")
                _f.close()
            except Exception:
                pass
            # #endregion
            return True
        except Exception as e:
            # #region agent log
            try:
                import json
                _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
                _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "controller.py:start_bot.except", "message": "start_bot failed", "data": {"bot_id": bot_id, "error_type": type(e).__name__, "error_str": str(e)[:200]}, "hypothesisId": "H2"}) + "\n")
                _f.close()
            except Exception:
                pass
            # #endregion
            bot.add_log(f"Failed to start: {e}", "CONTROLLER")
            bot.status = BotStatus.ERROR
            return False

    def stop_bot(self, bot_id: str, graceful: bool = True) -> bool:
        """Stop a specific bot."""
        bot = self.get_bot(bot_id)
        if not bot:
            raise ValueError(f"Bot not found: {bot_id}")

        if not bot.is_running:
            # If we have an external PID from a previous invocation, attempt to stop that process.
            external_pid = getattr(bot, "external_pid", None)
            if external_pid:
                try:
                    p = psutil.Process(external_pid)
                    p.terminate()
                    try:
                        p.wait(timeout=10)
                    except Exception:
                        p.kill()
                    bot.stop_time = datetime.now()
                    bot.status = BotStatus.STOPPED
                    bot.external_pid = None
                    # Remove from persisted state
                    state = self._load_pid_state()
                    if bot_id in state:
                        state.pop(bot_id, None)
                        self._save_pid_state(state)
                    # #region agent log
                    try:
                        import json
                        _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
                        _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "controller.py:stop_bot.external_pid", "message": "stop_bot external kill", "data": {"bot_id": bot_id, "external_pid": external_pid}, "hypothesisId": "H2"}) + "\n")
                        _f.close()
                    except Exception:
                        pass
                    # #endregion
                    bot.add_log("Stopped external process", "CONTROLLER")
                    return True
                except Exception:
                    # fall back to prior behavior / log not running
                    pass

            # #region agent log
            try:
                import json
                _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
                _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "controller.py:stop_bot.not_running", "message": "stop_bot skip", "data": {"bot_id": bot_id, "status": str(bot.status)}, "hypothesisId": "H2"}) + "\n")
                _f.close()
            except Exception:
                pass
            # #endregion
            bot.add_log("Not running", "CONTROLLER")
            return False

        try:
            if graceful:
                bot.add_log("Stopping gracefully...", "CONTROLLER")
                bot.process.terminate()
                try:
                    bot.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    bot.add_log("Graceful shutdown timeout, forcing...", "CONTROLLER")
                    bot.process.kill()
            else:
                bot.add_log("Force stopping...", "CONTROLLER")
                bot.process.kill()

            bot.stop_time = datetime.now()
            bot.update_runtime()
            bot.status = BotStatus.STOPPED
            bot.process = None
            # Clear any persisted PID
            state = self._load_pid_state()
            if bot_id in state:
                state.pop(bot_id, None)
                self._save_pid_state(state)
            bot.add_log("Stopped", "CONTROLLER")
            return True
        except Exception as e:
            # #region agent log
            try:
                import json
                _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
                _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "controller.py:stop_bot.except", "message": "stop_bot failed", "data": {"bot_id": bot_id, "error_type": type(e).__name__, "error_str": str(e)[:200]}, "hypothesisId": "H2"}) + "\n")
                _f.close()
            except Exception:
                pass
            # #endregion
            bot.add_log(f"Error stopping: {e}", "CONTROLLER")
            return False

    def restart_bot(self, bot_id: str) -> bool:
        """Restart a bot."""
        bot = self.get_bot(bot_id)
        if not bot:
            raise ValueError(f"Bot not found: {bot_id}")

        bot.add_log("Restarting...", "CONTROLLER")
        if bot.is_running:
            self.stop_bot(bot_id)
            time.sleep(2)
        bot.record_restart()
        return self.start_bot(bot_id)

    def start_all(self) -> int:
        """Start all bots."""
        started = 0
        for bid in list(self.bots):
            if self.start_bot(bid):
                started += 1
                time.sleep(1)
        return started

    def stop_all(self) -> int:
        """Stop all bots."""
        stopped = 0
        for bid in list(self.bots):
            if self.stop_bot(bid):
                stopped += 1
        self.health_monitor.stop_monitoring()
        return stopped

    def swarm_mode(
        self, script: str, args_variations: List[List[str]], count: int
    ) -> None:
        """Start N bots all running same script with different args."""
        for i in range(count):
            bot_id = f"swarm_{script}_{i}_{int(time.time())}"
            args = args_variations[i % len(args_variations)]
            bot_config = {
                "id": bot_id,
                "account": f"swarm_{i}",
                "username": f"swarm_user_{i}",
                "password": "temp_pass",
                "script": script,
                "args": args,
                "auto_restart": True,
            }
            self.add_bot(bot_config)
            self.start_bot(bot_id)
            time.sleep(1)

    def coordinate_mode(self, tasks: List[dict]) -> None:
        """Start bots with coordinated tasks."""
        for task in tasks:
            bot_id = task["bot"]
            bot = self.get_bot(bot_id)
            if not bot:
                bot_config = {
                    "id": bot_id,
                    "account": bot_id,
                    "username": task.get("username", bot_id),
                    "password": task.get("password", "temp"),
                    "script": task["script"],
                    "args": task.get("args", []),
                }
                self.add_bot(bot_config)
            self.start_bot(bot_id)
            time.sleep(1)

    def get_status_summary(self) -> dict:
        """Get summary of all bots."""
        return {
            "total": len(self.bots),
            "running": sum(1 for b in self.bots.values() if b.is_running),
            "stopped": sum(
                1 for b in self.bots.values() if b.status == BotStatus.STOPPED
            ),
            "crashed": sum(
                1 for b in self.bots.values() if b.status == BotStatus.CRASHED
            ),
            "error": sum(1 for b in self.bots.values() if b.status == BotStatus.ERROR),
        }
