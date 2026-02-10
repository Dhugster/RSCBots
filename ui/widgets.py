"""Reusable RuneScape-themed widgets for CLI and TUI."""
from typing import Any, List, Optional, Sequence, Tuple

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui import theme


def rs_panel(
    content: Any,
    title: Optional[str] = None,
    style: Optional[str] = None,
    border_style: Optional[str] = None,
    box_style: Optional[Any] = None,
) -> Panel:
    """Wrap content in a themed Panel (RS box and border)."""
    return Panel(
        content,
        title=title,
        style=style or theme.rs_panel_style,
        border_style=border_style or theme.rs_panel_border_style,
        box=box_style or theme.RS_BOX,
    )


def rs_table(
    headers: Sequence[str],
    rows: List[Tuple[Any, ...]],
    title: Optional[str] = None,
    header_style: Optional[str] = None,
) -> Table:
    """Build a themed Table with gold headers and brown border."""
    t = Table(
        title=title,
        box=theme.RS_BOX,
        border_style=theme.rs_panel_border_style,
        header_style=header_style or theme.rs_table_header_style,
    )
    for h in headers:
        t.add_column(h, style=theme.rs_table_cell_style)
    for row in rows:
        t.add_row(*row)
    return t


def rs_header(text: str, subtitle: Optional[str] = None) -> Panel:
    """Top bar: gold on dark brown."""
    content = text
    if subtitle:
        content = f"{text}  |  {subtitle}"
    return Panel(
        content,
        style=theme.rs_header_style,
        border_style=theme.RS_BROWN_DARK,
        box=theme.RS_BOX,
    )


def rs_footer(keys_text: str) -> Panel:
    """Footer bar with gold key hints."""
    return Panel(
        keys_text,
        style=theme.rs_footer_style,
        border_style=theme.RS_BROWN_DARK,
        box=theme.RS_BOX,
    )


def status_badge(bot_status) -> str:
    """Return Rich markup for status (uses theme.style_status)."""
    return theme.style_status(bot_status)
