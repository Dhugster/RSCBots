"""Command-line interface for bot management."""
import click
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table

from core.controller import BotController
from core.bot_instance import BotStatus

console = Console()
_controller: BotController | None = None


def get_controller() -> BotController:
    """Get or create controller instance (config relative to project root)."""
    global _controller
    if _controller is None:
        root = Path(__file__).resolve().parent.parent
        config_path = root / "config" / "bots.yaml"
        _controller = BotController(str(config_path))
    return _controller


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """IdleRSC Bot Management System."""
    ctx.obj = get_controller()


@cli.command("start-all")
@click.pass_obj
def start_all(controller: BotController) -> None:
    """Start all configured bots."""
    console.print("[bold blue]Starting all bots...[/]")
    started = controller.start_all()
    console.print(f"[green]OK[/] Started {started}/{len(controller.bots)} bots")


@cli.command()
@click.argument("bot_id")
@click.pass_obj
def start(controller: BotController, bot_id: str) -> None:
    """Start a specific bot."""
    if controller.start_bot(bot_id):
        console.print(f"[green]OK[/] Started bot: {bot_id}")
    else:
        console.print(f"[red]Failed[/] to start bot: {bot_id}")


@cli.command()
@click.argument("bot_id")
@click.pass_obj
def stop(controller: BotController, bot_id: str) -> None:
    """Stop a specific bot."""
    if controller.stop_bot(bot_id):
        console.print(f"[green]OK[/] Stopped bot: {bot_id}")
    else:
        console.print(f"[red]Failed[/] to stop bot: {bot_id}")


@cli.command("stop-all")
@click.pass_obj
def stop_all(controller: BotController) -> None:
    """Stop all bots."""
    console.print("[bold red]Stopping all bots...[/]")
    stopped = controller.stop_all()
    console.print(f"[green]OK[/] Stopped {stopped} bots")


@cli.command()
@click.argument("bot_id")
@click.pass_obj
def restart(controller: BotController, bot_id: str) -> None:
    """Restart a specific bot."""
    if controller.restart_bot(bot_id):
        console.print(f"[green]OK[/] Restarted bot: {bot_id}")
    else:
        console.print(f"[red]Failed[/] to restart bot: {bot_id}")


@cli.command("add-bot")
@click.option("--account", required=True, help="Account name")
@click.option("--username", required=True, help="Login username")
@click.option("--password", required=True, help="Login password")
@click.option("--script", required=True, help="Script name")
@click.option("--args", multiple=True, help="Script arguments")
@click.option("--auto-start", is_flag=True, help="Start immediately")
@click.pass_obj
def add_bot(
    controller: BotController,
    account: str,
    username: str,
    password: str,
    script: str,
    args: tuple,
    auto_start: bool,
) -> None:
    """Add a new bot."""
    bot_id = f"{script.lower()}_{int(time.time())}"
    bot_config = {
        "id": bot_id,
        "account": account,
        "username": username,
        "password": password,
        "script": script,
        "args": list(args),
    }
    controller.add_bot(bot_config)
    console.print(f"[green]OK[/] Added bot: {bot_id}")
    if auto_start:
        if controller.start_bot(bot_id):
            console.print(f"[green]OK[/] Started bot: {bot_id}")


@cli.command()
@click.option("--script", required=True, help="Script to run")
@click.option("--args", multiple=True, help="Script arguments")
@click.option("--count", default=5, type=int, help="Number of bots")
@click.pass_obj
def swarm(controller: BotController, script: str, args: tuple, count: int) -> None:
    """Start multiple bots on the same task."""
    console.print(f"[bold yellow]Starting swarm mode:[/] {count} bots running {script}")
    args_variations = [list(args)] if args else [[]]
    controller.swarm_mode(script, args_variations, count)
    console.print("[green]OK[/] Swarm activated")


@cli.command()
@click.pass_obj
def status(controller: BotController) -> None:
    """Show status of all bots."""
    summary = controller.get_status_summary()
    console.print("\n[bold]Bot Status Summary[/]")
    console.print(
        f"Total: {summary['total']} | "
        f"[green]Running: {summary['running']}[/] | "
        f"Stopped: {summary['stopped']} | "
        f"[red]Crashed: {summary['crashed']}[/] | "
        f"[yellow]Error: {summary['error']}[/]\n"
    )
    table = Table(title="Bot Details")
    table.add_column("Bot ID", style="cyan")
    table.add_column("Script", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Runtime", style="yellow")
    table.add_column("XP/hr", style="blue")
    table.add_column("Items", style="white")
    status_icons = {
        BotStatus.RUNNING: "[green]RUN[/]",
        BotStatus.IDLE: "IDLE",
        BotStatus.ERROR: "[red]ERR[/]",
        BotStatus.CRASHED: "[red]CRASH[/]",
        BotStatus.STOPPED: "[dim]STOP[/]",
    }
    for bot_id, bot in controller.bots.items():
        status_display = status_icons.get(bot.status, "???")
        xp_display = (
            f"{bot.metrics.xp_per_hour / 1000:.1f}k" if bot.metrics.xp_per_hour else "-"
        )
        items_display = (
            f"{bot.metrics.items_collected:,}" if bot.metrics.items_collected else "-"
        )
        table.add_row(
            bot_id,
            bot.script_name,
            status_display,
            bot.runtime_formatted,
            xp_display,
            items_display,
        )
    console.print(table)


@cli.command()
@click.option("--bot", default=None, help="Specific bot ID")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--tail", default=50, type=int, help="Number of lines to show")
@click.pass_obj
def logs(controller: BotController, bot: str | None, follow: bool, tail: int) -> None:
    """View bot logs."""
    if bot:
        bot_instance = controller.get_bot(bot)
        if not bot_instance:
            console.print(f"[red]Bot not found: {bot}[/]")
            return
        for log in bot_instance.get_recent_logs(tail):
            console.print(log)
        if follow:
            console.print("[dim]Follow mode: press Ctrl+C to stop[/]")
            try:
                while True:
                    for log in bot_instance.get_recent_logs(tail):
                        console.print(log)
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        for bot_id, bot_instance in controller.bots.items():
            console.print(f"\n[bold cyan]=== {bot_id} ===[/]")
            for log in bot_instance.get_recent_logs(10):
                console.print(log)


@cli.command()
@click.pass_obj
def dashboard(controller: BotController) -> None:
    """Launch the TUI dashboard."""
    from ui.tui import run_dashboard
    run_dashboard(controller)


@cli.command()
@click.pass_obj
def recover(controller: BotController) -> None:
    """Recover crashed bots."""
    recovered = controller.recovery_system.recover_all()
    console.print(f"[green]OK[/] Recovered {recovered} bots")


if __name__ == "__main__":
    cli()
