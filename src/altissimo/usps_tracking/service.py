"""USPS tracking service.

All USPS business logic lives here.  Dependencies (client, repo) are
injected via constructor for testability.

The ``on_tracking_update`` callback hook lets consuming projects define
what happens when tracking data is updated (e.g. notify on delivery).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from .exceptions import USPSTrackingSubscriptionNotFoundError
from .models import (
    CreateUSPSSubscription,
    StatusCategory,
    TrackInfo,
    USPSSubscription,
    USPSSubscriptionAdminNotification,
    USPSSubscriptionFilterProperties,
    USPSSubscriptionNotification,
    USPSSubscriptionsResponse,
    USPSTrackingDetail,
    USPSTrackingSubscription,
)
from .repo import USPSTrackingRepo, USPSTrackingRepoProtocol
from .settings import USPSServiceSettings

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols for injectable dependencies
# ---------------------------------------------------------------------------


class USPSClientProtocol(Protocol):
    """Protocol for the USPS API client dependency."""

    def get_tracking_detail(self, tracking_number: str) -> USPSTrackingDetail: ...

    def list_subscriptions(self, tracking_number: str) -> USPSSubscriptionsResponse: ...

    def create_subscription(self, body: CreateUSPSSubscription) -> USPSSubscription: ...

    def get_subscription(self, usps_subscription_id: str) -> USPSSubscription: ...

    def delete_subscription(self, usps_subscription_id: str, etag: str) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class USPSService:
    """USPS business logic and orchestration.

    Usage::

        # Production — lazily creates real client & repo
        service = USPSService()

        # With tracking update callback
        service = USPSService(on_tracking_update=my_handler)

        # Testing — inject fakes
        service = USPSService(client=fake, repo=fake)
    """

    def __init__(
        self,
        *,
        client: USPSClientProtocol | None = None,
        repo: USPSTrackingRepoProtocol | None = None,
        settings: USPSServiceSettings | None = None,
        on_tracking_update: Callable[[USPSTrackingDetail, TrackInfo], None] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._repo = repo
        self._settings = settings
        self._on_tracking_update = on_tracking_update
        self._sleep_fn = sleep_fn or time.sleep

    def _get_client(self) -> USPSClientProtocol:
        if self._client is None:
            from .client import USPSClient

            self._client = USPSClient()
        return self._client

    def _get_repo(self) -> USPSTrackingRepoProtocol:
        if self._repo is None:
            self._repo = USPSTrackingRepo()
        return self._repo

    def _get_settings(self) -> USPSServiceSettings:
        if self._settings is None:
            self._settings = USPSServiceSettings.from_env()
        return self._settings

    # -----------------------------------------------------------------
    # Callback Processing
    # -----------------------------------------------------------------

    def process_subscriptions_callback(self, body: USPSSubscriptionNotification) -> dict[str, Any]:
        """Process a USPS Subscriptions v3 callback.

        Parses the ``TrackInfo`` from the callback payload, saves the
        tracking detail, and invokes the ``on_tracking_update`` callback
        if configured.
        """
        logger.info(
            "Processing Subscriptions callback: %s [%s]",
            body.subscriptionId,
            body.subscriptionType,
        )

        data = body.payload.get("TrackInfo")
        if not data:
            raise ValueError("TrackInfo not found in payload")
        logger.debug("TrackInfo Data: %s", data.get("ID", "unknown"))

        from pydantic_core import ValidationError

        try:
            track_info = TrackInfo(**data)
            logger.info("Tracking Number: %s [%s]: %s", track_info.ID, track_info.StatusCategory, track_info.Status)
        except ValidationError as e:
            logger.error("Error validating TrackInfo: %s", e)
            return {"status": "error", "detail": str(e)}

        try:
            detail = self.save_tracking_detail(track_info.ID)
        except Exception:
            logger.exception("Error saving Tracking Detail for %s", track_info.ID)
            return {"status": "error", "detail": f"Failed to save tracking detail for {track_info.ID}"}

        # Invoke the callback hook
        if self._on_tracking_update:
            try:
                self._on_tracking_update(detail, track_info)
            except Exception:
                logger.exception("Error in on_tracking_update callback for %s", track_info.ID)

        return {"status": "ok"}

    # -----------------------------------------------------------------
    # Tracking Detail Operations
    # -----------------------------------------------------------------

    def get_tracking_detail(self, tracking_number: str) -> USPSTrackingDetail:
        """Get a tracking detail from Firestore.

        Raises:
            USPSTrackingDetailNotFoundError: If not found.
        """
        logger.info("Getting USPS Tracking Detail: %s", tracking_number)
        return self._get_repo().get_tracking_detail(tracking_number)

    def list_tracking_details(self) -> list[USPSTrackingDetail]:
        """List all tracking details from Firestore."""
        logger.info("Listing USPS Tracking Details")
        return self._get_repo().list_tracking_details()

    def list_tracking_details_by_status_category(self, status: str) -> list[USPSTrackingDetail]:
        """Filter tracking details by status category string.

        Prefix with ``-`` to exclude (e.g. ``"-Delivered"`` returns all non-delivered).
        """
        normalized_status = status.strip()
        if normalized_status.startswith("-"):
            excluded = normalized_status[1:].title()
            return [detail for detail in self.list_tracking_details() if detail.status_category != excluded]
        required = normalized_status.title()
        return [detail for detail in self.list_tracking_details() if detail.status_category == required]

    def save_tracking_detail(self, tracking_number: str) -> USPSTrackingDetail:
        """Fetch tracking from the USPS API and save to Firestore."""
        logger.info("Saving USPS Tracking Detail: %s", tracking_number)
        usps_tracking_detail = self._get_client().get_tracking_detail(tracking_number)
        usps_tracking_detail.updated_at = datetime.now()
        self._get_repo().save_tracking_detail(usps_tracking_detail)
        return usps_tracking_detail

    def delete_tracking_detail(self, tracking_number: str) -> dict[str, Any]:
        """Delete a tracking detail from Firestore.

        Raises:
            USPSTrackingDetailNotFoundError: If not found.
        """
        logger.info("Deleting USPS Tracking Detail: %s", tracking_number)
        tracking_detail = self.get_tracking_detail(tracking_number)
        self._get_repo().delete_tracking_detail(tracking_detail)
        return {"id": tracking_number}

    def process_tracking_details(self) -> dict[str, Any]:
        """Re-fetch and persist all non-delivered tracking details."""
        logger.info("Processing USPS Tracking Details")
        for detail in sorted(self.list_tracking_details(), key=lambda x: x.updated_at or x.created_at):
            if StatusCategory.DELIVERED.value in detail.status:
                continue
            self.save_tracking_detail(detail.tracking_number)
            self._sleep_fn(1)
        logger.info("Done processing USPS Tracking Details")
        return {"status": "ok"}

    # -----------------------------------------------------------------
    # Subscription Operations
    # -----------------------------------------------------------------

    def create_tracking_subscription(self, tracking_number: str) -> USPSTrackingSubscription:
        """Create a USPS subscription and save in Firestore."""
        logger.info("Creating USPS Subscription for tracking number: %s", tracking_number)

        # Check for existing subscriptions
        try:
            subscriptions = self._get_client().list_subscriptions(tracking_number)
            if subscriptions.subscriptions:
                subscription = subscriptions.subscriptions[0]
                logger.debug("Found existing USPS Subscription: %s [%s]", subscription.subscriptionId, tracking_number)
                tracking_subscription = USPSTrackingSubscription.from_usps_subscription(subscription)
                self._get_repo().save_tracking_subscription(tracking_subscription)
                return tracking_subscription
        except Exception:
            logger.debug("No existing USPS Subscriptions found for %s", tracking_number)

        # Create new subscription
        logger.debug("Creating new USPS Subscription for tracking number: %s", tracking_number)
        settings = self._get_settings()
        body = CreateUSPSSubscription(
            listenerURL=settings.listener_url,
            secret=settings.subscription_secret,
            adminNotification=[USPSSubscriptionAdminNotification(email=settings.admin_notification_email)],
            filterProperties=USPSSubscriptionFilterProperties(
                trackingNumber=tracking_number,
                trackingEventTypes=["ALL"],
            ),
        )
        subscription = self._get_client().create_subscription(body)
        logger.debug("Subscription created: %s [%s]", subscription.subscriptionId, tracking_number)

        tracking_subscription = USPSTrackingSubscription.from_usps_subscription(subscription)
        self._get_repo().save_tracking_subscription(tracking_subscription)
        logger.info("Done creating USPS Subscription for: %s", tracking_number)
        return tracking_subscription

    def delete_tracking_subscription(self, usps_subscription_id: str) -> dict[str, Any]:
        """Delete a subscription from USPS API and Firestore."""
        logger.info("Deleting USPS Tracking Subscription: %s", usps_subscription_id)

        try:
            subscription = self._get_client().get_subscription(usps_subscription_id)
            if not subscription.etag:
                raise ValueError(f"USPS subscription {usps_subscription_id} has no etag")
            self._get_client().delete_subscription(usps_subscription_id, subscription.etag)
        except Exception:
            logger.exception("Error deleting USPS Subscription from API: %s", usps_subscription_id)

        try:
            tracking_subscription = self._get_repo().get_tracking_subscription(usps_subscription_id)
            self._get_repo().delete_tracking_subscription(tracking_subscription)
        except USPSTrackingSubscriptionNotFoundError:
            logger.warning("USPS Tracking Subscription not found in Firestore: %s", usps_subscription_id)

        logger.info("Done deleting USPS Tracking Subscription: %s", usps_subscription_id)
        return {"id": usps_subscription_id}

    def get_tracking_subscription(self, usps_subscription_id: str) -> USPSTrackingSubscription:
        """Get a tracking subscription from Firestore.

        Raises:
            USPSTrackingSubscriptionNotFoundError: If not found.
        """
        logger.info("Getting USPS Tracking Subscription: %s", usps_subscription_id)
        return self._get_repo().get_tracking_subscription(usps_subscription_id)

    def list_tracking_subscriptions(
        self,
        tracking_number: str | None = None,
    ) -> list[USPSTrackingSubscription]:
        """List tracking subscriptions from Firestore."""
        if tracking_number:
            logger.info("Listing USPS Tracking Subscriptions for: %s", tracking_number)
        return self._get_repo().list_tracking_subscriptions(tracking_number)

    def process_tracking_subscriptions(self) -> dict[str, Any]:
        """Reconcile subscriptions — remove for delivered, create for active."""
        logger.info("Processing USPS Tracking Subscriptions")

        tracking_details = {t.tracking_number: t for t in self._get_repo().list_tracking_details()}
        tracking_subscriptions = {t.tracking_number: t for t in self._get_repo().list_tracking_subscriptions()}

        # Remove subscriptions for delivered packages
        for tracking_number, subscription in tracking_subscriptions.items():
            if not tracking_number or not subscription.subscription_id:
                logger.warning("Skipping subscription with no tracking number or id: %s", subscription)
                continue
            if tracking_number not in tracking_details:
                logger.warning("Tracking number not found in details: %s", tracking_number)
                continue
            detail = tracking_details[tracking_number]
            if detail.status_category == StatusCategory.DELIVERED.value:
                logger.info("Deleting subscription for delivered package: %s", tracking_number)
                self.delete_tracking_subscription(subscription.subscription_id)

        # Create subscriptions for active (non-delivered) packages
        for tracking_number, detail in tracking_details.items():
            if not tracking_number:
                logger.warning("Skipping tracking detail with no id: %s", detail)
                continue
            if detail.status_category == StatusCategory.DELIVERED.value:
                continue
            if tracking_number not in tracking_subscriptions:
                logger.info("Creating subscription for: %s", tracking_number)
                self.create_tracking_subscription(tracking_number)

        logger.info("Done processing USPS Tracking Subscriptions")
        return {"status": "ok"}

    def update_tracking_subscription(self, usps_subscription_id: str) -> USPSTrackingSubscription:
        """Refresh a tracking subscription from the USPS API."""
        logger.info("Updating USPS Tracking Subscription: %s", usps_subscription_id)
        subscription = self._get_client().get_subscription(usps_subscription_id)
        tracking_subscription = USPSTrackingSubscription.from_usps_subscription(subscription)
        self._get_repo().save_tracking_subscription(tracking_subscription)
        return tracking_subscription
