"""Compliance auditing API endpoints."""

from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from netconfigvault.compliance.engine import ComplianceEngine
from netconfigvault.compliance.reports import ComplianceReportGenerator
from netconfigvault.core.storage import StorageManager
from netconfigvault.inventory.loader import InventoryLoader
from netconfigvault.models.compliance import (
    ComplianceRule,
    DeviceComplianceReport,
    FleetComplianceSummary,
)
from netconfigvault.settings import AppSettings

router = APIRouter()


@router.get("/rules", response_model=List[ComplianceRule], summary="List all active compliance rules")
def list_compliance_rules() -> List[ComplianceRule]:
    settings = AppSettings.load()
    engine = ComplianceEngine(rules_dir=settings.compliance_rules_dir)
    return engine.rules


@router.get("/report", response_model=FleetComplianceSummary, summary="Fleet-wide compliance audit")
def get_fleet_compliance_report() -> FleetComplianceSummary:
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()
    storage = StorageManager(backup_dir=settings.backup_dir, git_enabled=False)
    engine = ComplianceEngine(rules_dir=settings.compliance_rules_dir)

    return engine.evaluate_fleet(inventory=inv, storage=storage)


@router.get("/{hostname}", response_model=DeviceComplianceReport, summary="Get device compliance report")
def get_device_compliance(hostname: str) -> DeviceComplianceReport:
    settings = AppSettings.load()
    inv = InventoryLoader(settings.inventory_path).load()

    matched = [d for d in inv.devices if d.hostname.lower() == hostname.lower()]
    if not matched:
        raise HTTPException(status_code=404, detail=f"Device '{hostname}' not found in inventory")

    device = matched[0]
    storage = StorageManager(backup_dir=settings.backup_dir, git_enabled=False)
    latest_config = storage.get_latest_config(device.hostname, device.site)

    if latest_config is None:
        raise HTTPException(status_code=400, detail=f"No backup configuration found for '{hostname}' to audit")

    engine = ComplianceEngine(rules_dir=settings.compliance_rules_dir)
    return engine.evaluate(device, latest_config)


@router.get("/{hostname}/html", response_class=HTMLResponse, summary="View visual HTML compliance report")
def get_device_compliance_html(hostname: str) -> str:
    report = get_device_compliance(hostname)
    return ComplianceReportGenerator.generate_html(report)
