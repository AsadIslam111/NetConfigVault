"""Backup result and metadata models."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


class BackupStatus(str, Enum):
    """Execution status of a device backup attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    AUTH_FAILED = "auth_failed"


class BackupMetadata(BaseModel):
    """Metadata recorded with every configuration snapshot."""
    hostname: str
    host: str
    device_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = Field(default=0.0, description="Collection latency in seconds")
    config_size_bytes: int = Field(default=0, description="Payload size in bytes")
    config_hash: str = Field(description="SHA-256 integrity hash")
    device_info: dict[str, Any] = Field(default_factory=dict, description="Hardware, OS version, uptime")
    changed: bool = Field(default=False, description="Flag indicating deviation from prior snapshot")


class BackupResult(BaseModel):
    """Outcome for a specific device during a backup execution."""
    device_hostname: str
    status: BackupStatus
    message: str = ""
    config_path: Path | None = None
    metadata: BackupMetadata | None = None
    error: str | None = None
    attempts: int = 1


class BackupRunSummary(BaseModel):
    """Consolidated metrics for an entire backup run batch."""
    run_id: str
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    total_devices: int = 0
    successful: int = 0
    failed: int = 0
    changed: int = 0
    skipped: int = 0
    results: list[BackupResult] = Field(default_factory=list)

