"""Credential manager facade to route requests to the active backend."""

import logging
from typing import Dict, Optional, Type
from netconfigvault.credentials.backends import (
    CredentialBackend,
    Credentials,
    DotenvBackend,
    EnvBackend,
)

logger = logging.getLogger(__name__)

BACKEND_MAP: Dict[str, Type[CredentialBackend]] = {
    "env": EnvBackend,
    "dotenv": DotenvBackend,
}


class CredentialManager:
    """Manages device authentication credential resolution."""

    def __init__(self, backend_name: str = "dotenv"):
        backend_cls = BACKEND_MAP.get(backend_name.lower())
        if not backend_cls:
            raise ValueError(
                f"Unsupported credential backend '{backend_name}'. "
                f"Valid backends: {list(BACKEND_MAP.keys())}"
            )
        self.backend = backend_cls()
        logger.debug("Credential manager initialized with backend: %s", backend_name)

    def get_for_device(self, hostname: str, credential_group: Optional[str] = None) -> Credentials:
        """Resolve credentials for a given device hostname."""
        return self.backend.get_credentials(hostname, credential_group)

