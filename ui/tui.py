"""TUI dashboard for IdleRSC bot manager (RuneScape theme)."""
import time
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.text import Text

from core.controller import BotController

from ui import theme
from ui.widgets import (
    rs_header,
    rs_footer,
    rs_panel,
    rs_table,
    status_badge,
)


def make_header(controller: BotController):
    """Build header panel (gold on dark, RS box)."""
    summary = controller.get_status_summary()
    subtitle = f"{theme.SUBTITLE_WORLD}  |  {summary['running']}/{summary['total']} {theme.TITLE_BOTS_ONLINE}"
    return rs_header(theme.TITLE_MAIN, subtitle)


def make_bot_table(controller: BotController):
    """Build bot status table (Control Panel)."""
    headers = ("Bot ID", "Script", "Status", "Runtime", "XP/hr", "Items")
    rows = []
    for bot_id, bot in controller.bots.items():
        xp = (
            f"{bot.metrics.xp_per_hour / 1000:.1f}k"
            if bot.metrics.xp_per_hour
            else "-"
        )
        items = f"{bot.metrics.items_collected:,}" if bot.metrics.items_collected else "-"
        rows.append(
            (
                bot_id,
                bot.script_name,
                Text.from_markup(status_badge(bot.status)),
                bot.runtime_formatted,
                xp,
                items,
            )
        )
    table = rs_table(headers, rows, title=theme.TITLE_CONTROL)
    return rs_panel(table, title=theme.TITLE_CONTROL, border_style=theme.rs_panel_border_style)


def make_log_panel(controller: BotController, lines: int = 20):
    """Build Game Log panel: [BotID] in gold, ERROR lines in red."""
    aggregated = controller.log_aggregator.get_aggregated_logs({"tail": lines})
    if not aggregated:
        content = Text.from_markup(f"[dim {theme.RS_TAN}]No log output yet.[/]")
    else:
        parts = []
        for line in aggregated[-lines:]:
            if line.startswith("["):
                bracket_end = line.find("]")
                if bracket_end != -1:
                    bot_part = line[: bracket_end + 1]
                    rest = line[bracket_end + 1 :].strip()
                    if "ERROR" in rest.upper():
                        parts.append(
                            f"[{theme.RS_GOLD}]{bot_part}[/] [{theme.RS_DANGER}]{rest}[/]"
                        )
                    else:
                        parts.append(
                            f"[{theme.RS_GOLD}]{bot_part}[/] [dim {theme.RS_TAN}]{rest}[/]"
                        )
                else:
                    parts.append(f"[dim {theme.RS_TAN}]{line}[/]")
            else:
                parts.append(f"[dim {theme.RS_TAN}]{line}[/]")
        content = Text.from_markup("\n".join(parts))
    return rs_panel(
        content,
        title=theme.TITLE_GAME_LOG,
        style=theme.rs_log_content_style,
        border_style=theme.rs_panel_border_style,
    )


def make_footer():
    """Build footer (dark bar, gold keys)."""
    return rs_footer(theme.FOOTER_KEYS)


def run_dashboard(controller: BotController) -> None:
    """Run the Rich Live TUI dashboard."""
    console = Console()
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

    def generate() -> Layout:
        layout["header"].update(make_header(controller))
        layout["bots"].update(make_bot_table(controller))
        layout["logs"].update(make_log_panel(controller))
        layout["footer"].update(make_footer())
        return layout

    try:
        with Live(generate, refresh_per_second=2, screen=True, console=console):
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
