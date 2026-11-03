"""Data models for configuration compliance and security baseline checking."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ComplianceSeverity(str, Enum):
    """Urgency level of a compliance check."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CheckType(str, Enum):
    """Evaluation strategy for a compliance rule."""
    MUST_CONTAIN = "must_contain"
    MUST_NOT_CONTAIN = "must_not_contain"
    REGEX_MATCH = "regex_match"


class ComplianceRule(BaseModel):
    """Definition of a compliance auditing rule."""
    id: str = Field(..., description="Unique rule code, e.g. CISCO-SEC-001")
    name: str = Field(..., description="Human-readable rule title")
    description: str = Field(..., description="Detailed context and rationale")
    severity: ComplianceSeverity = Field(default=ComplianceSeverity.MEDIUM)
    check_type: CheckType = Field(default=CheckType.MUST_CONTAIN)
    pattern: str = Field(..., description="Regular expression pattern to check against config")
    remediation: str = Field(default="", description="CLI commands required to fix violation")
    platforms: List[str] = Field(default_factory=list, description="Target platforms (e.g. cisco_ios)")


class RuleEvaluationResult(BaseModel):
    """Outcome of checking a single rule against a device's configuration."""
    rule: ComplianceRule
    passed: bool
    matched_lines: List[str] = Field(default_factory=list)
    message: str = ""


class DeviceComplianceReport(BaseModel):
    """Comprehensive compliance evaluation for a single device."""
    hostname: str
    device_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    total_rules: int = 0
    passed: int = 0
    failed: int = 0
    score_percent: float = 0.0
    critical_failures: List[RuleEvaluationResult] = Field(default_factory=list)
    results: List[RuleEvaluationResult] = Field(default_factory=list)


class FleetComplianceSummary(BaseModel):
    """Aggregate compliance status across all network devices."""
    generated_at: datetime = Field(default_factory=datetime.now)
    total_devices: int = 0
    compliant_devices: int = 0
    non_compliant_devices: int = 0
    overall_score: float = 0.0
    total_critical_violations: int = 0
    reports: List[DeviceComplianceReport] = Field(default_factory=list)
