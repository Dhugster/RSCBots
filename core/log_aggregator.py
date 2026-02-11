"""Log aggregation for bot stdout/stderr."""
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .controller import BotController
    from .bot_instance import BotInstance


class LogAggregator:
    def __init__(self, controller: "BotController") -> None:
        self.controller = controller
        self._log_threads: dict = {}
        self._log_files: dict = {}

    def start_log_capture(self, bot_id: str) -> None:
        """Start capturing stdout/stderr for a bot; append to in-memory logs and optional file."""
        bot = self.controller.get_bot(bot_id)
        # #region agent log
        try:
            import json
            _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
            _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "log_aggregator.py:start_log_capture", "message": "start_log_capture", "data": {"bot_id": bot_id, "has_bot": bot is not None, "has_process": getattr(bot, "process", None) is not None if bot else False}, "hypothesisId": "H3"}) + "\n")
            _f.close()
        except Exception:
            pass
        # #endregion
        if not bot or not bot.process:
            return

        log_dir = Path(self.controller.settings.get("log_directory", "./logs"))
        if not log_dir.is_absolute():
            log_dir = getattr(self.controller, "root", Path.cwd()) / log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{bot_id}.log"
        try:
            log_file = open(log_path, "a", encoding="utf-8", errors="replace")
        except OSError:
            log_file = None
        self._log_files[bot_id] = log_file

        def read_stdout() -> None:
            if not bot.process or not bot.process.stdout:
                return
            try:
                for line in iter(bot.process.stdout.readline, ""):
                    if not line:
                        break
                    line = line.rstrip()
                    bot.add_log(line, "STDOUT")
                    self._parse_log_line(bot, line)
                    if log_file:
                        try:
                            log_file.write(f"[STDOUT] {line}\n")
                            log_file.flush()
                        except OSError:
                            pass
            except (ValueError, OSError):
                pass
            finally:
                if log_file:
                    try:
                        log_file.close()
                    except OSError:
                        pass

        def read_stderr() -> None:
            if not bot.process or not bot.process.stderr:
                return
            try:
                for line in iter(bot.process.stderr.readline, ""):
                    if not line:
                        break
                    line = line.rstrip()
                    bot.add_log(line, "STDERR")
                    if log_file:
                        try:
                            log_file.write(f"[STDERR] {line}\n")
                            log_file.flush()
                        except OSError:
                            pass
            except (ValueError, OSError):
                pass

        t_out = threading.Thread(target=read_stdout, daemon=True)
        t_err = threading.Thread(target=read_stderr, daemon=True)
        t_out.start()
        t_err.start()
        self._log_threads[bot_id] = (t_out, t_err)

    def _parse_log_line(self, bot: "BotInstance", line: str) -> None:
        """Parse log line for metrics (XP, items, profit). Updates BotMetrics."""
        line_lower = line.lower()
        xp_updated = False
        # XP: "gained N xp", "+N xp", "N xp", "gained N experience", "N experience", "experience gained"
        if "xp" in line_lower or "experience" in line_lower:
            if "gained" in line_lower or "+" in line or "experience" in line_lower:
                m = re.search(
                    r"(\d+)\s*(?:xp|experience)|(?:xp|experience)[:\s]*(\d+)|gained\s+(\d+)|[\+](\d+)\s*(?:xp|experience)?",
                    line_lower,
                    re.I,
                )
                if m:
                    n = int(next((g for g in m.groups() if g), "0"))
                    if n > 0:
                        bot.metrics.total_xp_gained += n
                        xp_updated = True
        if xp_updated and bot.start_time and bot.is_running:
            rt = int((datetime.now() - bot.start_time).total_seconds())
            bot.metrics.update_xp_rate(rt)
        # Items: "collected", "picked up", "loot"
        if any(k in line_lower for k in ("collected", "picked up", "loot")):
            bot.metrics.items_collected += 1
        # Profit: "coins", "gold", "gp", "profit" with a number
        if any(k in line_lower for k in ("coins", "gold", "gp", "profit")):
            m = re.search(
                r"(\d[\d,]*)\s*(?:gp|gold|coins?)|(?:gp|gold|coins?|profit)[:\s]*(\d[\d,]*)",
                line_lower,
            )
            if m:
                raw = (m.group(1) or m.group(2) or "0").replace(",", "")
                try:
                    n = int(raw)
                    if n > 0:
                        bot.metrics.profit += n
                except ValueError:
                    pass

    def get_aggregated_logs(self, filters: Optional[dict] = None) -> list[str]:
        """Get logs from all bots, optionally filtered by bot_id."""
        result = []
        for bid, bot in self.controller.bots.items():
            if filters and filters.get("bot_id") and filters["bot_id"] != bid:
                continue
            for log in bot.get_recent_logs(filters.get("tail", 100) if filters else 100):
                result.append(f"[{bid}] {log}")
        return result
