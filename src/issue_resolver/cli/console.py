"""Rich console for consistent terminal output."""

from rich.console import Console
from rich.theme import Theme

theme = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "cost": "magenta",
        "dry_run": "bold blue",
    }
)

console = Console(theme=theme, stderr=False)
err_console = Console(theme=theme, stderr=True)
