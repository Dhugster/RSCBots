"""Main bot controller - manages multiple bot instances."""
import os
import subprocess
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .bot_instance import BotInstance, BotStatus
from .health_monitor import HealthMonitor
from .log_aggregator import LogAggregator
from .recovery import RecoverySystem


class BotController:
    """Central controller for managing multiple IdleRSC bot instances."""

    def __init__(self, config_path: str = "config/bots.yaml") -> None:
        self.config_path = Path(config_path).resolve()
        self.root = self.config_path.parent.parent
        self.config = self._load_config()
        self.settings = self._load_settings()

        self.bots: Dict[str, BotInstance] = {}
        self.health_monitor = HealthMonitor(self)
        self.log_aggregator = LogAggregator(self)
        self.recovery_system = RecoverySystem(self)

        self._load_bots_from_config()

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
            script_name=config["script"],
            script_args=config.get("args", []),
            auto_restart=config.get("auto_restart", True),
            max_runtime_hours=config.get("max_runtime"),
            health_check_interval=config.get("health_check_interval", 30),
        )

    def add_bot(self, bot_config: dict) -> BotInstance:
        """Add a new bot to the controller."""
        bot = self._create_bot_from_config(bot_config)
        self.bots[bot.bot_id] = bot
        return bot

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

            return True
        except Exception as e:
            bot.add_log(f"Failed to start: {e}", "CONTROLLER")
            bot.status = BotStatus.ERROR
            return False

    def stop_bot(self, bot_id: str, graceful: bool = True) -> bool:
        """Stop a specific bot."""
        bot = self.get_bot(bot_id)
        if not bot:
            raise ValueError(f"Bot not found: {bot_id}")

        if not bot.is_running:
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
            bot.add_log("Stopped", "CONTROLLER")
            return True
        except Exception as e:
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
