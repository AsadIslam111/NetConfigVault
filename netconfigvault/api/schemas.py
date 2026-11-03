"""API request and response schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """API health status."""
    status: str = "ok"
    version: str
    total_managed_devices: int
    active_devices: int


class DeviceResponse(BaseModel):
    """Network device detail representation."""
    hostname: str
    host: str
    device_type: str
    port: int
    site: str
    role: str
    groups: List[str]
    enabled: bool


class BackupRunRequest(BaseModel):
    """Payload to trigger an ad-hoc backup run."""
    groups: Optional[List[str]] = Field(default=None, description="Optional group filter")
    sites: Optional[List[str]] = Field(default=None, description="Optional site filter")


class BackupFileItem(BaseModel):
    """Single historical backup file snapshot."""
    filename: str
    timestamp: str
    size_bytes: int


class LatestConfigResponse(BaseModel):
    """Current running configuration snapshot."""
    hostname: str
    site: str
    config_text: str
    hash_sha256: str
