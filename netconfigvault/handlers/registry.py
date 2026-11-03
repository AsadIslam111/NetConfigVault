"""Dynamic registry mapping device types to their respective handler classes."""

import logging
from typing import Dict, Type
from netconfigvault.handlers.base import BaseDeviceHandler
from netconfigvault.handlers.cisco_ios import CiscoIOSHandler
from netconfigvault.handlers.mikrotik_ros import MikrotikROSHandler
from netconfigvault.models.device import DeviceType

logger = logging.getLogger(__name__)

# Primary handler registry
_HANDLER_REGISTRY: Dict[DeviceType, Type[BaseDeviceHandler]] = {
    DeviceType.CISCO_IOS: CiscoIOSHandler,
    DeviceType.CISCO_XE: CiscoIOSHandler,
    DeviceType.MIKROTIK_ROUTEROS: MikrotikROSHandler,
}


def register_handler(device_type: DeviceType, handler_class: Type[BaseDeviceHandler]) -> None:
    """Register a new vendor handler class for a device type."""
    logger.debug("Registering handler %s for %s", handler_class.__name__, device_type.value)
    _HANDLER_REGISTRY[device_type] = handler_class


def get_handler(device_type: DeviceType) -> Type[BaseDeviceHandler]:
    """Retrieve the registered handler class for a given device type."""
    handler = _HANDLER_REGISTRY.get(device_type)
    if not handler:
        raise ValueError(
            f"No handler registered for device type '{device_type.value}'. "
            f"Registered platforms: {[dt.value for dt in _HANDLER_REGISTRY.keys()]}"
        )
    return handler

