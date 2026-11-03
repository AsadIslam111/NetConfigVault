"""Credential storage backends supporting environment variables, .env, and overrides."""

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class Credentials:
    """Device authentication credentials."""
    username: str
    password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    enable_secret: Optional[str] = None


class CredentialBackend(ABC):
    """Abstract interface for credential providers."""

    @abstractmethod
    def get_credentials(self, device_hostname: str, credential_group: Optional[str] = None) -> Credentials:
        """Resolve credentials for a device."""
        pass


def _sanitize_env_key(key: str) -> str:
    """Transform hostname or group into standard ENV key format (e.g. core-rtr-01 -> CORE_RTR_01)."""
    return re.sub(r"[^A-Za-z0-9]", "_", key).upper()


class EnvBackend(CredentialBackend):
    """Retrieves credentials from system environment variables.

    Lookup hierarchy:
    1. Device-specific: NCV_<HOSTNAME>_USERNAME / PASSWORD / SSH_KEY / ENABLE_SECRET
    2. Group-specific: NCV_GROUP_<GROUP>_USERNAME / PASSWORD / SSH_KEY / ENABLE_SECRET
    3. Global defaults: NCV_SSH_USERNAME / NCV_SSH_PASSWORD / NCV_SSH_KEY_PATH / NCV_ENABLE_SECRET
    """

    def get_credentials(self, device_hostname: str, credential_group: Optional[str] = None) -> Credentials:
        dev_prefix = f"NCV_{_sanitize_env_key(device_hostname)}"

        # 1. Device specific check
        username = os.getenv(f"{dev_prefix}_USERNAME")
        password = os.getenv(f"{dev_prefix}_PASSWORD")
        ssh_key = os.getenv(f"{dev_prefix}_SSH_KEY") or os.getenv(f"{dev_prefix}_SSH_KEY_PATH")
        enable_secret = os.getenv(f"{dev_prefix}_ENABLE_SECRET")

        # 2. Credential group check if not found
        if not username and credential_group:
            grp_prefix = f"NCV_GROUP_{_sanitize_env_key(credential_group)}"
            username = os.getenv(f"{grp_prefix}_USERNAME")
            password = os.getenv(f"{grp_prefix}_PASSWORD")
            ssh_key = os.getenv(f"{grp_prefix}_SSH_KEY") or os.getenv(f"{grp_prefix}_SSH_KEY_PATH")
            enable_secret = os.getenv(f"{grp_prefix}_ENABLE_SECRET")

        # 3. Global default fallback
        username = username or os.getenv("NCV_SSH_USERNAME")
        password = password or os.getenv("NCV_SSH_PASSWORD")
        ssh_key = ssh_key or os.getenv("NCV_SSH_KEY_PATH")
        enable_secret = enable_secret or os.getenv("NCV_ENABLE_SECRET")

        if not username:
            raise ValueError(
                f"No SSH username found for device '{device_hostname}'. "
                f"Define {dev_prefix}_USERNAME or global NCV_SSH_USERNAME."
            )

        return Credentials(
            username=username,
            password=password,
            ssh_key_path=ssh_key,
            enable_secret=enable_secret,
        )


class DotenvBackend(EnvBackend):
    """Loads environment configuration from a .env file before resolving credentials."""

    def __init__(self, dotenv_path: Optional[str] = None):
        if dotenv_path and os.path.exists(dotenv_path):
            load_dotenv(dotenv_path, override=False)
            logger.debug("Loaded .env from explicit path %s", dotenv_path)
        else:
            load_dotenv(override=False)
            logger.debug("Loaded .env from default lookup path")

