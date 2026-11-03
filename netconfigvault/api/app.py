"""FastAPI application factory for NetConfigVault."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from netconfigvault import __version__
from netconfigvault.api.routes import backups, compliance, devices, diffs
from netconfigvault.api.schemas import HealthResponse
from netconfigvault.inventory.loader import InventoryLoader
from netconfigvault.settings import AppSettings


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    app = FastAPI(
        title="NetConfigVault REST API",
        description=(
            "Enterprise Network Configuration Backup, Semantic Change Detection, "
            "and Automated Compliance Auditing API for Cisco IOS and MikroTik RouterOS."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Enable CORS for dashboards / third-party frontends
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root health endpoint
    @app.get("/api/health", response_model=HealthResponse, tags=["Health"])
    def health_check() -> HealthResponse:
        settings = AppSettings.load()
        inv = InventoryLoader(settings.inventory_path).load()
        return HealthResponse(
            version=__version__,
            total_managed_devices=len(inv.devices),
            active_devices=len(inv.get_enabled_devices()),
        )

    # Mount domain routers
    app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
    app.include_router(backups.router, prefix="/api/backups", tags=["Backups"])
    app.include_router(diffs.router, prefix="/api/diffs", tags=["Diffs"])
    app.include_router(compliance.router, prefix="/api/compliance", tags=["Compliance"])

    return app


app = create_app()
