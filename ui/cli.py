"""Command-line interface for bot management (RuneScape theme)."""
import click
import time
from pathlib import Path
from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from core.controller import BotController
from core.bot_instance import BotStatus

from ui import theme
from ui.widgets import rs_table, status_badge

console = Console()
_controller: BotController | None = None


def get_controller() -> BotController:
    """Get or create controller instance (config relative to project root)."""
    global _controller
    if _controller is None:
        root = Path(__file__).resolve().parent.parent
        config_path = root / "config" / "bots.yaml"
        # #region agent log
        try:
            import json
            _f = __import__("builtins").open(r"c:\Users\Owner\.cursor\plans\RSC\.cursor\debug.log", "a", encoding="utf-8")
            _f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "location": "cli.py:get_controller", "message": "get_controller", "data": {"config_path": str(config_path), "root": str(root)}, "hypothesisId": "H1"}) + "\n")
            _f.close()
        except Exception:
            pass
        # #endregion
        _controller = BotController(str(config_path))
    return _controller


def _default_callback(ctx: click.Context) -> None:
    """No subcommand: open the unified Dashboard."""
    from ui.dashboard import run_dashboard
    run_dashboard(get_controller())


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """IdleRSC Bot Management System."""
    ctx.obj = get_controller()
    if ctx.invoked_subcommand is None:
        _default_callback(ctx)


@cli.command("start-all")
@click.pass_obj
def start_all(controller: BotController) -> None:
    """Start all configured bots."""
    console.print(f"[bold {theme.RS_GOLD}]{theme.MSG_STARTING_ROSTER}[/]")
    started = controller.start_all()
    console.print(f"[{theme.RS_SUCCESS}]{theme.MSG_DONE}[/] Started {started}/{len(controller.bots)} bots")


@cli.command()
@click.argument("bot_id")
@click.pass_obj
def start(controller: BotController, bot_id: str) -> None:
    """Start a specific bot."""
    if controller.start_bot(bot_id):
        console.print(f"[{theme.RS_SUCCESS}]{theme.MSG_DONE}[/] Started bot: {bot_id}")
    else:
        console.print(f"[{theme.RS_DANGER}]{theme.MSG_FAILED}[/] to start bot: {bot_id}")


@cli.command()
@click.argument("bot_id")
@click.pass_obj
def stop(controller: BotController, bot_id: str) -> None:
    """Stop a specific bot."""
    if controller.stop_bot(bot_id):
        console.print(f"[{theme.RS_SUCCESS}]{theme.MSG_DONE}[/] Stopped bot: {bot_id}")
    else:
        console.print(f"[{theme.RS_DANGER}]{theme.MSG_FAILED}[/] to stop bot: {bot_id}")


@cli.command("stop-all")
@click.pass_obj
def stop_all(controller: BotController) -> None:
    """Stop all bots."""
    console.print(f"[bold {theme.RS_DANGER}]Stopping all bots...[/]")
    stopped = controller.stop_all()
    console.print(f"[{theme.RS_SUCCESS}]{theme.MSG_DONE}[/] Stopped {stopped} bots")


@cli.command()
@click.argument("bot_id")
@click.pass_obj
def restart(controller: BotController, bot_id: str) -> None:
    """Restart a specific bot."""
    if controller.restart_bot(bot_id):
        console.print(f"[{theme.RS_SUCCESS}]{theme.MSG_DONE}[/] Restarted bot: {bot_id}")
    else:
        console.print(f"[{theme.RS_DANGER}]{theme.MSG_FAILED}[/] to restart bot: {bot_id}")


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
    console.print(f"[{theme.RS_SUCCESS}]{theme.MSG_DONE}[/] Added bot: {bot_id}")
    if auto_start:
        if controller.start_bot(bot_id):
            console.print(f"[{theme.RS_SUCCESS}]{theme.MSG_DONE}[/] Started bot: {bot_id}")


