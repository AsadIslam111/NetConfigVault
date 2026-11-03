"""Device inventory management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from netconfigvault.api.schemas import DeviceResponse
from netconfigvault.inventory.loader import InventoryLoader
from netconfigvault.settings import AppSettings

router = APIRouter()


@router.get("", response_model=List[DeviceResponse], summary="List all inventory devices")
def get_devices(
    group: Optional[str] = Query(None, description="Filter by group tag"),
    site: Optional[str] = Query(None, description="Filter by site name"),
) -> List[DeviceResponse]:
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()

    devices = inv.devices
    if group:
        devices = [d for d in devices if group.lower() in [g.lower() for g in d.groups]]
    if site:
        devices = [d for d in devices if d.site.lower() == site.lower()]

    return [
        DeviceResponse(
            hostname=d.hostname,
            host=d.host,
            device_type=d.device_type.value,
            port=d.port,
            site=d.site,
            role=d.role,
            groups=d.groups,
            enabled=d.enabled,
        )
        for d in devices
    ]


@router.get("/{hostname}", response_model=DeviceResponse, summary="Get single device details")
def get_device(hostname: str) -> DeviceResponse:
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()

    matched = [d for d in inv.devices if d.hostname.lower() == hostname.lower()]
    if not matched:
        raise HTTPException(status_code=404, detail=f"Device '{hostname}' not found in inventory")

    d = matched[0]
    return DeviceResponse(
        hostname=d.hostname,
        host=d.host,
        device_type=d.device_type.value,
        port=d.port,
        site=d.site,
        role=d.role,
        groups=d.groups,
        enabled=d.enabled,
    )
