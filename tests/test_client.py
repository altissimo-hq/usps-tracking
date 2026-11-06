"""Unit tests for USPSClient."""

import pytest

from altissimo.usps_tracking.client import USPSClient
from altissimo.usps_tracking.settings import USPSSettings

pytestmark = pytest.mark.unit


class TestUSPSClientInit:
    """Tests for USPSClient construction."""

    def test_default_construction(self):
        client = USPSClient()
        assert client._settings is None
        assert client._credentials is None

    def test_explicit_settings(self):
        settings = USPSSettings(consumer_key="key", consumer_secret="secret")
        client = USPSClient(settings=settings)
        assert client._get_settings().consumer_key == "key"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("USPS_CONSUMER_KEY", "env_key")
        monkeypatch.setenv("USPS_CONSUMER_SECRET", "env_secret")
        client = USPSClient.from_env()
        settings = client._get_settings()
        assert settings.consumer_key == "env_key"
        assert settings.consumer_secret == "env_secret"

    def test_url_construction(self):
        settings = USPSSettings(
            consumer_key="key",
            consumer_secret="secret",
            base_url="https://custom.api.com",
        )
        client = USPSClient(settings=settings)
        assert client._url("/tracking/v3/tracking/123") == "https://custom.api.com/tracking/v3/tracking/123"


class TestUSPSSettings:
    """Tests for USPSSettings."""

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("USPS_CONSUMER_KEY", "test_key")
        monkeypatch.setenv("USPS_CONSUMER_SECRET", "test_secret")
        settings = USPSSettings.from_env()
        assert settings.consumer_key == "test_key"
        assert settings.consumer_secret == "test_secret"
        assert settings.base_url == "https://apis.usps.com"

    def test_from_env_custom_base_url(self, monkeypatch):
        monkeypatch.setenv("USPS_CONSUMER_KEY", "key")
        monkeypatch.setenv("USPS_CONSUMER_SECRET", "secret")
        monkeypatch.setenv("USPS_API_BASE_URL", "https://sandbox.usps.com/")
        settings = USPSSettings.from_env()
        assert settings.base_url == "https://sandbox.usps.com"

    def test_from_env_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("USPS_CONSUMER_KEY", raising=False)
        monkeypatch.delenv("USPS_CONSUMER_SECRET", raising=False)
        with pytest.raises(ValueError, match="USPS_CONSUMER_KEY"):
            USPSSettings.from_env()

    def test_from_env_missing_secret_raises(self, monkeypatch):
        monkeypatch.setenv("USPS_CONSUMER_KEY", "key")
        monkeypatch.delenv("USPS_CONSUMER_SECRET", raising=False)
        with pytest.raises(ValueError, match="USPS_CONSUMER_SECRET"):
            USPSSettings.from_env()
