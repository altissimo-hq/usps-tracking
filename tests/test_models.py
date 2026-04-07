"""Unit tests for USPS models."""

import pytest

from usps_tracking.models import (
    Address,
    StatusCategory,
    USPSTrackingEvent,
    USPSTrackingSummary,
)

pytestmark = pytest.mark.unit


class TestAddress:
    """Tests for the minimal Address model."""

    def test_default_construction(self):
        addr = Address()
        assert addr.country == "US"
        assert addr.address1 == ""

    def test_full_construction(self):
        addr = Address(
            address1="123 Main St",
            address2="Apt 4",
            city="Boston",
            state="MA",
            postal_code="02101",
            country="US",
        )
        assert addr.city == "Boston"
        assert addr.postal_code == "02101"


class TestStatusCategory:
    """Tests for StatusCategory enum."""

    def test_delivered_value(self):
        assert StatusCategory.DELIVERED.value == "Delivered"

    def test_in_transit_value(self):
        assert StatusCategory.IN_TRANSIT.value == "In Transit"

    def test_all_expected_values(self):
        values = {e.value for e in StatusCategory}
        assert "Accepted" in values
        assert "Pre-Shipment" in values
        assert "Out for Delivery" in values


class TestUSPSTrackingEvent:
    """Tests for USPSTrackingEvent."""

    def test_camel_case_alias(self):
        event = USPSTrackingEvent(eventType="DI", eventCode="01")
        assert event.event_type == "DI"
        assert event.event_code == "01"

    def test_snake_case_alias(self):
        event = USPSTrackingEvent(event_type="DI", event_code="01")
        assert event.event_type == "DI"

    def test_extra_fields_allowed(self):
        event = USPSTrackingEvent(event_type="DI", event_code="01", extra_field="value")
        assert event.event_type == "DI"


class TestUSPSTrackingSummary:
    """Tests for USPSTrackingSummary."""

    def test_from_camel_case(self):
        summary = USPSTrackingSummary(
            trackingNumber="TEST123",
            eventSummaries=["Delivered", "In Transit"],
        )
        assert summary.tracking_number == "TEST123"
        assert len(summary.event_summaries) == 2
