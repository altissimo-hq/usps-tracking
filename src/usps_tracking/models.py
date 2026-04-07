"""USPS tracking models.

API response models mirror the USPS REST API v3 JSON shapes.
Persistence models require the ``[firestore]`` extra.
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, Json, model_validator
from typing_extensions import Self

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Minimal Address model for origin/destination in tracking data
# ---------------------------------------------------------------------------


class Address(BaseModel):
    """Minimal address model for tracking origin/destination data."""

    address1: str = ""
    address2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = "US"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StatusCategory(str, Enum):
    """USPS tracking status categories."""

    ACCEPTED = "Accepted"
    ALERT = "Alert"
    AVAILABLE_FOR_AGENT_PICKUP = "Available for Agent Pickup"
    AVAILABLE_FOR_PICKUP = "Available for Pickup"
    DELIVERED = "Delivered"
    DELIVERED_TO_AGENT = "Deliverd to Agent"
    DELIVERY_ATTEMPT = "Delivery Attempt"
    IN_TRANSIT = "In Transit"
    IN_TRANSIT_FROM_ORIGIN_PROCESSING = "In Transit from Origin Processing"
    MOVING_THROUGH_NETWORK = "Moving Through Network"
    ON_ITS_WAY_TO_USPS = "On its Way to USPS"
    OUT_FOR_DELIVERY = "Out for Delivery"
    PRE_SHIPMENT = "Pre-Shipment"
    PREPARING_FOR_DELIVERY = "Preparing for Delivery"
    RETURNED_TO_SENDER = "Returned to Sender"
    PROCESSING_AT_DESTINATION = "Processing at Destination"


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------


class USPSCredentials(BaseModel):
    """USPS OAuth credentials."""

    access_token: str
    token_type: str
    issued_at: datetime
    expires_in: int
    status: str
    scope: str
    issuer: str
    client_id: str
    application_name: str
    api_products: str
    public_key: str


class TrackSummary(BaseModel):
    """USPS track summary event from the XML/JSON callback."""

    EventTime: str
    EventDate: str
    Event: str
    EventCity: str
    EventState: str
    EventZIPCode: str
    EventCountry: str
    FirmName: str
    Name: str
    AuthorizedAgent: bool
    EventCode: str
    ActionCode: str | None = None
    ReasonCode: str | None = None
    GeoCertified: bool | None = None
    DeliveryAttributeCode: str
    EventStatusCategory: str | None = None
    GMT: str
    GMTOffset: str
    CODAmountDue: str | None = None


class TrackInfo(BaseModel):
    """USPS TrackInfo from the subscription callback payload."""

    ID: str
    AdditionalInfo: str | None = None
    ADPScripting: str | None = None
    ArchiveRestoreInfo: str | None = None
    AssociatedLabel: str | None = None
    CarrierRelease: bool | None = None
    Class: str
    ClassofMailCode: str | None = None
    DestinationCity: str | None = None
    DestinationCountryCode: str | None = None
    DestinationState: str | None = None
    DestinationZip: str | None = None
    EditedLabelID: str | None = None
    EmailEnabled: bool
    EndOfDay: str | None = None
    eSOFEligible: bool | None = None
    ExpectedDeliveryDate: str | None = None
    ExpectedDeliveryTime: str | None = None
    ExpectedDeliveryType: str | None = None
    GuaranteedDeliveryDate: str | None = None
    GuaranteedDeliveryTime: str | None = None
    GuaranteedDeliveryType: str | None = None
    GuaranteedDetails: str | None = None
    KahalaIndicator: bool
    MailTypeCode: str
    MPDATE: datetime
    MPSUFFIX: int
    OnTime: bool | None = None
    OriginCity: str | None = None
    OriginCountryCode: str | None = None
    OriginState: str | None = None
    OriginZip: str | None = None
    PredictedDeliveryDate: str | None = None
    PredictedDeliveryTime: str | None = None
    PredictedDeliveryType: str | None = None
    PredictedDeliverySource: str | None = None
    PDWStart: str | None = None
    PDWEnd: str | None = None
    PurgeByDate: str | None = None
    RelatedRRID: str | None = None
    RestoreEnabled: bool
    ReturnDateNotice: str | None = None
    PodEnabled: bool
    TpodEnabled: bool | None = None
    RramEnabled: bool
    RreEnabled: bool
    Service: list[str]
    ServiceTypeCode: str
    Status: str
    StatusCategory: str
    StatusSummary: str
    TABLECODE: str
    ProductWeight: str | None = None
    TrackDetail: list[TrackSummary] | None = None
    TrackSummary: TrackSummary


class USPSTrackingEvent(BaseModel):
    """USPS tracking event from the v3 API."""

    event_type: str = Field(validation_alias=AliasChoices("eventType", "event_type"))

    event_timestamp: Annotated[
        datetime | None,
        Field(None, validation_alias=AliasChoices("eventTimestamp", "event_timestamp")),
    ]
    gmt_timestamp: datetime | None = Field(None, validation_alias=AliasChoices("GMTTimestamp", "gmt_timestamp"))
    gmt_offset: str | None = Field(None, validation_alias=AliasChoices("GMTOffset", "gmt_offset"))

    event_city: str | None = Field(None, validation_alias=AliasChoices("eventCity", "event_city"))
    event_state: str | None = Field(None, validation_alias=AliasChoices("eventState", "event_state"))
    event_zip: str | None = Field(None, validation_alias=AliasChoices("eventZIP", "event_zip"))
    event_country: str | None = Field(None, validation_alias=AliasChoices("eventCountry", "event_country"))

    additional_prop: str | None = Field(None, validation_alias=AliasChoices("additionalProp", "additional_prop"))
    authorized_agent: bool | None = Field(None, validation_alias=AliasChoices("authorizedAgent", "authorized_agent"))
    event_code: str = Field(validation_alias=AliasChoices("eventCode", "event_code"))
    firm: str | None = None
    name: str | None = None

    timestamp: datetime | None = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def set_timestamp(self) -> Self:
        """Set a normalized timestamp from GMT or event timestamp."""
        if self.gmt_timestamp:
            self.timestamp = self.gmt_timestamp
            return self

        if timestamp := self.event_timestamp:
            try:
                from zoneinfo import ZoneInfo

                self.timestamp = timestamp.replace(tzinfo=ZoneInfo("America/New_York"))
            except ImportError:
                self.timestamp = timestamp

        return self


class USPSTrackingSummary(BaseModel):
    """USPS tracking summary."""

    tracking_number: str = Field(validation_alias=AliasChoices("trackingNumber", "tracking_number"))
    event_summaries: list[str] = Field(validation_alias=AliasChoices("eventSummaries", "event_summaries"))

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Subscription models
# ---------------------------------------------------------------------------


class USPSLink(BaseModel):
    """USPS API link."""

    href: str
    rel: list[str]
    method: Literal["GET", "POST", "PUT", "DELETE"]
    title: str | None = None
    submissionMediaType: str | None = None
    targetMediaType: str | None = None


class USPSSubscriptionNotification(BaseModel):
    """USPS subscription callback notification payload."""

    subscriptionId: str
    subscriptionType: str
    timestamp: datetime
    payload: Json[Any]
    links: list[USPSLink]

    model_config = ConfigDict(extra="allow")


class USPSSubscriptionAdminNotification(BaseModel):
    """Admin notification email for USPS subscriptions."""

    email: str


class USPSSubscriptionFilterProperties(BaseModel):
    """Filter properties for USPS subscriptions."""

    trackingNumber: str | None = None
    trackingEventTypes: list[str] = []


class CreateUSPSSubscription(BaseModel):
    """Request body for creating a USPS subscription."""

    listenerURL: str
    secret: str = Field(min_length=32, max_length=32)
    status: Literal["DISABLED", "ENABLED", "SUSPENDED"] = "ENABLED"
    adminNotification: list[USPSSubscriptionAdminNotification]
    filterProperties: USPSSubscriptionFilterProperties


class USPSSubscription(BaseModel):
    """USPS subscription response."""

    subscriptionId: str
    listenerURL: str
    secret: str
    status: str
    statusReason: str
    adminNotification: list[USPSSubscriptionAdminNotification]
    creationTimestamp: datetime
    statusChangeTimestamp: datetime
    expirationTimestamp: datetime
    filterProperties: USPSSubscriptionFilterProperties
    etag: str | None = None


class USPSSubscriptionsResponse(BaseModel):
    """USPS subscriptions list response."""

    subscriptions: list[USPSSubscription]
    metadata: dict


# ---------------------------------------------------------------------------
# Firestore persistence models (requires ``[firestore]`` extra)
# ---------------------------------------------------------------------------

_HAS_FIREDANTIC = False
_FiredanticBase: type = BaseModel  # fallback

try:
    from firedantic import Model as _FiredanticModel

    _HAS_FIREDANTIC = True
    _FiredanticBase = _FiredanticModel
except ImportError:
    pass


class USPSTrackingDetail(_FiredanticBase):  # type: ignore[misc]
    """Persisted USPS tracking detail.

    When firedantic is installed (via the ``[firestore]`` extra) this is a
    Firedantic ``Model`` stored in the ``usps_tracking_details`` collection.
    Without firedantic it is a plain Pydantic ``BaseModel``.
    """

    if _HAS_FIREDANTIC:
        __collection__ = "usps_tracking_details"

    tracking_number: str = Field(validation_alias=AliasChoices("trackingNumber", "tracking_number"))

    destination_city: str | None = Field(None, validation_alias=AliasChoices("destinationCity", "destination_city"))
    destination_state: str | None = Field(None, validation_alias=AliasChoices("destinationState", "destination_state"))
    destination_zip: str | None = Field(None, validation_alias=AliasChoices("destinationZIP", "destination_zip"))

    expected_delivery_time_stamp: datetime | None = Field(
        None,
        validation_alias=AliasChoices("expectedDeliveryTimeStamp", "expected_delivery_time_stamp"),
    )
    mail_piece_intake_date: datetime = Field(
        validation_alias=AliasChoices("mailPieceIntakeDate", "mail_piece_intake_date")
    )
    predicted_delivery_date: datetime | None = Field(
        None,
        validation_alias=AliasChoices("predictedDeliveryDate", "predicted_delivery_date"),
    )
    predicted_delivery_window_start_time: str | None = Field(
        None,
        validation_alias=AliasChoices("predictedDeliveryWindowStartTime", "predicted_delivery_window_start_time"),
    )
    predicted_delivery_window_end_time: str | None = Field(
        None,
        validation_alias=AliasChoices("predictedDeliveryWindowEndTime", "predicted_delivery_window_end_time"),
    )

    origin_city: str | None = Field(None, validation_alias=AliasChoices("originCity", "origin_city"))
    origin_state: str | None = Field(None, validation_alias=AliasChoices("originState", "origin_state"))
    origin_zip: str | None = Field(None, validation_alias=AliasChoices("originZIP", "origin_zip"))

    services: list[str] = []
    status: str
    status_category: str = Field(validation_alias=AliasChoices("statusCategory", "status_category"))
    status_summary: str = Field(validation_alias=AliasChoices("statusSummary", "status_summary"))
    tracking_events: list[USPSTrackingEvent] = Field(validation_alias=AliasChoices("trackingEvents", "tracking_events"))

    mail_class: str = Field(validation_alias=AliasChoices("mailClass", "mail_class"))
    mail_type: str = Field(validation_alias=AliasChoices("mailType", "mail_type"))
    service_type_code: str = Field(validation_alias=AliasChoices("serviceTypeCode", "service_type_code"))
    table_code: str = Field(validation_alias=AliasChoices("tableCode", "table_code"))
    unique_mail_piece_id: str = Field(validation_alias=AliasChoices("uniqueMailPieceID", "unique_mail_piece_id"))

    email_enabled: bool = Field(validation_alias=AliasChoices("emailEnabled", "email_enabled"))
    kahala_indicator: bool = Field(validation_alias=AliasChoices("kahalaIndicator", "kahala_indicator"))
    proof_of_delivery_enabled: bool = Field(
        validation_alias=AliasChoices("proofOfDeliveryEnabled", "proof_of_delivery_enabled")
    )
    restore_enabled: bool = Field(validation_alias=AliasChoices("restoreEnabled", "restore_enabled"))
    rram_enabled: bool = Field(validation_alias=AliasChoices("RRAMEnabled", "rram_enabled"))
    rre_enabled: bool = Field(validation_alias=AliasChoices("RREEnabled", "rre_enabled"))

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def validate_id(self) -> Self:
        """Ensure the document ID is the tracking number."""
        if hasattr(self, "id"):
            if not self.id:  # type: ignore[has-type]
                self.id = self.tracking_number  # type: ignore[has-type]
        if self.tracking_events:
            self.updated_at = self.tracking_events[0].gmt_timestamp or self.tracking_events[0].timestamp
        return self


class USPSTrackingSubscription(_FiredanticBase):  # type: ignore[misc]
    """Persisted USPS tracking subscription.

    When firedantic is installed this is stored in the
    ``usps_tracking_subscriptions`` collection.
    """

    if _HAS_FIREDANTIC:
        __collection__ = "usps_tracking_subscriptions"

    subscription_id: str = Field(validation_alias=AliasChoices("subscriptionId", "subscription_id"))
    listener_url: str = Field(validation_alias=AliasChoices("listenerURL", "listener_url"))
    secret: str

    tracking_number: str = Field(
        validation_alias=AliasChoices(AliasPath("filterProperties", "trackingNumber"), "tracking_number")
    )
    tracking_event_types: list[str] = Field(
        validation_alias=AliasChoices(AliasPath("filterProperties", "trackingEventTypes"), "tracking_event_types")
    )
    admin_notification: list[USPSSubscriptionAdminNotification] = Field(
        validation_alias=AliasChoices("adminNotification", "admin_notification")
    )

    status: str
    status_reason: str = Field(validation_alias=AliasChoices("statusReason", "status_reason"))

    creation_timestamp: datetime = Field(validation_alias=AliasChoices("creationTimestamp", "creation_timestamp"))
    expiration_timestamp: datetime = Field(validation_alias=AliasChoices("expirationTimestamp", "expiration_timestamp"))
    status_change_timestamp: datetime = Field(
        validation_alias=AliasChoices("statusChangeTimestamp", "status_change_timestamp")
    )

    @model_validator(mode="after")
    def validate_id(self) -> Self:
        """Ensure the document ID is the subscription ID."""
        if hasattr(self, "id"):
            if not self.id:  # type: ignore[has-type]
                self.id = self.subscription_id  # type: ignore[has-type]
        return self

    @classmethod
    def from_usps_subscription(cls, usps_subscription: USPSSubscription) -> USPSTrackingSubscription:
        """Create from a USPSSubscription API response."""
        return cls(**usps_subscription.model_dump())
