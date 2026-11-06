"""USPS tracking persistence repository.

Requires the ``[firestore]`` extra (firedantic).
"""

from __future__ import annotations

from typing import Protocol, cast

from .exceptions import USPSTrackingDetailNotFoundError, USPSTrackingSubscriptionNotFoundError
from .models import USPSTrackingDetail, USPSTrackingSubscription


class USPSTrackingRepoProtocol(Protocol):
    """Protocol for USPS tracking persistence — implement for test fakes."""

    def get_tracking_detail(self, tracking_number: str) -> USPSTrackingDetail: ...

    def list_tracking_details(self) -> list[USPSTrackingDetail]: ...

    def save_tracking_detail(self, tracking_detail: USPSTrackingDetail) -> None: ...

    def delete_tracking_detail(self, tracking_detail: USPSTrackingDetail) -> None: ...

    def get_tracking_subscription(self, usps_subscription_id: str) -> USPSTrackingSubscription: ...

    def list_tracking_subscriptions(self, tracking_number: str | None = None) -> list[USPSTrackingSubscription]: ...

    def save_tracking_subscription(self, tracking_subscription: USPSTrackingSubscription) -> None: ...

    def delete_tracking_subscription(self, tracking_subscription: USPSTrackingSubscription) -> None: ...


class USPSTrackingRepo:
    """Thin Firedantic persistence wrapper for USPS tracking.

    Requires firedantic to be installed (the ``[firestore]`` extra).
    """

    def get_tracking_detail(self, tracking_number: str) -> USPSTrackingDetail:
        """Fetch by tracking number.

        Raises:
            USPSTrackingDetailNotFoundError: If not found.
        """
        try:
            from firedantic import ModelNotFoundError

            try:
                return cast("USPSTrackingDetail", USPSTrackingDetail.get_by_id(tracking_number))
            except ModelNotFoundError as e:
                raise USPSTrackingDetailNotFoundError(f"Tracking detail not found: {tracking_number}") from e
        except ImportError as e:
            raise RuntimeError(
                "firedantic is required for USPSTrackingRepo — install with: pip install usps-tracking[firestore]"
            ) from e

    def list_tracking_details(self) -> list[USPSTrackingDetail]:
        """List all tracking details."""
        return cast("list[USPSTrackingDetail]", USPSTrackingDetail.find())

    def save_tracking_detail(self, tracking_detail: USPSTrackingDetail) -> None:
        """Persist a tracking detail."""
        tracking_detail.save()

    def delete_tracking_detail(self, tracking_detail: USPSTrackingDetail) -> None:
        """Delete a tracking detail."""
        tracking_detail.delete()

    def get_tracking_subscription(self, usps_subscription_id: str) -> USPSTrackingSubscription:
        """Fetch by subscription ID.

        Raises:
            USPSTrackingSubscriptionNotFoundError: If not found.
        """
        try:
            from firedantic import ModelNotFoundError

            try:
                return cast("USPSTrackingSubscription", USPSTrackingSubscription.get_by_id(usps_subscription_id))
            except ModelNotFoundError as e:
                raise USPSTrackingSubscriptionNotFoundError(
                    f"Tracking subscription not found: {usps_subscription_id}"
                ) from e
        except ImportError as e:
            raise RuntimeError(
                "firedantic is required for USPSTrackingRepo — install with: pip install usps-tracking[firestore]"
            ) from e

    def list_tracking_subscriptions(self, tracking_number: str | None = None) -> list[USPSTrackingSubscription]:
        """List tracking subscriptions, optionally filtered by tracking number."""
        if tracking_number:
            return cast(
                "list[USPSTrackingSubscription]", USPSTrackingSubscription.find({"tracking_number": tracking_number})
            )
        return cast("list[USPSTrackingSubscription]", USPSTrackingSubscription.find())

    def save_tracking_subscription(self, tracking_subscription: USPSTrackingSubscription) -> None:
        """Persist a tracking subscription."""
        tracking_subscription.save()

    def delete_tracking_subscription(self, tracking_subscription: USPSTrackingSubscription) -> None:
        """Delete a tracking subscription."""
        tracking_subscription.delete()
