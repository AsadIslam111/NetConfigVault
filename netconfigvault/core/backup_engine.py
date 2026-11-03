"""Backup engine orchestrating multi-vendor network configuration extraction."""

import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

from netconfigvault.core.storage import StorageManager
from netconfigvault.credentials.manager import CredentialManager
from netconfigvault.handlers.registry import get_handler
from netconfigvault.models.backup import (
    BackupMetadata,
    BackupResult,
    BackupRunSummary,
    BackupStatus,
)
from netconfigvault.models.device import Device, Inventory
from netconfigvault.settings import AppSettings

logger = logging.getLogger(__name__)


class BackupEngine:
    """Orchestrates configuration collection, validation, and storage across inventory devices."""

    def __init__(
        self,
        settings: AppSettings,
        storage: Optional[StorageManager] = None,
        credential_manager: Optional[CredentialManager] = None,
    ):
        self.settings = settings
        self.storage = storage or StorageManager(
            backup_dir=settings.backup_dir,
            git_enabled=settings.git_enabled,
        )
        self.credential_manager = credential_manager or CredentialManager(
            backend_name=settings.credential_backend
        )

    def run(
        self,
        inventory: Inventory,
        groups: Optional[List[str]] = None,
        sites: Optional[List[str]] = None,
    ) -> BackupRunSummary:
        """Execute configuration backups for all targeted devices."""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        started_at = datetime.now()

        # Filter targeted active devices
        devices = inventory.get_enabled_devices()
        if groups:
            groups_lower = [g.lower() for g in groups]
            devices = [d for d in devices if any(g.lower() in groups_lower for g in d.groups)]
        if sites:
            sites_lower = [s.lower() for s in sites]
            devices = [d for d in devices if d.site.lower() in sites_lower]

        summary = BackupRunSummary(
            run_id=run_id,
            started_at=started_at,
            total_devices=len(devices),
        )

        logger.info("Initiating backup run '%s' across %d device(s)...", run_id, len(devices))
        if not devices:
            summary.completed_at = datetime.now()
            return summary

        # Execute in parallel or sequential based on concurrency settings
        results: List[BackupResult] = []
        if self.settings.max_concurrent_devices > 1 and len(devices) > 1:
            results = self._run_concurrent(devices)
        else:
            results = [self._backup_device_with_retries(d) for d in devices]

        # Collate summary metrics
        for res in results:
            summary.results.append(res)
            if res.status == BackupStatus.SUCCESS:
                summary.successful += 1
                if res.metadata and res.metadata.changed:
                    summary.changed += 1
            elif res.status in (BackupStatus.FAILED, BackupStatus.AUTH_FAILED, BackupStatus.TIMEOUT):
                summary.failed += 1
            elif res.status == BackupStatus.SKIPPED:
                summary.skipped += 1

        summary.completed_at = datetime.now()

        # Automatic Git commit for the batch
        if self.settings.git_auto_commit and summary.successful > 0:
            commit_msg = (
                f"Backup run {run_id} | "
                f"Total: {summary.total_devices}, "
                f"OK: {summary.successful}, "
                f"Changed: {summary.changed}, "
                f"Failed: {summary.failed}"
            )
            self.storage.git_commit(commit_msg)

        logger.info(
            "Completed backup run '%s': %d OK, %d Changed, %d Failed (Total %d)",
            run_id,
            summary.successful,
            summary.changed,
            summary.failed,
            summary.total_devices,
        )

        return summary

    def _backup_device_with_retries(self, device: Device) -> BackupResult:
        """Attempt device backup with exponential backoff on transient errors."""
        last_error = None
        last_status = BackupStatus.FAILED

        for attempt in range(1, self.settings.max_retries + 1):
            try:
                return self._collect_device_config(device, attempt)
            except NetmikoAuthenticationException as err:
                logger.error("[%s] Authentication error on attempt %d: %s", device.hostname, attempt, err)
                # Auth errors are rarely transient, abort retrying
                return BackupResult(
                    device_hostname=device.hostname,
                    status=BackupStatus.AUTH_FAILED,
                    error=f"Authentication failure: {err}",
                    attempts=attempt,
                )
            except NetmikoTimeoutException as err:
                last_error = str(err)
                last_status = BackupStatus.TIMEOUT
                logger.warning("[%s] Timeout on attempt %d/%d: %s", device.hostname, attempt, self.settings.max_retries, err)
            except Exception as err:
                last_error = str(err)
                last_status = BackupStatus.FAILED
                logger.warning("[%s] Backup failure on attempt %d/%d: %s", device.hostname, attempt, self.settings.max_retries, err)

            if attempt < self.settings.max_retries:
                backoff_wait = min(2 ** attempt, 10)
                logger.debug("[%s] Waiting %ds before next retry...", device.hostname, backoff_wait)
                time.sleep(backoff_wait)

        return BackupResult(
            device_hostname=device.hostname,
            status=last_status,
            error=last_error,
            attempts=self.settings.max_retries,
        )

    def _collect_device_config(self, device: Device, attempt: int) -> BackupResult:
        """Connect to device via vendor handler, extract config & metadata, and store."""
        t0 = time.time()

        credentials = self.credential_manager.get_for_device(
            device.hostname, device.credential_group
        )
        handler_cls = get_handler(device.device_type)
        handler = handler_cls(
            device=device,
            credentials=credentials,
            timeout=self.settings.connection_timeout,
            command_timeout=self.settings.command_timeout,
        )

        with handler:
            config_text = handler.get_config()
            device_info = handler.get_device_info()

        elapsed_seconds = round(time.time() - t0, 2)
        config_bytes = config_text.encode("utf-8")
        config_hash = hashlib.sha256(config_bytes).hexdigest()

        metadata = BackupMetadata(
            hostname=device.hostname,
            host=device.host,
            device_type=device.device_type.value,
            timestamp=datetime.now(),
            duration_seconds=elapsed_seconds,
            config_size_bytes=len(config_bytes),
            config_hash=config_hash,
            device_info=device_info,
        )

        saved_path = self.storage.save_config(
            hostname=device.hostname,
            site=device.site,
            config_text=config_text,
            metadata=metadata,
        )

        return BackupResult(
            device_hostname=device.hostname,
            status=BackupStatus.SUCCESS,
            config_path=saved_path,
            metadata=metadata,
            attempts=attempt,
            message="Configuration retrieved and saved successfully.",
        )

    def _run_concurrent(self, devices: List[Device]) -> List[BackupResult]:
        """Execute backups concurrently using a managed ThreadPoolExecutor."""
        results: List[BackupResult] = []
        max_workers = min(self.settings.max_concurrent_devices, len(devices))
        logger.debug("Running concurrent backup batch with %d worker threads", max_workers)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._backup_device_with_retries, dev): dev
                for dev in devices
            }
            for future in as_completed(future_map):
                dev = future_map[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    logger.critical("[%s] Unhandled exception in worker thread: %s", dev.hostname, exc, exc_info=True)
                    results.append(
                        BackupResult(
                            device_hostname=dev.hostname,
                            status=BackupStatus.FAILED,
                            error=f"Worker exception: {exc}",
                        )
                    )

        return results

