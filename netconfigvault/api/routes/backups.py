"""Backup execution and retrieval endpoints."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from netconfigvault.api.schemas import (
    BackupFileItem,
    BackupRunRequest,
    LatestConfigResponse,
)
from netconfigvault.core.backup_engine import BackupEngine
from netconfigvault.core.storage import StorageManager
from netconfigvault.inventory.loader import InventoryLoader
from netconfigvault.models.backup import BackupRunSummary
from netconfigvault.settings import AppSettings

router = APIRouter()


@router.get("/{hostname}", response_model=List[BackupFileItem], summary="List snapshots for a device")
def list_device_backups(hostname: str) -> List[BackupFileItem]:
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()

    matched = [d for d in inv.devices if d.hostname.lower() == hostname.lower()]
    site = matched[0].site if matched else "default"

    storage = StorageManager(backup_dir=settings.backup_dir, git_enabled=False)
    backup_files = storage.list_backups(hostname, site)

    return [
        BackupFileItem(
            filename=f.name,
            timestamp=f.stem,
            size_bytes=f.stat().st_size,
        )
        for f in backup_files
    ]


@router.get("/{hostname}/latest", response_model=LatestConfigResponse, summary="Get latest running config")
def get_latest_config(hostname: str) -> LatestConfigResponse:
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()

    matched = [d for d in inv.devices if d.hostname.lower() == hostname.lower()]
    site = matched[0].site if matched else "default"

    storage = StorageManager(backup_dir=settings.backup_dir, git_enabled=False)
    cfg_text = storage.get_latest_config(hostname, site)

    if cfg_text is None:
        raise HTTPException(status_code=404, detail=f"No backup configuration found for '{hostname}'")

    return LatestConfigResponse(
        hostname=hostname,
        site=site,
        config_text=cfg_text,
        hash_sha256=StorageManager.compute_sha256(cfg_text),
    )


@router.get("/{hostname}/latest/raw", response_class=PlainTextResponse, summary="Download raw config file")
def get_raw_latest_config(hostname: str) -> str:
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()

    matched = [d for d in inv.devices if d.hostname.lower() == hostname.lower()]
    site = matched[0].site if matched else "default"

    storage = StorageManager(backup_dir=settings.backup_dir, git_enabled=False)
    cfg_text = storage.get_latest_config(hostname, site)

    if cfg_text is None:
        raise HTTPException(status_code=404, detail=f"No backup configuration found for '{hostname}'")

    return cfg_text


@router.post("/run", response_model=BackupRunSummary, summary="Trigger ad-hoc backup run")
def trigger_backup(request: BackupRunRequest) -> BackupRunSummary:
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()
    engine = BackupEngine(settings)

    summary = engine.run(
        inventory=inv,
        groups=request.groups,
        sites=request.sites,
    )
    return summary
