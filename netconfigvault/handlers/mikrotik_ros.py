"""Handler implementation for MikroTik RouterOS devices."""

import logging
import re
from typing import Any, Dict, List
from netconfigvault.handlers.base import BaseDeviceHandler

logger = logging.getLogger(__name__)

MIKROTIK_NOISE_PATTERNS = [
    re.compile(r"^#\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+by\s+RouterOS.*$", re.IGNORECASE),
    re.compile(r"^#\s*software id\s*=.*$", re.IGNORECASE),
]


class MikrotikROSHandler(BaseDeviceHandler):
    """Device handler for MikroTik RouterOS devices via SSH."""

    def get_config(self) -> str:
        if not self.connection:
            raise RuntimeError("Connection must be established before retrieving configuration.")

        # Default to compact export (standard for RouterOS configuration archives)
        commands = self.device.backup_commands or ["/export compact"]
        output_parts: List[str] = []

        for cmd in commands:
            logger.debug("[%s] Executing MikroTik export: %s", self.device.hostname, cmd)
            out = self.connection.send_command(
                cmd,
                read_timeout=self.command_timeout,
                strip_prompt=True,
                strip_command=True,
                expect_string=r"\[.*?\]\s*>",
            )
            output_parts.append(out)

        raw_config = "\n".join(output_parts)
        return self._sanitize_config(raw_config)

    def get_device_info(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "platform": self.device.device_type.value,
            "vendor": "MikroTik",
        }
        if not self.connection:
            return info

        try:
            res_out = self.connection.send_command("/system resource print", read_timeout=30)
            info["raw_resource"] = res_out[:1000]

            # Parse OS version
            ver_match = re.search(r"version:\s*([^\s\n]+)", res_out, re.IGNORECASE)
            if ver_match:
                info["os_version"] = ver_match.group(1)

            # Parse uptime
            uptime_match = re.search(r"uptime:\s*([^\n]+)", res_out, re.IGNORECASE)
            if uptime_match:
                info["uptime"] = uptime_match.group(1).strip()

            # Parse board name / architecture
            board_match = re.search(r"board-name:\s*([^\n]+)", res_out, re.IGNORECASE)
            if board_match:
                info["model"] = board_match.group(1).strip()

            # Parse identity
            identity_out = self.connection.send_command("/system identity print", read_timeout=15)
            id_match = re.search(r"name:\s*(.+)", identity_out, re.IGNORECASE)
            if id_match:
                info["identity"] = id_match.group(1).strip()
        except Exception as e:
            logger.warning("[%s] Failed to gather complete MikroTik device info: %s", self.device.hostname, e)

        return info

    def get_hostname_from_device(self) -> str:
        if not self.connection:
            return self.device.hostname

        try:
            identity_out = self.connection.send_command("/system identity print", read_timeout=15)
            match = re.search(r"name:\s*(.+)", identity_out, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        except Exception:
            pass

        # Fallback to prompt extraction [admin@Identity] >
        prompt = self.connection.find_prompt()
        prompt_match = re.search(r"\[.*@(.*?)\]", prompt)
        if prompt_match:
            return prompt_match.group(1).strip()

        return self.device.hostname

    def _sanitize_config(self, raw_config: str) -> str:
        """Strip volatile RouterOS export timestamps and IDs."""
        cleaned_lines: List[str] = []
        for line in raw_config.splitlines():
            if not any(pattern.match(line.strip()) for pattern in MIKROTIK_NOISE_PATTERNS):
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

