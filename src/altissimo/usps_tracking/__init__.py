"""USPS tracking & subscription client with optional Firestore persistence.

Install with ``pip install usps-tracking[firestore]`` to enable
Firedantic persistence models and repository.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

try:
    __version__ = version("usps-tracking")
except PackageNotFoundError:  # pragma: no cover - editable install without metadata
    __version__ = "0.1.0"

__all__ = [
    "USPSClient",
    "USPSCredentials",
    "USPSService",
    "USPSServiceSettings",
    "USPSSettings",
    "USPSTrackingDetail",
    "USPSTrackingEvent",
    "USPSTrackingSubscription",
    "USPSTrackingSummary",
    "__version__",
]


def __getattr__(name: str) -> Any:
    """Lazy attribute access — avoids import-time side effects."""
    if name in {"USPSClient", "USPSSettings"}:
        from .client import USPSClient
        from .settings import USPSSettings

        return USPSSettings if name == "USPSSettings" else USPSClient
    if name in {"USPSService", "USPSServiceSettings"}:
        from .service import USPSService
        from .settings import USPSServiceSettings

        return USPSServiceSettings if name == "USPSServiceSettings" else USPSService
    if name in {
        "USPSCredentials",
        "USPSTrackingDetail",
        "USPSTrackingEvent",
        "USPSTrackingSubscription",
        "USPSTrackingSummary",
    }:
        from . import models

        return getattr(models, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
