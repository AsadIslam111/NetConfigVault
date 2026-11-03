"""Command Line Interface for NetConfigVault."""

import logging
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from netconfigvault import __version__
from netconfigvault.core.backup_engine import BackupEngine
from netconfigvault.inventory.loader import InventoryLoader
from netconfigvault.models.backup import BackupStatus
from netconfigvault.settings import AppSettings

app = typer.Typer(
    name="ncv",
    help="NetConfigVault - Automated Network Configuration Backup & Compliance System.",
    add_completion=False,
)
console = Console()


def configure_logging(log_dir: Path, verbose: bool = False) -> None:
    """Setup console and file logging."""
    log_dir.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO

    file_handler = logging.FileHandler(log_dir / "ncv.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    console_handler = RichHandler(
        console=console,
        show_path=False,
        rich_tracebacks=True,
        markup=True,
    )
    console_handler.setLevel(level)

    logging.basicConfig(
        level=level,
        handlers=[console_handler, file_handler],
        force=True,
    )


@app.command()
def backup(
    group: Optional[List[str]] = typer.Option(None, "--group", "-g", help="Filter target devices by group"),
    site: Optional[List[str]] = typer.Option(None, "--site", "-s", help="Filter target devices by site"),
    inventory_file: Optional[Path] = typer.Option(None, "--inventory", "-i", help="Path to custom inventory.yml"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose debug logging"),
) -> None:
    """Execute configuration backup across managed network devices."""
    settings = AppSettings.load()
    if inventory_file:
        settings.inventory_path = inventory_file

    configure_logging(settings.log_dir, verbose=verbose)

    console.print(
        Panel.fit(
            f"[bold cyan]NetConfigVault v{__version__}[/bold cyan]\n"
            f"[dim]Initiating automated configuration backup run...[/dim]",
            border_style="cyan",
        )
    )

    try:
        loader = InventoryLoader(settings.inventory_path)
        inventory = loader.load()
    except Exception as e:
        console.print(f"[bold red]Error loading inventory:[/bold red] {e}")
        raise typer.Exit(code=1)

    engine = BackupEngine(settings)
    summary = engine.run(inventory=inventory, groups=group, sites=site)

    # Format result table
    table = Table(
        title=f"Backup Run Report [{summary.run_id}]",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Device Hostname", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Changed", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Attempts", justify="center")
    table.add_column("Details / Error", style="dim", max_width=50)

    for res in summary.results:
        # Determine status badge
        if res.status == BackupStatus.SUCCESS:
            status_text = "[green]SUCCESS[/green]"
        elif res.status == BackupStatus.AUTH_FAILED:
            status_text = "[red]AUTH ERROR[/red]"
        elif res.status == BackupStatus.TIMEOUT:
            status_text = "[yellow]TIMEOUT[/yellow]"
        elif res.status == BackupStatus.SKIPPED:
            status_text = "[dim]SKIPPED[/dim]"
        else:
            status_text = "[bold red]FAILED[/bold red]"

        changed_text = "-"
        duration_text = "-"
        if res.metadata:
            changed_text = "[bold yellow]YES[/bold yellow]" if res.metadata.changed else "[green]NO[/green]"
            duration_text = f"{res.metadata.duration_seconds:.2f}s"

        details = res.error or res.message or ""
        table.add_row(
            res.device_hostname,
            status_text,
            changed_text,
            duration_text,
            str(res.attempts),
            details,
        )

    console.print("\n")
    console.print(table)

    # Summary metrics panel
    success_rate = (
        round((summary.successful / summary.total_devices) * 100, 1)
        if summary.total_devices > 0
        else 0.0
    )
    console.print(
        f"\n[bold]Total Targets:[/bold] {summary.total_devices} | "
        f"[green][bold]Successful:[/bold] {summary.successful}[/green] | "
        f"[yellow][bold]Changed:[/bold] {summary.changed}[/yellow] | "
        f"[red][bold]Failed:[/bold] {summary.failed}[/red] | "
        f"[cyan][bold]Success Rate:[/bold] {success_rate}%[/cyan]\n"
    )

    if summary.failed > 0:
        raise typer.Exit(code=2)


@app.command()
def inventory(
    inventory_file: Optional[Path] = typer.Option(None, "--inventory", "-i", help="Path to inventory YAML"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Filter by device group"),
    site: Optional[str] = typer.Option(None, "--site", "-s", help="Filter by site"),
) -> None:
    """Inspect and validate device inventory entries."""
    settings = AppSettings.load()
    if inventory_file:
        settings.inventory_path = inventory_file

    try:
        loader = InventoryLoader(settings.inventory_path)
        inv = loader.load()
    except Exception as e:
        console.print(f"[bold red]Failed to read inventory:[/bold red] {e}")
        raise typer.Exit(code=1)

    devices = inv.devices
    if group:
        devices = [d for d in devices if group.lower() in [g.lower() for g in d.groups]]
    if site:
        devices = [d for d in devices if d.site.lower() == site.lower()]

    table = Table(
        title=f"Device Inventory ({len(devices)} items)",
        header_style="bold blue",
        show_lines=True,
    )
    table.add_column("Hostname", style="cyan bold")
    table.add_column("Host IP/FQDN")
    table.add_column("Platform (device_type)", style="magenta")
    table.add_column("Port", justify="right")
    table.add_column("Site")
    table.add_column("Role")
    table.add_column("Groups")
    table.add_column("Enabled", justify="center")

    for d in devices:
        status = "[green]YES[/green]" if d.enabled else "[red]NO[/red]"
        table.add_row(
            d.hostname,
            d.host,
            d.device_type.value,
            str(d.port),
            d.site,
            d.role,
            ", ".join(d.groups) if d.groups else "-",
            status,
        )

    console.print("\n")
    console.print(table)
    console.print(f"[dim]Inventory source: {settings.inventory_path.resolve()}[/dim]\n")


@app.command()
def version() -> None:
    """Display NetConfigVault version information."""
    console.print(f"NetConfigVault version: [bold cyan]{__version__}[/bold cyan]")


if __name__ == "__main__":
    app()

