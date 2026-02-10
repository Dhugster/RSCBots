"""Bot instance representation and management."""
from dataclasses import dataclass, field
from subprocess import Popen
from enum import Enum
from collections import deque
from datetime import datetime
from typing import Optional

class BotStatus(Enum):
    """Bot operational status."""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    CRASHED = "crashed"
    STOPPED = "stopped"

class HealthStatus(Enum):
    """Bot health check results."""
    HEALTHY = "healthy"
    CRASHED = "crashed"
    STUCK = "stuck"
    DISCONNECTED = "disconnected"
    ERROR_SPAM = "error_spam"
    UNKNOWN = "unknown"

@dataclass
class BotMetrics:
    """Metrics tracked for each bot."""
    xp_per_hour: float = 0.0
    items_collected: int = 0
    deaths: int = 0
    trades_completed: int = 0
    total_xp_gained: int = 0

    def update_xp_rate(self, runtime_seconds: int) -> None:
        """Calculate XP/hr based on runtime."""
        if runtime_seconds > 0:
            hours = runtime_seconds / 3600
            self.xp_per_hour = self.total_xp_gained / hours if hours > 0 else 0

@dataclass
class BotInstance:
    """Represents a single bot instance."""
    # Identity
    bot_id: str
    account_name: str
    username: str
    password: str

    # Script configuration
    script_name: str
    script_args: list[str]

    # Runtime state
    process: Optional[Popen] = None
    # PID for processes started in a previous CLI invocation; used for cross-process control
    external_pid: Optional[int] = None
    status: BotStatus = BotStatus.IDLE
    start_time: Optional[datetime] = None
    stop_time: Optional[datetime] = None
    runtime_seconds: int = 0

    # Monitoring
    logs: deque = field(default_factory=lambda: deque(maxlen=1000))
    metrics: BotMetrics = field(default_factory=BotMetrics)
    last_health_check: Optional[datetime] = None
    health_status: HealthStatus = HealthStatus.UNKNOWN

    # Recovery tracking
    crash_count: int = 0
    last_crash_time: Optional[datetime] = None
    restart_count: int = 0

    # Configuration
    auto_restart: bool = True
    max_runtime_hours: Optional[float] = None
    health_check_interval: int = 30
    restart_cooldown: int = 60
    max_restart_attempts: int = 3

    @property
    def is_running(self) -> bool:
        """Check if bot is currently running."""
        return (
            self.status == BotStatus.RUNNING
            and self.process is not None
            and self.process.poll() is None
        )

    @property
    def runtime_formatted(self) -> str:
        """Get formatted runtime string."""
        if not self.start_time:
            return "00:00:00"

        if self.is_running:
            runtime = (datetime.now() - self.start_time).total_seconds()
        elif self.stop_time:
            runtime = (self.stop_time - self.start_time).total_seconds()
        else:
            runtime = self.runtime_seconds

        hours = int(runtime // 3600)
        minutes = int((runtime % 3600) // 60)
        seconds = int(runtime % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def update_runtime(self) -> None:
        """Update runtime counter."""
        if self.start_time and self.is_running:
            self.runtime_seconds = int((datetime.now() - self.start_time).total_seconds())
            self.metrics.update_xp_rate(self.runtime_seconds)

    def add_log(self, message: str, source: str = "BOT") -> None:
        """Add a log entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{source}] {message}"
        self.logs.append(log_entry)

    def get_recent_logs(self, count: int = 50) -> list[str]:
        """Get recent log entries."""
        return list(self.logs)[-count:]

    def should_restart(self) -> bool:
        """Determine if bot should be restarted."""
        if not self.auto_restart:
            return False

        if self.restart_count >= self.max_restart_attempts:
            return False

        if self.last_crash_time:
            cooldown_elapsed = (datetime.now() - self.last_crash_time).total_seconds()
            if cooldown_elapsed < self.restart_cooldown:
                return False

        return True

    def record_crash(self) -> None:
        """Record a crash event."""
        self.crash_count += 1
        self.last_crash_time = datetime.now()
        self.status = BotStatus.CRASHED

    def record_restart(self) -> None:
        """Record a restart event."""
        self.restart_count += 1

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "bot_id": self.bot_id,
            "account_name": self.account_name,
            "script_name": self.script_name,
            "script_args": self.script_args,
            "status": self.status.value,
            "runtime": self.runtime_formatted,
            "xp_per_hour": self.metrics.xp_per_hour,
            "items_collected": self.metrics.items_collected,
            "crash_count": self.crash_count,
            "restart_count": self.restart_count,
        }
