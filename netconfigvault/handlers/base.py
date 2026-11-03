"""Abstract base class defining the contract for all network device handlers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

from netconfigvault.credentials.backends import Credentials
from netconfigvault.models.device import Device

logger = logging.getLogger(__name__)


class BaseDeviceHandler(ABC):
    """Abstract base handler for network device interaction via Netmiko.

    Subclasses must implement:
      - get_config()
      - get_device_info()
      - get_hostname_from_device()
    """

    def __init__(
        self,
        device: Device,
        credentials: Credentials,
        timeout: int = 30,
        command_timeout: int = 120,
    ):
        self.device = device
        self.credentials = credentials
        self.timeout = timeout
        self.command_timeout = command_timeout
        self.connection: Optional[Any] = None

    def connect(self) -> None:
        """Establish SSH session to the target network device."""
        logger.info("[%s] Connecting to %s:%d (%s)...", self.device.hostname, self.device.host, self.device.port, self.device.device_type.value)

        connect_params: Dict[str, Any] = {
            "device_type": self.device.device_type.value,
            "host": self.device.host,
            "port": self.device.port,
            "username": self.credentials.username,
            "timeout": self.timeout,
            "conn_timeout": self.timeout,
            "auth_timeout": self.timeout,
            "banner_timeout": self.timeout,
            "session_log_file_mode": "append",
        }

        # Key-based or password authentication
        if self.credentials.ssh_key_path:
            connect_params["use_keys"] = True
            connect_params["key_file"] = self.credentials.ssh_key_path
        elif self.credentials.password:
            connect_params["password"] = self.credentials.password

        # Enable secret for elevated privileges
        if self.credentials.enable_secret:
            connect_params["secret"] = self.credentials.enable_secret

        try:
            self.connection = ConnectHandler(**connect_params)
            logger.info("[%s] SSH session established successfully", self.device.hostname)
        except NetmikoAuthenticationException as err:
            logger.error("[%s] Authentication error: %s", self.device.hostname, err)
            raise
        except NetmikoTimeoutException as err:
            logger.error("[%s] Connection timeout: %s", self.device.hostname, err)
            raise
        except Exception as err:
            logger.error("[%s] Unexpected connection failure: %s", self.device.hostname, err)
            raise

    def disconnect(self) -> None:
        """Gracefully terminate SSH session."""
        if self.connection:
            try:
                self.connection.disconnect()
                logger.debug("[%s] SSH session terminated", self.device.hostname)
            except Exception as e:
                logger.debug("[%s] Error closing session: %s", self.device.hostname, e)
            finally:
                self.connection = None

    @abstractmethod
    def get_config(self) -> str:
        """Pull and return the running/active configuration text."""
        pass

    @abstractmethod
    def get_device_info(self) -> Dict[str, Any]:
        """Fetch metadata such as hardware model, OS version, uptime, and serial number."""
        pass

    @abstractmethod
    def get_hostname_from_device(self) -> str:
        """Query device prompt or system identity to discover its configured hostname."""
        pass

    def _sanitize_config(self, raw_config: str) -> str:
        """Strip volatile noise (e.g. timestamps, dynamic tokens) that cause false-positive diffs."""
        return raw_config.strip()

    def __enter__(self) -> "BaseDeviceHandler":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

