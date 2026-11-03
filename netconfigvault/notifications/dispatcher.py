"""Alert dispatcher routing alerts to configured notification sinks."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from netconfigvault.settings import AppSettings

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Categorization for alert urgency."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Standardized event notification."""
    title: str
    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    hostname: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class AlertDispatcher:
    """Manages dispatching alerts to all active communication channels."""

    def __init__(self, settings: AppSettings):
        self.channels: List[Any] = []

        # Slack Channel
        if settings.slack_webhook_url:
            from netconfigvault.notifications.slack_notifier import SlackNotifier
            self.channels.append(SlackNotifier(webhook_url=settings.slack_webhook_url))
            logger.info("Slack alert channel registered.")

        # Email Channel
        if settings.smtp_server and settings.alert_email:
            from netconfigvault.notifications.email_notifier import EmailNotifier
            self.channels.append(
                EmailNotifier(
                    server=settings.smtp_server,
                    port=settings.smtp_port,
                    recipient=settings.alert_email,
                )
            )
            logger.info("SMTP email alert channel registered for %s.", settings.alert_email)

    def dispatch(self, alert: Alert) -> int:
        """Broadcast alert to all configured channels. Returns number of successful sends."""
        if not self.channels:
            logger.debug("No external notification channels configured. Alert logged: %s", alert.title)
            return 0

        dispatched_count = 0
        for channel in self.channels:
            try:
                if channel.send(alert):
                    dispatched_count += 1
            except Exception as e:
                logger.error("Exception in alert channel %s: %s", type(channel).__name__, e)

        return dispatched_count
