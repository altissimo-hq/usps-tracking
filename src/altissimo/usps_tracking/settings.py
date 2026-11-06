"""USPS client settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class USPSSettings:
    """Settings for the USPS API client."""

    consumer_key: str
    consumer_secret: str
    base_url: str = "https://apis.usps.com"
    timeout: int = 10

    @classmethod
    def from_env(cls) -> USPSSettings:
        """Build settings from environment variables.

        Reads ``USPS_CONSUMER_KEY``, ``USPS_CONSUMER_SECRET``, and
        optionally ``USPS_API_BASE_URL``.

        Raises:
            ValueError: If required env vars are missing.
        """
        consumer_key = os.environ.get("USPS_CONSUMER_KEY", "")
        consumer_secret = os.environ.get("USPS_CONSUMER_SECRET", "")
        base_url = os.environ.get("USPS_API_BASE_URL", "https://apis.usps.com")

        if not consumer_key:
            raise ValueError("USPS_CONSUMER_KEY is not set")
        if not consumer_secret:
            raise ValueError("USPS_CONSUMER_SECRET is not set")

        return cls(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            base_url=base_url.rstrip("/"),
        )


@dataclass(frozen=True)
class USPSServiceSettings:
    """Settings for the USPS service layer."""

    listener_url: str
    # FIXME: a public default secret. Callers should pass their own; see the PR that added this note.
    subscription_secret: str = "MySecretKeyPhraseIs32BytesLength"  # noqa: S105
    admin_notification_email: str = "admin@example.com"

    @classmethod
    def from_env(cls, *, domain: str = "example.com", admin_email: str = "admin@example.com") -> USPSServiceSettings:
        """Build service settings from environment variables.

        Args:
            domain: The base domain for the listener URL.
            admin_email: Email for USPS subscription admin notifications.
        """
        env = os.environ.get("ENV", "dev")
        if env == "prod":
            listener_url = f"https://usps.{domain}/subscriptions"
        else:
            listener_url = f"https://usps.{env}.{domain}/subscriptions"
        return cls(listener_url=listener_url, admin_notification_email=admin_email)