@cli.command()
@click.option("--script", required=True, help="Script to run")
@click.option("--args", multiple=True, help="Script arguments")
@click.option("--count", default=5, type=int, help="Number of bots")
@click.pass_obj
def swarm(controller: BotController, script: str, args: tuple, count: int) -> None:
    """Start multiple bots on the same task."""
    console.print(f"[bold {theme.RS_GOLD}]Starting swarm mode:[/] {count} bots running {script}")
    args_variations = [list(args)] if args else [[]]
    controller.swarm_mode(script, args_variations, count)
    console.print(f"[{theme.RS_SUCCESS}]{theme.MSG_DONE}[/] Swarm activated")


@cli.command()
@click.pass_obj
def status(controller: BotController) -> None:
    """Show status of all bots."""
    summary = controller.get_status_summary()
    console.print()
    console.print(Rule(style=theme.rs_rule_style, characters="-"))
    console.print(f"[bold {theme.RS_GOLD}]Bot Status Summary[/]")
    console.print(
        f"Total: {summary['total']} | "
        f"[{theme.RS_SUCCESS}]Running: {summary['running']}[/] | "
        f"[{theme.RS_BROWN}]Stopped: {summary['stopped']}[/] | "
        f"[{theme.RS_DANGER}]Crashed: {summary['crashed']}[/] | "
        f"[{theme.RS_WARN}]Error: {summary['error']}[/]"
    )
    console.print()
    headers = ("Bot ID", "Script", "Status", "Runtime", "XP/hr", "Items")
    rows = []
    for bot_id, bot in controller.bots.items():
        xp_display = (
            f"{bot.metrics.xp_per_hour / 1000:.1f}k" if bot.metrics.xp_per_hour else "-"
        )
        items_display = (
            f"{bot.metrics.items_collected:,}" if bot.metrics.items_collected else "-"
        )
        rows.append(
            (
                bot_id,
                bot.script_name,
                Text.from_markup(status_badge(bot.status)),
                bot.runtime_formatted,
                xp_display,
                items_display,
            )
        )
    table = rs_table(headers, rows, title="Bot Details")
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
            console.print(f"[{theme.RS_DANGER}]Bot not found: {bot}[/]")
            return
        console.print(Rule(style=theme.rs_rule_style, characters="-"))
        console.print(f"[bold {theme.RS_GOLD}]{bot}[/]")
        for log in bot_instance.get_recent_logs(tail):
            if "ERROR" in log.upper():
                console.print(f"[{theme.RS_DANGER}]{log}[/]")
            else:
                console.print(f"[dim {theme.RS_TAN}]{log}[/]")
        if follow:
            console.print(f"[dim {theme.RS_BROWN}]Follow mode: press Ctrl+C to stop[/]")
            try:
                while True:
                    for log in bot_instance.get_recent_logs(tail):
                        if "ERROR" in log.upper():
                            console.print(f"[{theme.RS_DANGER}]{log}[/]")
                        else:
                            console.print(f"[dim {theme.RS_TAN}]{log}[/]")
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        for bot_id, bot_instance in controller.bots.items():
            console.print()
            console.print(Rule(style=theme.rs_rule_style, characters="-"))
            console.print(f"[bold {theme.RS_GOLD}]{bot_id}[/]")
            for log in bot_instance.get_recent_logs(10):
                if "ERROR" in log.upper():
                    console.print(f"[{theme.RS_DANGER}]{log}[/]")
                else:
                    console.print(f"[dim {theme.RS_TAN}]{log}[/]")


@cli.command()
@click.pass_obj
def dashboard(controller: BotController) -> None:
    """Launch the unified Dashboard (Setup + Live views)."""
    from ui.dashboard import run_dashboard
    run_dashboard(controller)


@cli.command()
@click.pass_obj
def launch(controller: BotController) -> None:
    """One-click launcher: select bots, assign scripts, press P to start all."""
    from ui.launcher import run_launcher
    run_launcher(controller)


@cli.command()
@click.pass_obj
def recover(controller: BotController) -> None:
    """Recover crashed bots."""
    recovered = controller.recovery_system.recover_all()
    console.print(f"[{theme.RS_SUCCESS}]{theme.MSG_RECOVERED}[/] {recovered} bots")


if __name__ == "__main__":
    cli()
