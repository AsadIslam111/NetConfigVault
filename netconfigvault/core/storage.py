"""Storage manager for configuration backups with Git versioning."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from git import Repo, InvalidGitRepositoryError, GitCommandError
from netconfigvault.models.backup import BackupMetadata

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages filesystem storage and Git revision tracking for configuration archives."""

    def __init__(self, backup_dir: Union[str, Path] = "backups", git_enabled: bool = True):
        self.backup_dir = Path(backup_dir).resolve()
        self.git_enabled = git_enabled
        self.repo: Optional[Repo] = None

        self.backup_dir.mkdir(parents=True, exist_ok=True)

        if self.git_enabled:
            self._init_git_repo()

    def _init_git_repo(self) -> None:
        """Initialize or connect to existing Git repository in the backup root."""
        try:
            self.repo = Repo(self.backup_dir)
            logger.debug("Attached to existing Git repository at %s", self.backup_dir)
        except (InvalidGitRepositoryError, GitCommandError):
            try:
                self.repo = Repo.init(self.backup_dir)
                logger.info("Initialized new Git repository at %s", self.backup_dir)
            except Exception as e:
                logger.warning("Could not initialize Git repository at %s: %s", self.backup_dir, e)
                self.repo = None

        # Ensure git author is configured for commits if none is set
        if self.repo:
            with self.repo.config_writer() as config:
                if not config.has_section("user") or not config.has_option("user", "name"):
                    config.set_value("user", "name", "NetConfigVault Automation")
                    config.set_value("user", "email", "automation@netconfigvault.local")

    @staticmethod
    def compute_sha256(content: str) -> str:
        """Generate SHA-256 hash for configuration content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get_latest_config(self, hostname: str, site: str) -> Optional[str]:
        """Read the latest saved configuration snapshot for a device."""
        latest_file = self.backup_dir / site / hostname / "latest.cfg"
        if latest_file.exists():
            return latest_file.read_text(encoding="utf-8")
        return None

    def save_config(
        self,
        hostname: str,
        site: str,
        config_text: str,
        metadata: BackupMetadata,
        always_archive: bool = False,
    ) -> Path:
        """Write backup archive files and update the latest reference snapshot.

        By default, writes a new timestamped revision snapshot only if changes are detected,
        preventing duplicate archive clutter.
        """
        device_folder = self.backup_dir / site / hostname
        device_folder.mkdir(parents=True, exist_ok=True)

        timestamp_tag = metadata.timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        config_file = device_folder / f"{timestamp_tag}.cfg"
        meta_file = device_folder / f"{timestamp_tag}.json"
        latest_file = device_folder / "latest.cfg"

        # Change detection against previous latest.cfg
        prior_content = self.get_latest_config(hostname, site)
        is_changed = False
        if prior_content is not None:
            is_changed = self.compute_sha256(prior_content) != self.compute_sha256(config_text)
        else:
            is_changed = True  # Initial backup baseline

        metadata.changed = is_changed

        if is_changed or always_archive:
            # Write timestamped snapshot and metadata for the new revision
            config_file.write_text(config_text, encoding="utf-8")
            meta_file.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
            latest_file.write_text(config_text, encoding="utf-8")

            logger.info(
                "[%s] Config saved: %s (Status: %s)",
                hostname,
                config_file.name,
                "MODIFIED" if is_changed else "BASELINE",
            )
            return config_file
        else:
            logger.info("[%s] Config unchanged. Retaining existing baseline snapshot.", hostname)
            return latest_file

    def git_commit(self, commit_message: str) -> bool:
        """Commit all updated device configuration files to Git."""
        if not self.git_enabled or not self.repo:
            return False

        try:
            self.repo.git.add(A=True)
            # Check for changes (untracked or staged)
            has_changes = self.repo.is_dirty(untracked_files=True)
            if not has_changes:
                try:
                    has_changes = bool(self.repo.index.diff("HEAD"))
                except Exception:
                    # Initial commit when HEAD does not exist yet
                    has_changes = bool(self.repo.index.entries)

            if has_changes:
                self.repo.index.commit(commit_message)
                logger.info("Git commit recorded: '%s'", commit_message)
                return True
            else:
                logger.debug("No Git working tree changes to commit.")
                return False
        except Exception as err:
            logger.error("Failed to commit configuration changes to Git: %s", err)
            return False
