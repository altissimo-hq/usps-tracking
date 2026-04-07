"""Unit tests for USPSService."""

from __future__ import annotations

from datetime import datetime

import pytest

from usps_tracking.exceptions import USPSTrackingDetailNotFoundError
from usps_tracking.service import USPSService
from usps_tracking.settings import USPSServiceSettings

pytestmark = pytest.mark.unit


class TestGetTrackingDetail:
    """Tests for USPSService.get_tracking_detail."""

    def test_returns_stored_detail(self, fake_client, fake_repo, sample_tracking_detail):
        fake_repo._details[sample_tracking_detail.tracking_number] = sample_tracking_detail
        service = USPSService(client=fake_client, repo=fake_repo)

        result = service.get_tracking_detail(sample_tracking_detail.tracking_number)

        assert result.tracking_number == sample_tracking_detail.tracking_number
        assert result.status == "In Transit"

    def test_raises_on_missing(self, fake_client, fake_repo):
        service = USPSService(client=fake_client, repo=fake_repo)

        with pytest.raises(USPSTrackingDetailNotFoundError):
            service.get_tracking_detail("nonexistent")


class TestSaveTrackingDetail:
    """Tests for USPSService.save_tracking_detail."""

    def test_saves_from_api(self, fake_client, fake_repo, sample_tracking_detail):
        fake_client.add_tracking_detail(sample_tracking_detail.tracking_number, sample_tracking_detail)
        service = USPSService(client=fake_client, repo=fake_repo)

        result = service.save_tracking_detail(sample_tracking_detail.tracking_number)

        assert result.tracking_number == sample_tracking_detail.tracking_number
        assert sample_tracking_detail.tracking_number in fake_repo._details


class TestDeleteTrackingDetail:
    """Tests for USPSService.delete_tracking_detail."""

    def test_deletes_existing(self, fake_client, fake_repo, sample_tracking_detail):
        fake_repo._details[sample_tracking_detail.tracking_number] = sample_tracking_detail
        service = USPSService(client=fake_client, repo=fake_repo)

        result = service.delete_tracking_detail(sample_tracking_detail.tracking_number)

        assert result == {"id": sample_tracking_detail.tracking_number}
        assert sample_tracking_detail.tracking_number not in fake_repo._details

    def test_raises_on_missing(self, fake_client, fake_repo):
        service = USPSService(client=fake_client, repo=fake_repo)

        with pytest.raises(USPSTrackingDetailNotFoundError):
            service.delete_tracking_detail("nonexistent")


class TestListTrackingDetails:
    """Tests for USPSService.list_tracking_details."""

    def test_returns_empty_list(self, fake_client, fake_repo):
        service = USPSService(client=fake_client, repo=fake_repo)
        assert service.list_tracking_details() == []

    def test_returns_stored_details(self, fake_client, fake_repo, sample_tracking_detail):
        fake_repo._details[sample_tracking_detail.tracking_number] = sample_tracking_detail
        service = USPSService(client=fake_client, repo=fake_repo)

        result = service.list_tracking_details()

        assert len(result) == 1


class TestListByStatusCategory:
    """Tests for USPSService.list_tracking_details_by_status_category."""

    def test_filter_by_status(self, fake_client, fake_repo, sample_tracking_detail, delivered_tracking_detail):
        fake_repo._details[sample_tracking_detail.tracking_number] = sample_tracking_detail
        fake_repo._details["DELIVERED_123"] = delivered_tracking_detail
        service = USPSService(client=fake_client, repo=fake_repo)

        result = service.list_tracking_details_by_status_category("Delivered")

        assert len(result) == 1
        assert result[0].status_category == "Delivered"

    def test_exclude_by_status(self, fake_client, fake_repo, sample_tracking_detail, delivered_tracking_detail):
        fake_repo._details[sample_tracking_detail.tracking_number] = sample_tracking_detail
        fake_repo._details["DELIVERED_123"] = delivered_tracking_detail
        service = USPSService(client=fake_client, repo=fake_repo)

        result = service.list_tracking_details_by_status_category("-Delivered")

        assert len(result) == 1
        assert result[0].status_category != "Delivered"


class TestProcessTrackingDetails:
    """Tests for USPSService.process_tracking_details."""

    def test_skips_delivered(self, fake_client, fake_repo, delivered_tracking_detail):
        fake_repo._details["DELIVERED"] = delivered_tracking_detail
        fake_client.add_tracking_detail("DELIVERED", delivered_tracking_detail)
        service = USPSService(client=fake_client, repo=fake_repo, sleep_fn=lambda _: None)

        result = service.process_tracking_details()

        assert result == {"status": "ok"}


