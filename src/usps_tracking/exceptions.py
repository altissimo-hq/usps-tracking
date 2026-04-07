"""USPS tracking exception hierarchy."""


class USPSError(Exception):
    """Base error for the usps-tracking package."""


class USPSTrackingDetailNotFoundError(USPSError):
    """Raised when a USPS tracking detail is not found in persistence."""


class USPSTrackingSubscriptionNotFoundError(USPSError):
    """Raised when a USPS tracking subscription is not found in persistence."""


class USPSClientError(USPSError):
    """Error communicating with the USPS API."""


class USPSAuthenticationError(USPSClientError):
    """Error authenticating with the USPS API."""
