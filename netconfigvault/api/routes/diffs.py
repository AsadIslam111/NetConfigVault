"""Diff inspection API endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from netconfigvault.core.diff_engine import DiffEngine
from netconfigvault.core.storage import StorageManager
from netconfigvault.inventory.loader import InventoryLoader
from netconfigvault.models.diff import DiffResult
from netconfigvault.settings import AppSettings

router = APIRouter()


@router.get("/{hostname}", response_model=DiffResult, summary="Get semantic diff between two latest backups")
def get_device_diff(hostname: str) -> DiffResult:
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()

    matched = [d for d in inv.devices if d.hostname.lower() == hostname.lower()]
    site = matched[0].site if matched else "default"

    storage = StorageManager(backup_dir=settings.backup_dir, git_enabled=False)
    backups = storage.list_backups(hostname, site)

    if len(backups) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Device '{hostname}' has {len(backups)} snapshot(s). At least 2 are required to compute a diff.",
        )

    prior_cfg = backups[-2].read_text(encoding="utf-8")
    latest_cfg = backups[-1].read_text(encoding="utf-8")

    diff_engine = DiffEngine()
    return diff_engine.compare(hostname, prior_cfg, latest_cfg, generate_html=True)


@router.get("/{hostname}/html", response_class=HTMLResponse, summary="View visual HTML diff in browser")
def get_device_diff_html(hostname: str) -> str:
    diff_res = get_device_diff(hostname)
    if not diff_res.html_diff:
        return "<h3>No configuration changes detected between recent snapshots.</h3>"
    return diff_res.html_diff
