"""Inventory loader with strict validation and YAML parsing."""

import logging
from pathlib import Path
from typing import Union
import yaml
from pydantic import ValidationError

from netconfigvault.models.device import Inventory

logger = logging.getLogger(__name__)


class InventoryLoader:
    """Loads, validates, and manages device inventory from YAML definitions."""

    def __init__(self, inventory_path: Union[str, Path]):
        self.inventory_path = Path(inventory_path)

    def load(self) -> Inventory:
        """Parse the inventory file and construct the validated Inventory model."""
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"Inventory file not found: {self.inventory_path}")

        logger.debug("Parsing inventory definition from %s", self.inventory_path)
        try:
            with open(self.inventory_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error("YAML syntax error in inventory file %s: %s", self.inventory_path, e)
            raise ValueError(f"Invalid YAML in inventory file: {e}") from e

        if not isinstance(raw_data, dict) or "devices" not in raw_data:
            raise ValueError(f"Inventory file {self.inventory_path} must contain a root 'devices' list")

        try:
            inventory = Inventory(**raw_data)
        except ValidationError as e:
            logger.error("Schema validation failed for %s:\n%s", self.inventory_path, e)
            raise

        # Check for duplicate hostnames
        hostnames = [d.hostname for d in inventory.devices]
        duplicates = {name for name in hostnames if hostnames.count(name) > 1}
        if duplicates:
            raise ValueError(f"Duplicate hostnames detected in inventory: {', '.join(duplicates)}")

        active_count = len(inventory.get_enabled_devices())
        logger.info(
            "Successfully loaded %d devices (%d active, %d disabled) from %s",
            len(inventory.devices),
            active_count,
            len(inventory.devices) - active_count,
            self.inventory_path.name,
        )

        return inventory

