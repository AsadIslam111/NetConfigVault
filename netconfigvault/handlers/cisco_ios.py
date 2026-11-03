"""Handler implementation for Cisco IOS and IOS-XE devices."""

import logging
import re
from typing import Any, Dict, List
from netconfigvault.handlers.base import BaseDeviceHandler

logger = logging.getLogger(__name__)

CISCO_NOISE_PATTERNS = [
    re.compile(r"^!\s*Last configuration change at.*$", re.IGNORECASE),
    re.compile(r"^!\s*NVRAM config last updated at.*$", re.IGNORECASE),
    re.compile(r"^ntp clock-period\s+\d+.*$", re.IGNORECASE),
    re.compile(r"^!\s*No configuration change since last restart.*$", re.IGNORECASE),
]


class CiscoIOSHandler(BaseDeviceHandler):
    """Device handler for Cisco IOS and IOS-XE platforms."""

    def get_config(self) -> str:
        if not self.connection:
            raise RuntimeError("Connection must be established before retrieving configuration.")

        # Escalate to privileged exec if enable secret is present
        if self.credentials.enable_secret and not self.connection.check_enable_mode():
            logger.debug("[%s] Elevating to privileged exec mode", self.device.hostname)
            self.connection.enable()

        # Disable terminal pagination
        self.connection.send_command("terminal length 0")

        commands = self.device.backup_commands or ["show running-config"]
        output_parts: List[str] = []

        for cmd in commands:
            logger.debug("[%s] Executing config command: %s", self.device.hostname, cmd)
            out = self.connection.send_command(
                cmd,
                read_timeout=self.command_timeout,
                strip_prompt=True,
                strip_command=True,
            )
            output_parts.append(out)

        raw_config = "\n".join(output_parts)
        return self._sanitize_config(raw_config)

    def get_device_info(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "platform": self.device.device_type.value,
            "vendor": "Cisco",
        }
        if not self.connection:
            return info

        try:
            version_out = self.connection.send_command("show version", read_timeout=30)
            info["raw_version"] = version_out[:1000]

            # Parse Cisco version string
            ver_match = re.search(r"Cisco IOS Software.*?Version\s+([^\s,]+)", version_out, re.IGNORECASE)
            if ver_match:
                info["os_version"] = ver_match.group(1)

            # Parse uptime
            uptime_match = re.search(r"(?:uptime is|uptime:)\s*(.+?)(?:\n|$)", version_out, re.IGNORECASE)
            if uptime_match:
                info["uptime"] = uptime_match.group(1).strip()

            # Parse hardware model
            model_match = re.search(r"cisco\s+([A-Za-z0-9\-]+)\s+\(.*?\)\s+processor", version_out, re.IGNORECASE)
            if model_match:
                info["model"] = model_match.group(1)
        except Exception as e:
            logger.warning("[%s] Failed to gather complete device info: %s", self.device.hostname, e)

        return info

    def get_hostname_from_device(self) -> str:
        if not self.connection:
            return self.device.hostname
        prompt = self.connection.find_prompt()
        return re.sub(r"[#>]", "", prompt).strip()

    def _sanitize_config(self, raw_config: str) -> str:
        """Strip volatile Cisco comments and timestamp lines."""
        cleaned_lines: List[str] = []
        for line in raw_config.splitlines():
            if not any(pattern.match(line.strip()) for pattern in CISCO_NOISE_PATTERNS):
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

