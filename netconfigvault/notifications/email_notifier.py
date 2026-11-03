"""SMTP email notification channel."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Delivers formatted alert emails over SMTP."""

    def __init__(
        self,
        server: str,
        port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        recipient: Optional[str] = None,
        sender: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.server = server
        self.port = port
        self.username = username
        self.password = password
        self.recipient = recipient
        self.sender = sender or username or "netconfigvault@localhost"
        self.use_tls = use_tls

    def send(self, alert: Any) -> bool:
        if not self.recipient:
            logger.warning("Email recipient not configured. Skipping email dispatch.")
            return False

        subject = f"[NetConfigVault Alert - {str(alert.severity).upper()}] {alert.title}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = self.recipient

        # Plain text fallback
        text_body = f"""NetConfigVault Alert Notification
----------------------------------
Severity: {alert.severity}
Device:   {alert.hostname or 'N/A'}
Title:    {alert.title}

Details:
{alert.message}
"""
        msg.attach(MIMEText(text_body, "plain"))

        # HTML formatting
        html_body = f"""<html>
<body style="font-family: Arial, sans-serif; background-color: #f8fafc; padding: 20px;">
    <div style="background: white; border-radius: 8px; padding: 24px; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0;">
        <h2 style="color: #0f172a; margin-top: 0;">{alert.title}</h2>
        <p><strong>Device:</strong> {alert.hostname or 'N/A'}</p>
        <p><strong>Severity:</strong> <span style="text-transform: uppercase;">{alert.severity}</span></p>
        <div style="background: #f1f5f9; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px;">
            {alert.message.replace(chr(10), '<br>')}
        </div>
    </div>
</body>
</html>"""
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.server, self.port, timeout=15) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.sendmail(self.sender, [self.recipient], msg.as_string())
            logger.debug("Email notification dispatched to %s for: %s", self.recipient, alert.title)
            return True
        except Exception as err:
            logger.error("Failed to transmit email notification via %s:%d: %s", self.server, self.port, err)
            return False