class TestCreateTrackingSubscription:
    """Tests for USPSService.create_tracking_subscription."""

    def test_creates_subscription(self, fake_client, fake_repo):
        settings = USPSServiceSettings(listener_url="https://usps.test.example.com/subscriptions")
        service = USPSService(client=fake_client, repo=fake_repo, settings=settings)

        result = service.create_tracking_subscription("TEST123")

        assert result.subscription_id == "sub-TEST123"
        assert result.tracking_number == "TEST123"
        assert "sub-TEST123" in fake_repo._subscriptions


class TestOnTrackingUpdateCallback:
    """Tests for the on_tracking_update callback hook."""

    def test_callback_fires(self, fake_client, fake_repo, sample_tracking_detail):
        updates = []
        fake_client.add_tracking_detail(sample_tracking_detail.tracking_number, sample_tracking_detail)

        def capture(detail, track_info):
            updates.append((detail, track_info))

        service = USPSService(client=fake_client, repo=fake_repo, on_tracking_update=capture)

        # Simulate callback payload
        body_data = {
            "subscriptionId": "sub-1",
            "subscriptionType": "TRACKING",
            "timestamp": datetime.now().isoformat(),
            "payload": '{"TrackInfo": {"ID": "'
            + sample_tracking_detail.tracking_number
            + '", "Class": "PRIORITY_MAIL", "EmailEnabled": true, "KahalaIndicator": false, "MailTypeCode": "DM", "MPDATE": "'
            + datetime.now().isoformat()
            + '", "MPSUFFIX": 0, "RestoreEnabled": true, "PodEnabled": false, "RramEnabled": false, "RreEnabled": false, "Service": ["Priority Mail"], "ServiceTypeCode": "020", "Status": "In Transit", "StatusCategory": "In Transit", "StatusSummary": "In Transit", "TABLECODE": "T", "TrackSummary": {"EventTime": "10:00", "EventDate": "2026-03-19", "Event": "In Transit", "EventCity": "Boston", "EventState": "MA", "EventZIPCode": "02101", "EventCountry": "US", "FirmName": "", "Name": "", "AuthorizedAgent": false, "EventCode": "01", "DeliveryAttributeCode": "", "GMT": "15:00", "GMTOffset": "-05:00"}}}',
            "links": [],
        }

        from usps_tracking.models import USPSSubscriptionNotification

        body = USPSSubscriptionNotification(**body_data)
        result = service.process_subscriptions_callback(body)

        assert result["status"] == "ok"
        assert len(updates) == 1

    def test_no_callback_when_not_set(self, fake_client, fake_repo, sample_tracking_detail):
        """Service works fine without an on_tracking_update callback."""
        fake_client.add_tracking_detail(sample_tracking_detail.tracking_number, sample_tracking_detail)
        service = USPSService(client=fake_client, repo=fake_repo)

        body_data = {
            "subscriptionId": "sub-1",
            "subscriptionType": "TRACKING",
            "timestamp": datetime.now().isoformat(),
            "payload": '{"TrackInfo": {"ID": "'
            + sample_tracking_detail.tracking_number
            + '", "Class": "PRIORITY_MAIL", "EmailEnabled": true, "KahalaIndicator": false, "MailTypeCode": "DM", "MPDATE": "'
            + datetime.now().isoformat()
            + '", "MPSUFFIX": 0, "RestoreEnabled": true, "PodEnabled": false, "RramEnabled": false, "RreEnabled": false, "Service": ["Priority Mail"], "ServiceTypeCode": "020", "Status": "In Transit", "StatusCategory": "In Transit", "StatusSummary": "In Transit", "TABLECODE": "T", "TrackSummary": {"EventTime": "10:00", "EventDate": "2026-03-19", "Event": "In Transit", "EventCity": "Boston", "EventState": "MA", "EventZIPCode": "02101", "EventCountry": "US", "FirmName": "", "Name": "", "AuthorizedAgent": false, "EventCode": "01", "DeliveryAttributeCode": "", "GMT": "15:00", "GMTOffset": "-05:00"}}}',
            "links": [],
        }

        from usps_tracking.models import USPSSubscriptionNotification

        body = USPSSubscriptionNotification(**body_data)
        result = service.process_subscriptions_callback(body)

        assert result["status"] == "ok"
