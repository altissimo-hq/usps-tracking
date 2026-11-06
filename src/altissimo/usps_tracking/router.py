"""USPS webhook FastAPI router.

Thin adapter — delegates all business logic to
:class:`~usps_tracking.service.USPSService`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter

from .service import USPSService

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from .models import TrackInfo, USPSSubscriptionNotification, USPSTrackingDetail

logger = logging.getLogger(__name__)


def create_usps_router(
    *,
    on_tracking_update: Callable[[USPSTrackingDetail, TrackInfo], None] | None = None,
    tags: Sequence[str] | None = None,
) -> APIRouter:
    """Create a USPS webhook router with an optional tracking update callback.

    Usage::

        from altissimo.usps_tracking.router import create_usps_router

        def handle_update(detail, track_info):
            if track_info.StatusCategory == "Delivered":
                # project-specific delivery logic
                ...

        app.include_router(create_usps_router(on_tracking_update=handle_update))
    """
    router = APIRouter(tags=list(tags) if tags else ["USPS"])
    service = USPSService(on_tracking_update=on_tracking_update)

    @router.post("/subscriptions")
    async def subscriptions_callback(body: USPSSubscriptionNotification) -> dict[str, Any]:
        """Receive USPS Subscriptions v3 notification."""
        logger.info(
            "Received USPS subscription notification: %s [%s]",
            body.subscriptionId,
            body.subscriptionType,
        )
        return service.process_subscriptions_callback(body)

    return router


# Convenience: a plain router with no callback for simple setups
router = create_usps_router()
