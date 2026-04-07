"""USPS tracking test fixtures."""

from __future__ import annotations

from datetime import datetime

import pytest

from usps_tracking.exceptions import (
    USPSClientError,
    USPSTrackingDetailNotFoundError,
    USPSTrackingSubscriptionNotFoundError,
)
from usps_tracking.models import (
    CreateUSPSSubscription,
    USPSSubscription,
    USPSSubscriptionsResponse,
    USPSTrackingDetail,
    USPSTrackingEvent,
    USPSTrackingSubscription,
)


class FakeUSPSTrackingRepo:
    """In-memory fake for unit tests."""

    def __init__(self) -> None:
        self._details: dict[str, USPSTrackingDetail] = {}
        self._subscriptions: dict[str, USPSTrackingSubscription] = {}

    def get_tracking_detail(self, tracking_number: str) -> USPSTrackingDetail:
        if tracking_number not in self._details:
            raise USPSTrackingDetailNotFoundError(f"Not found: {tracking_number}")
        return self._details[tracking_number]

    def list_tracking_details(self) -> list[USPSTrackingDetail]:
        return list(self._details.values())

    def save_tracking_detail(self, tracking_detail: USPSTrackingDetail) -> None:
        self._details[tracking_detail.tracking_number] = tracking_detail

    def delete_tracking_detail(self, tracking_detail: USPSTrackingDetail) -> None:
        if tracking_detail.tracking_number not in self._details:
            raise USPSTrackingDetailNotFoundError(f"Not found: {tracking_detail.tracking_number}")
        del self._details[tracking_detail.tracking_number]

    def get_tracking_subscription(self, usps_subscription_id: str) -> USPSTrackingSubscription:
        if usps_subscription_id not in self._subscriptions:
            raise USPSTrackingSubscriptionNotFoundError(f"Not found: {usps_subscription_id}")
        return self._subscriptions[usps_subscription_id]

    def list_tracking_subscriptions(self, tracking_number: str | None = None) -> list[USPSTrackingSubscription]:
        if tracking_number:
            return [s for s in self._subscriptions.values() if s.tracking_number == tracking_number]
        return list(self._subscriptions.values())

    def save_tracking_subscription(self, tracking_subscription: USPSTrackingSubscription) -> None:
        self._subscriptions[tracking_subscription.subscription_id] = tracking_subscription

    def delete_tracking_subscription(self, tracking_subscription: USPSTrackingSubscription) -> None:
        if tracking_subscription.subscription_id not in self._subscriptions:
            raise USPSTrackingSubscriptionNotFoundError(f"Not found: {tracking_subscription.subscription_id}")
        del self._subscriptions[tracking_subscription.subscription_id]


class FakeUSPSClient:
    """Fake USPS API client for unit tests."""

    def __init__(self) -> None:
        self._tracking_details: dict[str, USPSTrackingDetail] = {}
        self._subscriptions: dict[str, USPSSubscription] = {}
        self._subscriptions_by_tracking: dict[str, list[USPSSubscription]] = {}

    def add_tracking_detail(self, tracking_number: str, detail: USPSTrackingDetail) -> None:
        self._tracking_details[tracking_number] = detail

    def get_tracking_detail(self, tracking_number: str) -> USPSTrackingDetail:
        if tracking_number not in self._tracking_details:
            raise USPSClientError(f"Tracking not found: {tracking_number}")
        return self._tracking_details[tracking_number]

    def list_subscriptions(self, tracking_number: str) -> USPSSubscriptionsResponse:
        subs = self._subscriptions_by_tracking.get(tracking_number, [])
        return USPSSubscriptionsResponse(subscriptions=subs, metadata={})

    def create_subscription(self, body: CreateUSPSSubscription) -> USPSSubscription:
        sub = USPSSubscription(
            subscriptionId=f"sub-{body.filterProperties.trackingNumber}",
            listenerURL=body.listenerURL,
            secret=body.secret,
            status="ENABLED",
            statusReason="Created",
            adminNotification=body.adminNotification,
            creationTimestamp=datetime.now(),
            statusChangeTimestamp=datetime.now(),
            expirationTimestamp=datetime.now(),
            filterProperties=body.filterProperties,
            etag="test-etag",
        )
        return sub

    def get_subscription(self, usps_subscription_id: str) -> USPSSubscription:
        if usps_subscription_id not in self._subscriptions:
            raise USPSClientError(f"Subscription not found: {usps_subscription_id}")
        return self._subscriptions[usps_subscription_id]

    def delete_subscription(self, usps_subscription_id: str, etag: str) -> dict:
        return {"status": "ok"}


@pytest.fixture()
def fake_repo():
    """Provide a fresh FakeUSPSTrackingRepo for each test."""
    return FakeUSPSTrackingRepo()


@pytest.fixture()
def fake_client():
    """Provide a fresh FakeUSPSClient for each test."""
    return FakeUSPSClient()


def _make_tracking_detail(
    tracking_number: str = "9400111899223456789012",
    status: str = "In Transit",
    status_category: str = "In Transit",
) -> USPSTrackingDetail:
    """Helper to build a USPSTrackingDetail for tests."""
    return USPSTrackingDetail(
        tracking_number=tracking_number,
        status=status,
        status_category=status_category,
        status_summary=f"Package is {status}",
        mail_piece_intake_date=datetime.now(),
        tracking_events=[
            USPSTrackingEvent(
                event_type="DI",
                event_timestamp=datetime.now(),
                event_code="01",
            ),
        ],
        mail_class="PRIORITY_MAIL",
        mail_type="LETTER",
        service_type_code="020",
        table_code="T",
        unique_mail_piece_id="test-unique-id",
        email_enabled=True,
        kahala_indicator=False,
        proof_of_delivery_enabled=False,
        restore_enabled=True,
        rram_enabled=False,
        rre_enabled=False,
    )


@pytest.fixture()
def sample_tracking_detail() -> USPSTrackingDetail:
    """A representative USPS tracking detail."""
    return _make_tracking_detail()


@pytest.fixture()
def delivered_tracking_detail() -> USPSTrackingDetail:
    """A delivered USPS tracking detail."""
    return _make_tracking_detail(status="Delivered", status_category="Delivered")
