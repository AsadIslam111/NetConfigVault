"""Slack incoming webhook notification channel."""

import logging
from typing import Any, Dict
import requests

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Delivers formatted alert cards to a Slack channel via webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, alert: Any) -> bool:
        """Post the alert payload to the configured Slack webhook."""
        # Color coding by severity
        color_map = {
            "critical": "#e11d48",  # Red
            "warning": "#f59e0b",   # Amber
            "info": "#10b981",      # Green
        }
        severity_value = getattr(alert.severity, "value", str(alert.severity)).lower()
        color = color_map.get(severity_value, "#3b82f6")

        # Build Slack attachment
        fields = []
        if alert.hostname:
            fields.append({"title": "Device", "value": alert.hostname, "short": True})
        fields.append({"title": "Severity", "value": severity_value.upper(), "short": True})

        if alert.details:
            for k, v in alert.details.items():
                fields.append({"title": str(k).replace("_", " ").title(), "value": str(v), "short": True})

        payload: Dict[str, Any] = {
            "attachments": [
                {
                    "fallback": f"[{severity_value.upper()}] {alert.title}",
                    "color": color,
                    "title": alert.title,
                    "text": alert.message,
                    "fields": fields,
                    "footer": "NetConfigVault Network Automation",
                }
            ]
        }

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.debug("Slack notification successfully dispatched for: %s", alert.title)
                return True
            else:
                logger.warning("Slack webhook returned HTTP %d: %s", resp.status_code, resp.text)
                return False
        except Exception as err:
            logger.error("Failed to post notification to Slack: %s", err)
            return False
