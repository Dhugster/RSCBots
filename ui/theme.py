"""RuneScape Classic / OSRS theme for IdleRSC Bot Manager.
Central place for colors, borders, status styles, and copy.
"""
from rich import box

# --- Box / border ---
RS_BOX = box.SQUARE
RS_BOX_ROUNDED = box.ROUNDED

# --- Colors (Rich style strings; hex/rgb for truecolor, named fallback) ---
RS_GOLD = "#f9d000"
RS_GOLD_DIM = "#b58900"
RS_BROWN = "#94866d"
RS_BROWN_DARK = "#605443"
RS_TAN = "#d0bd97"
RS_BG_DARK = "#18140c"
RS_SUCCESS = "green"
RS_DANGER = "red"
RS_WARN = "yellow3"

# --- Panel style combinations ---
rs_header_style = f"bold {RS_GOLD} on {RS_BG_DARK}"
rs_panel_style = f"dim white on {RS_BG_DARK}"
rs_panel_border_style = RS_BROWN
rs_footer_style = f"bold {RS_GOLD} on {RS_BG_DARK}"
rs_log_content_style = f"dim white on {RS_BG_DARK}"
rs_table_header_style = f"bold {RS_GOLD}"
rs_table_cell_style = RS_TAN
rs_rule_style = RS_GOLD

# --- Copy constants (game-flavored labels) ---
TITLE_MAIN = "IdleRSC Bot Manager"
TITLE_CONTROL = "Control Panel"
TITLE_GAME_LOG = "Game Log"
TITLE_BOTS_ONLINE = "Bots Online"
SUBTITLE_WORLD = "Coleslaw World"
STATUS_RUN = "RUN"
STATUS_IDLE = "IDLE"
STATUS_ERR = "ERR"
STATUS_CRASH = "CRASH"
STATUS_DISCO = "DISCO"
STATUS_STOP = "STOP"
FOOTER_KEYS = "Commands: [S]tart | [P]ause | [R]estart | [K]ill | [L]ogs | [Q]uit (Ctrl+C)"
MSG_STARTING_ROSTER = "Starting bot roster..."
MSG_DONE = "Done."
MSG_FAILED = "Failed."
MSG_RECOVERED = "Recovered"


def style_status(bot_status) -> str:
    """Return Rich markup string for a bot status badge (e.g. [green]RUN[/])."""
    # #region agent log
    try:
        import json
        _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
        _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "theme.py:style_status", "message": "style_status", "data": {"bot_status_type": type(bot_status).__name__, "bot_status_repr": repr(bot_status)[:100]}, "hypothesisId": "H4"}) + "\n")
        _f.close()
    except Exception:
        pass
    # #endregion
    from core.bot_instance import BotStatus

    labels = {
        BotStatus.RUNNING: (RS_SUCCESS, STATUS_RUN),
        BotStatus.IDLE: (RS_WARN, STATUS_IDLE),
        BotStatus.STARTING: (RS_WARN, "START"),
        BotStatus.PAUSED: (RS_WARN, "PAUSE"),
        BotStatus.ERROR: (RS_DANGER, STATUS_ERR),
        BotStatus.CRASHED: (RS_DANGER, STATUS_CRASH),
        BotStatus.DISCONNECTED: (RS_WARN, STATUS_DISCO),
        BotStatus.STOPPED: (f"dim {RS_BROWN}", STATUS_STOP),
    }
    style, label = labels.get(bot_status, ("dim", "???"))
    return f"[{style}]{label}[/]"
