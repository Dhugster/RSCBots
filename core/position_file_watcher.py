"""Optional position file watcher: read a JSON file periodically and push bot positions to the controller."""
import json
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .controller import BotController

from .map_coords import game_tile_to_map_pixel


def _run_watcher(controller: "BotController", file_path: Path, interval_seconds: float) -> None:
    """Loop: read file, parse JSON, convert game tiles to map pixels, notify_position. Coords in file are game tiles."""
    while True:
        time.sleep(interval_seconds)
        if not getattr(controller, "_position_file_watcher_running", True):
            break
        if not file_path.exists():
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        for bot_id, entry in data.items():
            if not isinstance(entry, dict):
                continue
            try:
                tile_x = int(entry.get("tile_x", entry.get("x", 0)))
                tile_y = int(entry.get("tile_y", entry.get("y", 0)))
                layer = str(entry.get("layer", "surface")).lower()
                if layer not in ("surface", "floor1", "floor2", "dungeon"):
                    layer = "surface"
            except (TypeError, ValueError):
                continue
            map_x, map_y = game_tile_to_map_pixel(tile_x, tile_y, layer)
            controller.notify_position(bot_id, map_x, map_y, layer)


def start_position_file_watcher(
    controller: "BotController",
    file_path: str | Path | None,
    interval_seconds: float = 2.5,
) -> None:
    """If file_path is set and valid, start a daemon thread that periodically reads the file and updates positions."""
    if not file_path:
        return
    path = Path(file_path)
    if not path.is_absolute():
        path = getattr(controller, "root", Path.cwd()) / path
    path = path.resolve()
    controller._position_file_watcher_running = True
    thread = threading.Thread(
        target=_run_watcher,
        args=(controller, path, interval_seconds),
        daemon=True,
        name="position_file_watcher",
    )
    thread.start()
