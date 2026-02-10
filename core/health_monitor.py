"""Health monitoring for bot processes."""
import time
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from .bot_instance import BotInstance, BotStatus, HealthStatus

if TYPE_CHECKING:
    from .controller import BotController


class HealthMonitor:
    def __init__(self, controller: "BotController") -> None:
        self.controller = controller
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def start_monitoring(self) -> None:
        """Start background health check thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop_monitoring(self) -> None:
        """Stop the health check thread."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _monitor_loop(self) -> None:
        """Run health checks periodically."""
        interval = self.controller.settings.get("health_check_interval", 30)
        while self.running:
            for bot_id, bot in list(self.controller.bots.items()):
                if bot.status == BotStatus.RUNNING:
                    health = self.check_bot_health(bot)
                    bot.health_status = health
                    bot.last_health_check = datetime.now()
                    if health == HealthStatus.CRASHED:
                        self.controller.recovery_system.handle_crash(bot)
                    elif health == HealthStatus.STUCK:
                        self.controller.recovery_system.handle_stuck(bot)
                    elif health == HealthStatus.DISCONNECTED:
                        self.controller.recovery_system.handle_crash(bot)
                    elif health == HealthStatus.ERROR_SPAM:
                        self.controller.recovery_system.handle_crash(bot)
            time.sleep(interval)

    def check_bot_health(self, bot: BotInstance) -> HealthStatus:
        """Check if bot is healthy."""
        if not bot.process:
            return HealthStatus.CRASHED
        if bot.process.poll() is not None:
            return HealthStatus.CRASHED

        recent = bot.get_recent_logs(50)
        error_count = sum(1 for log in recent if "ERROR" in log)
        if error_count > 10:
            return HealthStatus.ERROR_SPAM
        if any("disconnect" in log.lower() for log in recent):
            return HealthStatus.DISCONNECTED

        if bot.start_time:
            elapsed = (datetime.now() - bot.start_time).total_seconds()
            if elapsed > 300 and bot.metrics.xp_per_hour == 0 and bot.metrics.total_xp_gained == 0:
                return HealthStatus.STUCK

        return HealthStatus.HEALTHY
