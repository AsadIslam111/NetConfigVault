"""Application settings loader using Pydantic Settings and optional YAML config."""

import logging
from pathlib import Path
from typing import Any
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class AppSettings(BaseSettings):
    """Global configuration settings for NetConfigVault."""

    model_config = SettingsConfigDict(
        env_prefix="NCV_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Paths
    inventory_path: Path = Field(default=Path("config/inventory.yml"))
    settings_path: Path = Field(default=Path("config/settings.yml"))
    backup_dir: Path = Field(default=Path("backups"))
    compliance_rules_dir: Path = Field(default=Path("config/compliance_rules"))
    log_dir: Path = Field(default=Path("logs"))

    # Concurrency & Performance
    max_concurrent_devices: int = Field(default=5, ge=1, le=50)
    connection_timeout: int = Field(default=30, description="SSH connection timeout in seconds")
    command_timeout: int = Field(default=120, description="Command execution timeout in seconds")
    max_retries: int = Field(default=3, ge=1, le=10)

    # Version Control
    git_enabled: bool = Field(default=True)
    git_auto_commit: bool = Field(default=True)

    # Notifications & Integration (Tier 2/3)
    slack_webhook_url: str | None = None
    smtp_server: str | None = None
    smtp_port: int = 587
    alert_email: str | None = None

    # Credential management
    credential_backend: str = Field(default="dotenv")

    @classmethod
    def load(cls, config_path: Path | str = "config/settings.yml") -> "AppSettings":
        """Load settings from YAML file if available, layered with env vars."""
        path = Path(config_path)
        data: dict[str, Any] = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = yaml.safe_load(f)
                    if isinstance(content, dict):
                        data = content
            except Exception as e:
                logger.warning("Failed to parse settings YAML file at %s: %s", path, e)

        return cls(**data)

