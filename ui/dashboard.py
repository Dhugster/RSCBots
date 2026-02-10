"""Unified Dashboard: one TUI with Setup view (accounts + tasks) and Live view (bots + logs)."""
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.table import Table
from rich.text import Text

from core.controller import BotController

from ui import theme
from ui.widgets import rs_header, rs_footer, rs_panel, rs_table, status_badge
from ui.tui import make_header, make_bot_table, make_log_panel, make_footer

ASSIGNMENTS_FILE = "config/launcher_assignments.json"


@dataclass
class SetupEntry:
    """Per-bot row in Setup view: selection and script/args (synced with controller)."""
    bot_id: str
    username: str
    selected: bool
    script_name: str
    script_args: list


def _assignments_path(controller: BotController) -> Path:
    return Path(controller.root) / ASSIGNMENTS_FILE


def _load_assignments(controller: BotController) -> dict:
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
    """Read a single key (blocking). Returns 'up'/'down' for arrows."""
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


def _get_key_timeout(console: Console, timeout_sec: float) -> str:
    """Read a single key with timeout. Returns '' if no key pressed."""
    if sys.platform == "win32":
        try:
            import msvcrt
            deadline = time.time() + timeout_sec
            while time.time() < deadline:
                if msvcrt.kbhit():
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
                time.sleep(0.05)
            return ""
        except Exception:
            return ""
    return ""


def _build_setup_entries(controller: BotController) -> list:
    """Build SetupEntry list from controller.bots, using saved assignments for script/args."""
    saved = _load_assignments(controller)
    entries = []
    for bot_id, bot in controller.bots.items():
        a = saved.get(bot_id, {})
        script_name = a.get("script_name")
        if script_name is None:
            script_name = bot.script_name or ""
        script_args = a.get("script_args")
        if script_args is None:
            script_args = list(bot.script_args) if bot.script_args else []
        entries.append(
            SetupEntry(
                bot_id=bot_id,
                username=bot.username,
                selected=False,
                script_name=script_name,
                script_args=list(script_args),
            )
        )
    return entries


def _draw_setup(console: Console, controller: BotController, entries: list, cursor: int, presets: list) -> None:
    """Render Setup view: accounts table + presets + footer."""
    console.clear()
    console.print(rs_header(theme.TITLE_MAIN, theme.SUBTITLE_WORLD))

    table = Table(
        title="Accounts & Tasks",
        box=theme.RS_BOX,
        border_style=theme.rs_panel_border_style,
        header_style=theme.rs_table_header_style,
    )
    table.add_column("Sel", style=theme.RS_GOLD, width=4)
    table.add_column("ID", style=theme.rs_table_cell_style)
    table.add_column("Username", style=theme.rs_table_cell_style)
    table.add_column("Script", style=theme.rs_table_cell_style)
    table.add_column("Args", style=theme.rs_table_cell_style)
    for i, e in enumerate(entries):
        sel = "[X]" if e.selected else "[ ]"
        if i == cursor:
            sel = f"[bold {theme.RS_GOLD}]>{sel}<[/]"
        args_str = ",".join(e.script_args) if e.script_args else "-"
        if len(args_str) > 36:
            args_str = args_str[:36] + "..."
        table.add_row(sel, e.bot_id, e.username, e.script_name or "-", args_str)
    console.print(rs_panel(table, border_style=theme.rs_panel_border_style))

    if presets:
        preset_line = "  ".join(
            f"[{theme.RS_GOLD}]{i + 1}[/] {p['name']}" for i, p in enumerate(presets[:9])
        )
        console.print(rs_panel(f"Presets (apply to selected): {preset_line}", border_style=theme.rs_panel_border_style))

    footer = (
        "[A] Add  [E] Edit  [D] Delete  [Space] Toggle  [1-9] Apply preset  [P] Play  [L] Live  [Q] Quit"
    )
    console.print(rs_footer(footer))
    console.print(
        f"\n[dim]Row {cursor + 1}/{len(entries)}  |  Selected: {sum(1 for e in entries if e.selected)}[/]"
    )


def _apply_entries_to_bots(controller: BotController, entries: list) -> None:
    """Sync script/args from entries to controller.bots (in memory)."""
    for e in entries:
        bot = controller.get_bot(e.bot_id)
        if bot:
            bot.script_name = e.script_name
            bot.script_args = list(e.script_args)


