"""USPS REST API v3 client.

Self-contained OAuth 2.0 client credentials flow — no external base class.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import requests

from .exceptions import USPSAuthenticationError, USPSClientError
from .models import (
    CreateUSPSSubscription,
    USPSCredentials,
    USPSSubscription,
    USPSSubscriptionsResponse,
    USPSTrackingDetail,
    USPSTrackingSummary,
)
from .settings import USPSSettings

logger = logging.getLogger(__name__)


class USPSClient:
    """USPS REST API v3 client with built-in OAuth token management.

    The client automatically fetches and refreshes OAuth tokens using the
    client credentials flow.  Tokens are cached in memory and refreshed
    when they expire.

    Usage::

        client = USPSClient()  # reads env vars lazily
        detail = client.get_tracking_detail("9400111899223456789012")

        # Or with explicit settings
        settings = USPSSettings(consumer_key="...", consumer_secret="...")
        client = USPSClient(settings=settings)
    """

    def __init__(
        self,
        *,
        settings: USPSSettings | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._settings = settings
        self._session = session or requests.Session()
        self._credentials: USPSCredentials | None = None
        self._token_expires_at: datetime | None = None

    @classmethod
    def from_env(cls) -> USPSClient:
        """Build client from environment variables."""
        return cls(settings=USPSSettings.from_env())

    # -----------------------------------------------------------------
    # OAuth Token Management
    # -----------------------------------------------------------------

    def _get_settings(self) -> USPSSettings:
        if self._settings is None:
            self._settings = USPSSettings.from_env()
        return self._settings

    def _url(self, path: str) -> str:
        return f"{self._get_settings().base_url}{path}"

    @property
    def credentials(self) -> USPSCredentials | None:
        """Current cached credentials (may be stale)."""
        return self._credentials

    def authenticate(self) -> None:
        """Ensure we have valid OAuth credentials, refreshing if needed."""
        if self._credentials and self._token_expires_at and datetime.now() < self._token_expires_at:
            return
        self._credentials = self._fetch_client_credentials()
        self._token_expires_at = datetime.now() + timedelta(seconds=self._credentials.expires_in - 60)

    def _fetch_client_credentials(self) -> USPSCredentials:
        """Fetch a new OAuth token using client credentials flow."""
        settings = self._get_settings()
        body = {
            "client_id": settings.consumer_key,
            "client_secret": settings.consumer_secret,
            "grant_type": "client_credentials",
        }
        try:
            response = self._session.post(
                self._url("/oauth2/v3/token"),
                data=body,
                timeout=settings.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise USPSAuthenticationError(f"Failed to get USPS OAuth token: {e}") from e

        return USPSCredentials(**response.json())

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, Any] | None = None,
    ) -> requests.Response:
        """Make an authenticated request with automatic 401 retry."""
        self.authenticate()
        if self._credentials is None:
            raise RuntimeError("USPS authentication returned no credentials")

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._credentials.access_token}",
        }
        if extra_headers:
            headers.update(extra_headers)

        settings = self._get_settings()
        response = self._session.request(
            method,
            url,
            params=params,
            json=json_body,
            headers=headers,
            timeout=settings.timeout,
        )

        # Retry once on 401
        if response.status_code == 401:
            logger.info("USPS API returned 401; refreshing access token and retrying")
            self._credentials = None
            self._token_expires_at = None
            self.authenticate()
            if self._credentials is None:
                raise RuntimeError("USPS authentication returned no credentials")
            headers["Authorization"] = f"Bearer {self._credentials.access_token}"
            response = self._session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=settings.timeout,
            )

        return response

    # -----------------------------------------------------------------
    # Tracking Endpoints
    # -----------------------------------------------------------------

    def get_tracking_detail(self, tracking_number: str) -> USPSTrackingDetail:
        """Fetch detailed tracking for a tracking number."""
        logger.info("Getting USPS Tracking Detail: %s", tracking_number)
        response = self._request(
            "GET",
            self._url(f"/tracking/v3/tracking/{tracking_number}"),
            params={"expand": "DETAIL"},
        )
        response.raise_for_status()
        return USPSTrackingDetail(**response.json())

    def get_tracking_summary(self, tracking_number: str) -> USPSTrackingSummary:
        """Fetch tracking summary for a tracking number."""
        logger.info("Getting USPS Tracking Summary: %s", tracking_number)
        response = self._request(
            "GET",
            self._url(f"/tracking/v3/tracking/{tracking_number}"),
            params={"expand": "SUMMARY"},
        )
        response.raise_for_status()
        return USPSTrackingSummary(**response.json())

    # -----------------------------------------------------------------
    # Subscription Endpoints
    # -----------------------------------------------------------------

    def create_subscription(self, body: CreateUSPSSubscription) -> USPSSubscription:
        """Create a tracking subscription."""
        logger.debug("Creating USPS Subscription")
        data = body.model_dump(mode="json")
        response = self._request(
            "POST",
            self._url("/subscriptions-tracking/v3/subscriptions"),
            json_body=data,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.debug("Body: %s", json.dumps(data, indent=2))
            logger.debug("Response: %s", json.dumps(response.json(), indent=2))
            raise USPSClientError(f"Error creating subscription: {e}") from e
        subscription = USPSSubscription(**response.json())
        subscription.etag = response.headers.get("ETag")
        logger.debug("USPS Subscription Created: %s [%s]", subscription.subscriptionId, subscription.etag)
        return subscription

    def delete_subscription(self, usps_subscription_id: str, etag: str) -> dict[str, Any]:
        """Delete a subscription."""
        logger.debug("Deleting USPS Subscription: %s [%s]", usps_subscription_id, etag)
        response = self._request(
            "DELETE",
            self._url(f"/subscriptions-tracking/v3/subscriptions/{usps_subscription_id}"),
            extra_headers={"If-Match": etag},
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.debug("Response: %s", json.dumps(response.json(), indent=2))
            raise USPSClientError(f"Error deleting subscription: {e}") from e
        return {"status": "ok"}

    def get_subscription(self, usps_subscription_id: str) -> USPSSubscription:
        """Get a subscription by id."""
        response = self._request(
            "GET",
            self._url(f"/subscriptions-tracking/v3/subscriptions/{usps_subscription_id}"),
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.debug("Response: %s", json.dumps(response.json(), indent=2))
            raise USPSClientError(f"Error getting subscription: {e}") from e
        subscription = USPSSubscription(**response.json())
        subscription.etag = response.headers.get("ETag")
        return subscription

    def list_subscriptions(self, tracking_number: str) -> USPSSubscriptionsResponse:
        """List subscriptions for a tracking number."""
        response = self._request(
            "GET",
            self._url("/subscriptions-tracking/v3/subscriptions"),
            params={"trackingNumber": tracking_number},
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.debug("Response: %s", json.dumps(response.json(), indent=2))
            raise USPSClientError(f"Error listing subscriptions: {e}") from e
        return USPSSubscriptionsResponse(**response.json())
