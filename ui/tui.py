"""TUI dashboard for IdleRSC bot manager."""
import time
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.controller import BotController
from core.bot_instance import BotStatus


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def make_header(controller: BotController) -> Panel:
    """Build header panel."""
    summary = controller.get_status_summary()
    title = (
        f"[bold blue]IdleRSC Bot Management System[/] - "
        f"[green]{summary['running']}/{summary['total']} Bots[/] - "
        f"Coleslaw World"
    )
    return Panel(title, style="bold white on blue")


def make_bot_table(controller: BotController) -> Panel:
    """Build bot status table."""
    table = Table(title="Bot Status")
    table.add_column("Bot ID", style="cyan")
    table.add_column("Script", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Runtime", style="yellow")
    table.add_column("XP/hr", style="blue")
    table.add_column("Items", style="white")
    status_icons = {
        BotStatus.RUNNING: "[green]RUN[/]",
        BotStatus.IDLE: "[yellow]IDLE[/]",
        BotStatus.ERROR: "[red]ERR[/]",
        BotStatus.CRASHED: "[red]CRASH[/]",
        BotStatus.STOPPED: "[dim]STOP[/]",
    }
    for bot_id, bot in controller.bots.items():
        status_display = status_icons.get(bot.status, "???")
        xp = (
            f"{bot.metrics.xp_per_hour / 1000:.1f}k"
            if bot.metrics.xp_per_hour
            else "-"
        )
        items = f"{bot.metrics.items_collected:,}" if bot.metrics.items_collected else "-"
        table.add_row(
            bot_id,
            bot.script_name,
            status_display,
            bot.runtime_formatted,
            xp,
            items,
        )
    return Panel(table, border_style="blue", title="Bots")


def make_log_panel(controller: BotController, lines: int = 20) -> Panel:
    """Build live log feed panel."""
    aggregated = controller.log_aggregator.get_aggregated_logs({"tail": lines})
    if not aggregated:
        content = Text.from_markup("[dim]No log output yet.[/]")
    else:
        content = Text.from_markup("\n".join(aggregated[-lines:]))
    return Panel(content, title="Live Log Feed", border_style="green")


def make_footer() -> Panel:
    """Build footer with commands."""
    return Panel(
        "[bold]Commands:[/] [s]tart | [p]ause | [r]estart | [k]ill | [l]ogs | [q]uit (Ctrl+C)",
        style="bold white on black",
    )


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
