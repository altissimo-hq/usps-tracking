"""USPSClient against a fake HTTP session: OAuth, retries and each endpoint."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from altissimo.usps_tracking.client import USPSClient
from altissimo.usps_tracking.exceptions import USPSAuthenticationError, USPSClientError
from altissimo.usps_tracking.models import (
    CreateUSPSSubscription,
    USPSSubscriptionAdminNotification,
    USPSSubscriptionFilterProperties,
)
from altissimo.usps_tracking.settings import USPSSettings
from conftest import _make_tracking_detail

pytestmark = pytest.mark.unit

TOKEN = {
    "access_token": "token-1",
    "token_type": "Bearer",
    "issued_at": "2026-11-05T12:00:00",
    "expires_in": 3600,
    "status": "approved",
    "scope": "tracking subscriptions",
    "issuer": "api.usps.com",
    "client_id": "key",
    "application_name": "test",
    "api_products": "tracking",
    "public_key": "pk",
}

SUBSCRIPTION = {
    "subscriptionId": "sub-1",
    "listenerURL": "https://usps.test.example.com/subscriptions",
    "secret": "s" * 32,
    "status": "ENABLED",
    "statusReason": "Created",
    "adminNotification": [{"email": "admin@example.com"}],
    "creationTimestamp": "2026-11-05T12:00:00",
    "statusChangeTimestamp": "2026-11-05T12:00:00",
    "expirationTimestamp": "2026-12-05T12:00:00",
    "filterProperties": {"trackingNumber": "TN1", "trackingEventTypes": ["ALL"]},
}


class FakeResponse:
    """The parts of requests.Response the client uses."""

    def __init__(self, status_code: int = 200, body: Any = None, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.headers = headers or {}

    def json(self) -> Any:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} error")


class FakeSession:
    """Records requests and replays queued responses; token requests always succeed unless told otherwise."""

    def __init__(self, *responses: FakeResponse, token: FakeResponse | Exception | None = None) -> None:
        self.responses = list(responses)
        self.token = token if token is not None else FakeResponse(body=TOKEN)
        self.token_calls = 0
        self.requests: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.token_calls += 1
        if isinstance(self.token, Exception):
            raise self.token
        return self.token

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def make_client(session: FakeSession) -> USPSClient:
    settings = USPSSettings(consumer_key="key", consumer_secret="secret", base_url="https://usps.test")
    return USPSClient(settings=settings, session=session)  # type: ignore[arg-type]


def create_body() -> CreateUSPSSubscription:
    return CreateUSPSSubscription(
        listenerURL="https://usps.test.example.com/subscriptions",
        secret="s" * 32,
        adminNotification=[USPSSubscriptionAdminNotification(email="admin@example.com")],
        filterProperties=USPSSubscriptionFilterProperties(trackingNumber="TN1", trackingEventTypes=["ALL"]),
    )


class TestAuthentication:
    def test_token_is_cached(self):
        session = FakeSession()
        client = make_client(session)
        client.authenticate()
        client.authenticate()
        assert session.token_calls == 1
        assert client.credentials is not None
        assert client.credentials.access_token == "token-1"

    def test_token_failure_raises(self):
        client = make_client(FakeSession(token=requests.ConnectionError("down")))
        with pytest.raises(USPSAuthenticationError):
            client.authenticate()

    def test_retries_once_on_401_with_a_new_token(self):
        session = FakeSession(FakeResponse(401), FakeResponse(200, {"trackingNumber": "TN1", "eventSummaries": []}))
        client = make_client(session)
        summary = client.get_tracking_summary("TN1")
        assert summary.tracking_number == "TN1"
        assert session.token_calls == 2
        assert len(session.requests) == 2


class TestTracking:
    def test_get_tracking_detail(self):
        detail = _make_tracking_detail(tracking_number="TN1").model_dump(mode="json")
        session = FakeSession(FakeResponse(200, detail))
        result = make_client(session).get_tracking_detail("TN1")
        assert result.tracking_number == "TN1"
        assert session.requests[0]["url"] == "https://usps.test/tracking/v3/tracking/TN1"
        assert session.requests[0]["params"] == {"expand": "DETAIL"}
        assert session.requests[0]["headers"]["Authorization"] == "Bearer token-1"

    def test_get_tracking_summary(self):
        session = FakeSession(FakeResponse(200, {"trackingNumber": "TN1", "eventSummaries": ["Delivered"]}))
        result = make_client(session).get_tracking_summary("TN1")
        assert result.event_summaries == ["Delivered"]
        assert session.requests[0]["params"] == {"expand": "SUMMARY"}


class TestSubscriptions:
    def test_create_subscription_keeps_etag(self):
        session = FakeSession(FakeResponse(200, SUBSCRIPTION, {"ETag": "etag-1"}))
        result = make_client(session).create_subscription(create_body())
        assert result.subscriptionId == "sub-1"
        assert result.etag == "etag-1"
        assert session.requests[0]["method"] == "POST"
        assert session.requests[0]["json"]["filterProperties"]["trackingNumber"] == "TN1"

    def test_create_subscription_error(self):
        session = FakeSession(FakeResponse(400, {"error": "bad"}))
        with pytest.raises(USPSClientError):
            make_client(session).create_subscription(create_body())

    def test_get_subscription(self):
        session = FakeSession(FakeResponse(200, SUBSCRIPTION, {"ETag": "etag-2"}))
        result = make_client(session).get_subscription("sub-1")
        assert result.etag == "etag-2"

    def test_get_subscription_error(self):
        with pytest.raises(USPSClientError):
            make_client(FakeSession(FakeResponse(404, {}))).get_subscription("sub-1")

    def test_delete_subscription_sends_if_match(self):
        session = FakeSession(FakeResponse(204))
        assert make_client(session).delete_subscription("sub-1", "etag-1") == {"status": "ok"}
        assert session.requests[0]["method"] == "DELETE"
        assert session.requests[0]["headers"]["If-Match"] == "etag-1"

    def test_delete_subscription_error(self):
        with pytest.raises(USPSClientError):
            make_client(FakeSession(FakeResponse(412, {}))).delete_subscription("sub-1", "old")

    def test_list_subscriptions(self):
        session = FakeSession(FakeResponse(200, {"subscriptions": [SUBSCRIPTION], "metadata": {"count": 1}}))
        result = make_client(session).list_subscriptions("TN1")
        assert [s.subscriptionId for s in result.subscriptions] == ["sub-1"]
        assert session.requests[0]["params"] == {"trackingNumber": "TN1"}

    def test_list_subscriptions_error(self):
        with pytest.raises(USPSClientError):
            make_client(FakeSession(FakeResponse(500, {}))).list_subscriptions("TN1")


class TestLazyExports:
    def test_package_exports_resolve(self):
        import altissimo.usps_tracking as pkg

        for name in pkg.__all__:
            assert getattr(pkg, name) is not None

    def test_unknown_attribute(self):
        import altissimo.usps_tracking as pkg

        with pytest.raises(AttributeError):
            pkg.NotAThing  # noqa: B018


def test_reconcile_creates_and_removes_subscriptions(fake_client, fake_repo):
    """Active packages get a subscription; delivered ones lose theirs."""
    from altissimo.usps_tracking.service import USPSService
    from altissimo.usps_tracking.settings import USPSServiceSettings

    settings = USPSServiceSettings(listener_url="https://usps.test.example.com/subscriptions")
    service = USPSService(client=fake_client, repo=fake_repo, settings=settings)

    active = _make_tracking_detail(tracking_number="ACTIVE1")
    delivered = _make_tracking_detail(tracking_number="DONE1", status="Delivered", status_category="Delivered")
    for detail in (active, delivered):
        fake_repo.save_tracking_detail(detail)
    service.create_tracking_subscription("DONE1")
    assert "sub-DONE1" in fake_repo._subscriptions

    service.process_tracking_subscriptions()

    assert "sub-ACTIVE1" in fake_repo._subscriptions
    assert "sub-DONE1" not in fake_repo._subscriptions
