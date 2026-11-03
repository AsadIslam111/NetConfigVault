"""Compliance rule loading and validation."""

import logging
from pathlib import Path
from typing import List, Union
import yaml
from pydantic import ValidationError

from netconfigvault.models.compliance import ComplianceRule

logger = logging.getLogger(__name__)


class ComplianceRuleLoader:
    """Discovers and parses YAML compliance rule documents from disk."""

    def __init__(self, rules_dir: Union[str, Path] = "config/compliance_rules"):
        self.rules_dir = Path(rules_dir)

    def load_rules(self) -> List[ComplianceRule]:
        """Load and parse all compliance rules across active rule definition files."""
        if not self.rules_dir.exists():
            logger.warning("Compliance directory does not exist: %s", self.rules_dir)
            return []

        rules: List[ComplianceRule] = []
        rule_files = sorted(list(self.rules_dir.glob("*.yml")) + list(self.rules_dir.glob("*.yaml")))

        for rule_path in rule_files:
            logger.debug("Loading compliance rule set: %s", rule_path.name)
            try:
                with open(rule_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except Exception as e:
                logger.error("Failed to parse YAML file %s: %s", rule_path, e)
                continue

            if not isinstance(data, dict):
                continue

            metadata = data.get("metadata", {})
            default_platforms = metadata.get("applies_to", [])
            raw_rules = data.get("rules", [])

            for rule_dict in raw_rules:
                if not isinstance(rule_dict, dict):
                    continue
                # Inherit applies_to if platforms is not explicitly defined in the rule
                if "platforms" not in rule_dict or not rule_dict["platforms"]:
                    rule_dict["platforms"] = default_platforms

                try:
                    rule = ComplianceRule(**rule_dict)
                    rules.append(rule)
                except ValidationError as ve:
                    logger.warning("Skipping invalid rule in %s (%s): %s", rule_path.name, rule_dict.get("id"), ve)

        logger.info("Loaded %d compliance rules from %s", len(rules), self.rules_dir)
        return rules
