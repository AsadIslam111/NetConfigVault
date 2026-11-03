"""Compliance evaluation engine for network device configurations."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from netconfigvault.compliance.rules import ComplianceRuleLoader
from netconfigvault.core.storage import StorageManager
from netconfigvault.models.compliance import (
    CheckType,
    ComplianceRule,
    ComplianceSeverity,
    DeviceComplianceReport,
    FleetComplianceSummary,
    RuleEvaluationResult,
)
from netconfigvault.models.device import Device, Inventory

logger = logging.getLogger(__name__)


class ComplianceEngine:
    """Evaluates network configurations against security rules and generates compliance reports."""

    def __init__(
        self,
        rules_dir: Union[str, Path] = "config/compliance_rules",
        rules: Optional[List[ComplianceRule]] = None,
    ):
        if rules is not None:
            self.rules = rules
        else:
            loader = ComplianceRuleLoader(rules_dir=rules_dir)
            self.rules = loader.load_rules()

    def evaluate(self, device: Device, config_text: str) -> DeviceComplianceReport:
        """Audit a single device configuration against applicable rules."""
        platform_key = device.device_type.value
        applicable_rules = [
            r for r in self.rules
            if not r.platforms or platform_key in r.platforms
        ]

        report = DeviceComplianceReport(
            hostname=device.hostname,
            device_type=platform_key,
            timestamp=datetime.now(),
            total_rules=len(applicable_rules),
        )

        for rule in applicable_rules:
            result = self._check_rule(rule, config_text)
            report.results.append(result)

            if result.passed:
                report.passed += 1
            else:
                report.failed += 1
                if rule.severity == ComplianceSeverity.CRITICAL:
                    report.critical_failures.append(result)

        if report.total_rules > 0:
            report.score_percent = round((report.passed / report.total_rules) * 100, 1)

        logger.debug(
            "[%s] Compliance score: %.1f%% (%d/%d passed, %d critical failures)",
            device.hostname,
            report.score_percent,
            report.passed,
            report.total_rules,
            len(report.critical_failures),
        )

        return report

    def evaluate_fleet(
        self,
        inventory: Inventory,
        storage: StorageManager,
    ) -> FleetComplianceSummary:
        """Audit all enabled devices in the inventory using their latest configurations."""
        summary = FleetComplianceSummary()
        devices = inventory.get_enabled_devices()

        total_score_sum = 0.0
        devices_with_configs = 0

        for device in devices:
            latest_config = storage.get_latest_config(device.hostname, device.site)
            if latest_config is None:
                logger.warning("[%s] No backup configuration found for compliance audit", device.hostname)
                continue

            report = self.evaluate(device, latest_config)
            summary.reports.append(report)
            summary.total_critical_violations += len(report.critical_failures)

            if report.failed == 0 and report.total_rules > 0:
                summary.compliant_devices += 1
            else:
                summary.non_compliant_devices += 1

            total_score_sum += report.score_percent
            devices_with_configs += 1

        summary.total_devices = len(devices)
        if devices_with_configs > 0:
            summary.overall_score = round(total_score_sum / devices_with_configs, 1)

        return summary

    def _check_rule(self, rule: ComplianceRule, config_text: str) -> RuleEvaluationResult:
        """Check a single rule against device configuration text."""
        lines = config_text.splitlines()
        matched_lines: List[str] = []

        try:
            pattern = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)
        except re.error as err:
            logger.error("Invalid regex in rule %s ('%s'): %s", rule.id, rule.pattern, err)
            return RuleEvaluationResult(
                rule=rule,
                passed=False,
                message=f"Syntax error in rule regex: {err}",
            )

        # Check line-by-line or multiline
        for line in lines:
            if pattern.search(line.strip()):
                matched_lines.append(line.strip())

        # Determine pass/fail
        if rule.check_type == CheckType.MUST_CONTAIN:
            passed = len(matched_lines) > 0
            msg = (
                f"Compliant: matched '{matched_lines[0]}'"
                if passed
                else f"Violation: missing required pattern '{rule.pattern}'"
            )
        elif rule.check_type == CheckType.MUST_NOT_CONTAIN:
            passed = len(matched_lines) == 0
            msg = (
                "Compliant: prohibited pattern absent"
                if passed
                else f"Violation: found prohibited configuration '{matched_lines[0]}'"
            )
        elif rule.check_type == CheckType.REGEX_MATCH:
            passed = len(matched_lines) > 0
            msg = "Compliant: pattern matched" if passed else "Violation: pattern not found"
        else:
            passed = True
            msg = "Unknown check type (defaulted to pass)"

        return RuleEvaluationResult(
            rule=rule,
            passed=passed,
            matched_lines=matched_lines,
            message=msg,
        )
