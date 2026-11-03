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

from rich.syntax import Syntax

from netconfigvault import __version__
from netconfigvault.compliance.engine import ComplianceEngine
from netconfigvault.compliance.reports import ComplianceReportGenerator
from netconfigvault.core.backup_engine import BackupEngine
from netconfigvault.core.diff_engine import DiffEngine
from netconfigvault.core.storage import StorageManager
from netconfigvault.inventory.loader import InventoryLoader
from netconfigvault.models.backup import BackupStatus
from netconfigvault.models.compliance import ComplianceSeverity
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
        if res.diff and res.diff.has_changes:
            sec_tags = f" [{', '.join(res.diff.changed_sections)}]" if res.diff.changed_sections else ""
            details = f"[yellow]{res.diff.summary}{sec_tags}[/yellow]"
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
def diff(
    hostname: str = typer.Argument(..., help="Hostname of target device"),
    site: Optional[str] = typer.Option(None, "--site", "-s", help="Site of target device"),
    output_html: Optional[Path] = typer.Option(None, "--html", "-o", help="Optional path to save HTML report"),
) -> None:
    """Compare recent configuration snapshots and visualize changes."""
    settings = AppSettings.load()
    loader = InventoryLoader(settings.inventory_path)
    inv = loader.load()

    # Resolve device from inventory to find site if not provided
    matched = [d for d in inv.devices if d.hostname.lower() == hostname.lower()]
    device_site = site or (matched[0].site if matched else "default")

    storage = StorageManager(backup_dir=settings.backup_dir, git_enabled=False)
    backups = storage.list_backups(hostname, device_site)

    if len(backups) < 2:
        console.print(
            f"[yellow]Need at least 2 snapshot backups for {hostname} at site '{device_site}' to compute diff.[/yellow]\n"
            f"[dim]Found {len(backups)} snapshot(s) in {settings.backup_dir / device_site / hostname}[/dim]"
        )
        raise typer.Exit(code=1)

    # Compare the two most recent snapshots
    prior_path = backups[-2]
    latest_path = backups[-1]

    old_cfg = prior_path.read_text(encoding="utf-8")
    new_cfg = latest_path.read_text(encoding="utf-8")

    diff_engine = DiffEngine()
    result = diff_engine.compare(hostname, old_cfg, new_cfg, generate_html=True)

    console.print(
        Panel.fit(
            f"[bold cyan]Configuration Diff Analysis[/bold cyan] for [bold]{hostname}[/bold]\n"
            f"[dim]Baseline: {prior_path.name}  ⟶  Current: {latest_path.name}[/dim]\n"
            f"[bold]{result.summary}[/bold]",
            border_style="cyan",
        )
    )

    if not result.has_changes:
        console.print("[green]✔ Configurations are identical. No differences found.[/green]\n")
        return

    # Print syntax-colored diff
    for line in result.unified_diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            console.print(f"[bold blue]{line}[/bold blue]")
        elif line.startswith("@@"):
            console.print(f"[cyan]{line}[/cyan]")
        elif line.startswith("+"):
            console.print(f"[green]{line}[/green]")
        elif line.startswith("-"):
            console.print(f"[red]{line}[/red]")
        else:
            console.print(f"[dim]{line}[/dim]")

    if output_html and result.html_diff:
        output_html.parent.mkdir(parents=True, exist_ok=True)
        output_html.write_text(result.html_diff, encoding="utf-8")
        console.print(f"\n[green]HTML diff report exported to:[/green] [bold]{output_html.resolve()}[/bold]\n")


