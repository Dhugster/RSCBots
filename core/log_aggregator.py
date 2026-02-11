"""Log aggregation for bot stdout/stderr."""
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .controller import BotController
    from .bot_instance import BotInstance

from .map_coords import MAP_W, MAP_H, game_tile_to_map_pixel


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
        # XP: accept any line that looks like an XP amount (broad patterns, first match only to avoid double-count)
        _xp_patterns = [
            r"(\d+)\s*(?:xp|experience)(?:\s*(?:gained|received|points?))?\b",
            r"(?:xp|experience)[:\s]*(\d+)",
            r"(?:gained|received|get|\+)\s*(\d+)(?:\s*(?:xp|experience))?",
            r"\b(\d+)\s*(?:xp|experience)\b",
        ]
        for pat in _xp_patterns:
            m = re.search(pat, line_lower, re.I)
            if m:
                n = int(m.group(1))
                if n > 0:
                    bot.metrics.total_xp_gained += n
                    xp_updated = True
                break
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

        # Position for map: parse client "Coords: 161 607" format (game tiles) and convert to map pixels
        # Also supports: "position: 1234, 5678", "at 1234 5678", "tile 1234 5678", "x:1234 y:5678"
        is_game_tile_format = False
        m = None
        
        # First, check for client "Coords: X Y" or "Coords: X, Y" format (game tiles) - primary format from RSC client
        coord_match = re.search(r"coords?\s*:\s*(\d{1,4})\s*[,]?\s*(\d{1,4})", line_lower, re.I)
        if coord_match:
            m = coord_match
            is_game_tile_format = True
        
        # Fallback to other position formats (assume map pixels or legacy formats)
        if not m and any(k in line_lower for k in ("position", "tile", "location", " at ")):
            m = re.search(
                r"(?:position|tile|location|at)[:\s]*[\(\[]?\s*(\d{2,5})\s*[,)\]\s]+\s*(\d{2,5})",
                line_lower,
                re.I,
            )
            if not m:
                m = re.search(r"[xX][:\s]*(\d{2,5})\s*[yY][:\s]*(\d{2,5})", line_lower)
        
        if m:
            try:
                x, y = int(m.group(1)), int(m.group(2))
                layer = "surface"
                if "dungeon" in line_lower or "underground" in line_lower:
                    layer = "dungeon"
                elif "floor" in line_lower or "upstairs" in line_lower:
                    layer = "floor2" if ("2" in line or "second" in line_lower) else "floor1"
                
                # Coords may be game tiles (e.g. 161, 607) or map pixels (0..2448, 0..2736).
                # Game tile range: x in 0..816, y in 0..912 (map size/3). If larger, client sent map pixels.
                if is_game_tile_format:
                    if x > MAP_W // 3 or y > MAP_H // 3:
                        # Already map pixels; clamp only
                        x = max(0, min(MAP_W - 1, x))
                        y = max(0, min(MAP_H - 1, y))
                    else:
                        map_x, map_y = game_tile_to_map_pixel(x, y, layer)
                        x, y = map_x, map_y
                
                # #region agent log
                try:
                    import time
                    _path = __import__("pathlib").Path(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log")
                    _path.parent.mkdir(parents=True, exist_ok=True)
                    with open(_path, "a", encoding="utf-8") as _f:
                        _f.write(__import__("json").dumps({"location": "log_aggregator:notify_position", "message": "position from log line", "data": {"bot_id": bot.bot_id, "x": x, "y": y, "layer": layer, "was_game_tile": is_game_tile_format}, "hypothesisId": "H4", "timestamp": time.time() * 1000}) + "\n")
                except Exception:
                    pass
                # #endregion
                self.controller.notify_position(bot.bot_id, x, y, layer)
            except (ValueError, IndexError):
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