def _run_setup_view(console: Console, controller: BotController) -> str:
    """Run Setup view loop. Returns 'live' to switch to Live, 'quit' to exit, or '' (should not happen)."""
    presets = controller.get_task_presets()
    entries = _build_setup_entries(controller)
    cursor = 0

    while True:
        if not entries:
            console.clear()
            console.print(rs_header(theme.TITLE_MAIN, theme.SUBTITLE_WORLD))
            console.print(rs_panel(
                "[dim]No accounts. Press [A] to add one.[/]",
                border_style=theme.rs_panel_border_style,
            ))
            console.print(rs_footer("[A] Add account  [Q] Quit"))
            key = _get_key(console)
            if key == "a":
                _do_add_account(controller)
                entries = _build_setup_entries(controller)
                cursor = 0
            elif key in ("q", "\x1b"):
                return "quit"
            continue

        _draw_setup(console, controller, entries, cursor, presets)
        key = _get_key(console)

        if key in ("q", "\x1b"):
            return "quit"
        if key in ("\r", "\n"):
            key = " "
        if key == " ":
            entries[cursor].selected = not entries[cursor].selected
            continue
        if key == "up":
            cursor = max(0, cursor - 1)
            continue
        if key == "down":
            cursor = min(len(entries) - 1, cursor + 1)
            continue
        if key == "a":
            _do_add_account(controller)
            entries = _build_setup_entries(controller)
            cursor = min(cursor, len(entries) - 1) if entries else 0
            continue
        if key == "e":
            e = entries[cursor]
            _do_edit_account(controller, e)
            controller.save_bots_to_config()
            _save_assignments(controller, entries)
            entries = _build_setup_entries(controller)
            cursor = min(cursor, len(entries) - 1)
            continue
        if key == "d":
            bot_id = entries[cursor].bot_id
            controller.remove_bot(bot_id)
            controller.save_bots_to_config()
            entries = _build_setup_entries(controller)
            cursor = min(cursor, len(entries) - 1) if entries else 0
            continue
        if key in "123456789":
            idx = int(key) - 1
            if idx < len(presets):
                selected = [x for x in entries if x.selected]
                if not selected:
                    selected = [entries[cursor]]
                p = presets[idx]
                for x in selected:
                    x.script_name = p.get("script", "")
                    x.script_args = list(p.get("args", []))
                _apply_entries_to_bots(controller, entries)
                controller.save_bots_to_config()
                _save_assignments(controller, entries)
            continue
        if key == "p":
            selected = [e for e in entries if e.selected]
            if not selected:
                console.print(f"[{theme.RS_WARN}]Select at least one bot (Space), then press P.[/]")
                _get_key(console)
                continue
            _apply_entries_to_bots(controller, entries)
            controller.save_bots_to_config()
            _save_assignments(controller, entries)
            started = 0
            for e in selected:
                if controller.start_bot(e.bot_id):
                    started += 1
                time.sleep(0.5)
            console.print(f"[{theme.RS_SUCCESS}]Started {started} bot(s). Press any key.[/]")
            _get_key(console)
            continue
        if key == "l":
            return "live"


def _do_add_account(controller: BotController) -> None:
    """Prompt for new account and add to controller + persist."""
    console = Console()
    try:
        bot_id = input("Bot ID (e.g. fisher_001): ").strip()
        if not bot_id:
            return
        username = input("Username: ").strip()
        if not username:
            return
        password = input("Password: ").strip()
        if not password:
            return
        script = input("Script name [FishingBot]: ").strip() or "FishingBot"
        args_in = input("Args (comma-separated): ").strip()
        args = [a.strip() for a in args_in.split(",") if a.strip()] if args_in else []
        account_name = username
        config = {
            "id": bot_id,
            "account": account_name,
            "username": username,
            "password": password,
            "script": script,
            "args": args,
        }
        controller.add_bot(config)
        controller.save_bots_to_config()
        console.print(f"[{theme.RS_SUCCESS}]Added account: {bot_id}[/]")
    except (EOFError, KeyboardInterrupt):
        pass


def _do_edit_account(controller: BotController, entry: SetupEntry) -> None:
    """Prompt to edit selected account (username, password, script, args); update controller."""
    console = Console()
    bot = controller.get_bot(entry.bot_id)
    if not bot:
        return
    try:
        username = input(f"Username [{bot.username}]: ").strip() or bot.username
        password = input("Password (leave blank to keep): ").strip()
        script = input(f"Script [{bot.script_name}]: ").strip() or (bot.script_name or "")
        args_in = input(f"Args (comma-separated) [{','.join(bot.script_args)}]: ").strip()
        args = [a.strip() for a in args_in.split(",") if a.strip()] if args_in else []
        bot.username = username
        if password:
            bot.password = password
        bot.account_name = username
        bot.script_name = script
        bot.script_args = args
        entry.username = username
        entry.script_name = script
        entry.script_args = args
    except (EOFError, KeyboardInterrupt):
        pass


def _draw_live(console: Console, controller: BotController) -> None:
    """Render Live view: header, bot table, log panel, footer."""
    console.clear()
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="bots", ratio=2),
        Layout(name="logs", ratio=1),
    )
    layout["header"].update(make_header(controller))
    layout["bots"].update(make_bot_table(controller))
    layout["logs"].update(make_log_panel(controller))
    layout["footer"].update(rs_footer("[S] Setup  [R] Refresh  [Q] Quit"))
    console.print(layout)


def _run_live_view(console: Console, controller: BotController) -> str:
    """Run Live view: refresh every second, handle S (Setup) and Q (Quit). Returns 'setup' or 'quit'."""
    while True:
        _draw_live(console, controller)
        key = _get_key_timeout(console, 1.0)
        if key == "s":
            return "setup"
        if key == "q" or key == "\x1b":
            return "quit"
        if key == "r":
            continue


def run_dashboard(controller: BotController) -> None:
    """Run the unified Dashboard (Setup + Live views) until user quits."""
    console = Console()
    current = "setup"

    while True:
        if current == "setup":
            next_view = _run_setup_view(console, controller)
            if next_view == "quit":
                break
            current = "live"
        else:
            next_view = _run_live_view(console, controller)
            if next_view == "quit":
                break
            current = "setup"

    console.print("[dim]Dashboard closed.[/]")
