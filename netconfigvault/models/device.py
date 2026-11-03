"""Device inventory models and validations."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    """Supported network device types (compatible with Netmiko device types)."""
    CISCO_IOS = "cisco_ios"
    CISCO_XE = "cisco_xe"
    MIKROTIK_ROUTEROS = "mikrotik_routeros"


class DeviceGroup(str, Enum):
    """Common device classifications."""
    CORE = "core"
    DISTRIBUTION = "distribution"
    ACCESS = "access"
    EDGE = "edge"
    BRANCH = "branch"
    PRODUCTION = "production"
    LAB = "lab"
    CRITICAL = "critical"


class Device(BaseModel):
    """Represents a single manageable network device."""
    hostname: str = Field(..., description="Unique device identifier (e.g. core-rtr-01)")
    host: str = Field(..., description="IP address or resolvable FQDN")
    device_type: DeviceType = Field(..., description="Netmiko driver platform identifier")
    port: int = Field(default=22, ge=1, le=65535, description="SSH port")
    site: str = Field(default="default", description="Physical or logical location")
    role: str = Field(default="router", description="Device role: core-router, switch, edge-gw")
    groups: list[str] = Field(default_factory=list, description="Categorization tags")
    enabled: bool = Field(default=True, description="Whether backups are active for this device")

    # Optional overrides
    credential_group: str | None = Field(default=None, description="Key for credential group override")
    backup_commands: list[str] | None = Field(
        default=None,
        description="Override default platform commands (e.g. custom /export parameters)"
    )


class Inventory(BaseModel):
    """Collection container for all network devices."""
    devices: list[Device]

    def get_enabled_devices(self) -> list[Device]:
        """Return only active devices."""
        return [d for d in self.devices if d.enabled]

    def filter_by_group(self, group: str) -> list[Device]:
        """Filter enabled devices by group tag."""
        return [d for d in self.devices if d.enabled and group.lower() in [g.lower() for g in d.groups]]

    def filter_by_site(self, site: str) -> list[Device]:
        """Filter enabled devices by site."""
        return [d for d in self.devices if d.enabled and d.site.lower() == site.lower()]

    def filter_by_platform(self, device_type: DeviceType) -> list[Device]:
        """Filter enabled devices by platform."""
        return [d for d in self.devices if d.enabled and d.device_type == device_type]