@app.command()
def compliance(
    hostname: Optional[str] = typer.Argument(None, help="Device hostname to audit"),
    fleet: bool = typer.Option(False, "--fleet", "-f", help="Audit all fleet devices"),
    output_html: Optional[Path] = typer.Option(None, "--html", "-o", help="Optional path to export HTML audit report"),
) -> None:
    """Audit configurations against CIS security baselines and policy rules."""
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()
    storage = StorageManager(backup_dir=settings.backup_dir, git_enabled=False)
    engine = ComplianceEngine(rules_dir=settings.compliance_rules_dir)

    if fleet or not hostname:
        summary = engine.evaluate_fleet(inventory=inv, storage=storage)
        table = Table(
            title=f"Fleet Compliance Summary (Score: {summary.overall_score}%)",
            header_style="bold magenta",
            show_lines=True,
        )
        table.add_column("Device", style="cyan bold")
        table.add_column("Platform", style="magenta")
        table.add_column("Score", justify="right")
        table.add_column("Passed", justify="center")
        table.add_column("Violations", justify="center")
        table.add_column("Critical Violations", justify="center")

        for r in summary.reports:
            score_color = "green" if r.score_percent >= 80 else "yellow" if r.score_percent >= 60 else "red"
            crit_badge = f"[bold red]{len(r.critical_failures)}[/bold red]" if r.critical_failures else "[green]0[/green]"
            table.add_row(
                r.hostname,
                r.device_type,
                f"[{score_color}]{r.score_percent}%[/{score_color}]",
                f"[green]{r.passed}[/green] / {r.total_rules}",
                f"[red]{r.failed}[/red]" if r.failed else "[green]0[/green]",
                crit_badge,
            )

        console.print("\n")
        console.print(table)
        console.print(
            f"[bold]Total Evaluated Devices:[/bold] {summary.total_devices} | "
            f"[green][bold]Fully Compliant:[/bold] {summary.compliant_devices}[/green] | "
            f"[red][bold]Non-Compliant:[/bold] {summary.non_compliant_devices}[/red] | "
            f"[bold red]Total Critical Violations:[/bold red] {summary.total_critical_violations}\n"
        )
        return

    # Single device audit
    matched = [d for d in inv.devices if d.hostname.lower() == hostname.lower()]
    if not matched:
        console.print(f"[bold red]Device '{hostname}' not found in inventory.[/bold red]")
        raise typer.Exit(code=1)

    device = matched[0]
    latest_config = storage.get_latest_config(device.hostname, device.site)
    if latest_config is None:
        console.print(f"[bold red]No saved configuration found for '{hostname}'. Run a backup first.[/bold red]")
        raise typer.Exit(code=1)

    report = engine.evaluate(device, latest_config)

    score_color = "green" if report.score_percent >= 80 else "yellow" if report.score_percent >= 60 else "red"
    console.print(
        Panel.fit(
            f"[bold cyan]Security Compliance Report:[/bold cyan] [bold]{report.hostname}[/bold] ({report.device_type})\n"
            f"Overall Score: [{score_color} bold]{report.score_percent}%[/{score_color} bold] | "
            f"Passed: [green]{report.passed}[/green] / {report.total_rules} rules",
            border_style="cyan",
        )
    )

    table = Table(title=f"Rule Audit Details for {hostname}", show_lines=True)
    table.add_column("Rule ID", style="bold", no_wrap=True)
    table.add_column("Severity", justify="center")
    table.add_column("Name")
    table.add_column("Status", justify="center")
    table.add_column("Remediation / Details", style="dim", max_width=45)

    for r in report.results:
        rule = r.rule
        sev_color = {
            ComplianceSeverity.CRITICAL: "bold red",
            ComplianceSeverity.HIGH: "yellow",
            ComplianceSeverity.MEDIUM: "blue",
            ComplianceSeverity.LOW: "dim",
        }.get(rule.severity, "white")

        status_text = "[green]✔ PASS[/green]" if r.passed else "[bold red]✘ FAIL[/bold red]"
        detail = r.message
        if not r.passed and rule.remediation:
            detail = f"[yellow]{rule.remediation.splitlines()[0]}[/yellow]"

        table.add_row(
            rule.id,
            f"[{sev_color}]{rule.severity.value.upper()}[/{sev_color}]",
            rule.name,
            status_text,
            detail,
        )

    console.print("\n")
    console.print(table)
    console.print("\n")

    if output_html:
        html_report = ComplianceReportGenerator.generate_html(report)
        output_html.parent.mkdir(parents=True, exist_ok=True)
        output_html.write_text(html_report, encoding="utf-8")
        console.print(f"[green]HTML compliance report exported to:[/green] [bold]{output_html.resolve()}[/bold]\n")


@app.command()
def api(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind network host"),
    port: int = typer.Option(8000, "--port", "-p", help="Port number"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for dev"),
) -> None:
    """Launch NetConfigVault REST API server with interactive Swagger documentation."""
    import uvicorn
    console.print(
        Panel.fit(
            f"[bold cyan]NetConfigVault REST API Server[/bold cyan]\n"
            f"Serving at: [bold green]http://{host}:{port}[/bold green]\n"
            f"Swagger Docs: [bold green]http://{host}:{port}/docs[/bold green]",
            border_style="cyan",
        )
    )
    uvicorn.run("netconfigvault.api.app:app", host=host, port=port, reload=reload)


@app.command()
def version() -> None:
    """Display NetConfigVault version information."""
    console.print(f"NetConfigVault version: [bold cyan]{__version__}[/bold cyan]")


if __name__ == "__main__":
    app()

