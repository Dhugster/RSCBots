"""One-click launcher TUI: select bots, assign scripts, press Play to start all."""
import json
import sys
import time
from pathlib import Path
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.controller import BotController

from ui import theme
from ui.widgets import rs_header, rs_footer, rs_panel

ASSIGNMENTS_FILE = "config/launcher_assignments.json"


@dataclass
class LaunchEntry:
    """Per-bot row in the launcher: selection and script override."""
    bot_id: str
    username: str
    selected: bool
    script_name: str
    script_args: list[str]


def _assignments_path(controller: BotController) -> Path:
    """Path to persisted script assignments (per bot)."""
    return Path(controller.root) / ASSIGNMENTS_FILE


def _load_assignments(controller: BotController) -> dict:
    """Load saved script/args per bot_id. Returns {bot_id: {script_name, script_args}}."""
    path = _assignments_path(controller)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_assignments(controller: BotController, entries: list) -> None:
    """Save current script/args for each bot to launcher_assignments.json."""
    path = _assignments_path(controller)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        e.bot_id: {"script_name": e.script_name, "script_args": e.script_args}
        for e in entries
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _get_key(console: Console) -> str:
    """Read a single key. Windows: msvcrt; elsewhere: prompt. Returns 'up'/'down' for arrows."""
    if sys.platform == "win32":
        try:
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                ch2 = msvcrt.getch()
                if ch2 == b"H":
                    return "up"
                if ch2 == b"P":
                    return "down"
            if isinstance(ch, bytes):
                return ch.decode("utf-8", errors="replace").lower()
            return str(ch).lower()
        except Exception:
            pass
    k = input("Key (then Enter): ").strip().lower()
    if k in ("w", "k"):
        return "up"
    if k in ("s", "j"):
        return "down"
    return k[:1] if k else ""


def run_launcher(controller: BotController) -> None:
    """Run the unified Dashboard (Setup + Live). Backward-compat for 'python bot_manager.py launch'."""
    from ui.dashboard import run_dashboard
    run_dashboard(controller)
