# usps-tracking

USPS tracking & subscription client with optional Firestore persistence.

## Status

This is the USPS integration two Altissimo projects ran until April 1, 2026, kept as a package for reuse. Nothing deploys it now.

- **Subscriptions (webhooks) need a paid USPS contract.** Since April 1, 2026, the Subscriptions-Tracking API is no longer free, so `create_tracking_subscription`, `process_tracking_subscriptions` and the webhook router won't work without one.
- **Harden the webhook side before using it again.** `USPSServiceSettings.subscription_secret` defaults to a value that is public in this repo, and the router doesn't verify callbacks, so anyone who knows the URL can post a fake notification. Before reuse:
  - give each deployment its own secret;
  - verify each callback's `X-HMAC` signature (HMAC-SHA256 of the notification's `timestamp` + raw `payload`, keyed with that secret; confirm against the USPS spec);
  - act on the re-fetched `detail`, not the payload's `track_info`.
- **Move to Subscriptions-Tracking v3.2.** This code calls v3.0, which USPS retires on July 31, 2027.

## Installation

```bash
# Basic (API client + models only)
pip install git+https://github.com/altissimo-hq/usps-tracking.git

# With Firestore persistence
pip install "usps-tracking[firestore] @ git+https://github.com/altissimo-hq/usps-tracking.git"
```

## Quick Start

```python
from altissimo.usps_tracking import USPSClient

client = USPSClient()  # reads USPS_CONSUMER_KEY, USPS_CONSUMER_SECRET from env
detail = client.get_tracking_detail("9400111899223456789012")
print(detail.status_category)  # "In Transit", "Delivered", etc.
```

## With Firestore Persistence

```python
from altissimo.usps_tracking import USPSService

service = USPSService()

# Fetch from API and save to Firestore
detail = service.save_tracking_detail("9400111899223456789012")

# Create a subscription for webhook updates
service.create_tracking_subscription("9400111899223456789012")
```

## Tracking Update Callback Hook

Inject your own logic for when tracking data is updated via a webhook callback:

```python
from altissimo.usps_tracking import USPSService, USPSTrackingDetail
from altissimo.usps_tracking.models import TrackInfo

def handle_tracking_update(detail: USPSTrackingDetail, track_info: TrackInfo):
    if track_info.StatusCategory == "Delivered":
        print(f"Package {detail.tracking_number} delivered!")
        # Send email, update order, etc.

service = USPSService(on_tracking_update=handle_tracking_update)
```

## FastAPI Webhook Router

```python
from fastapi import FastAPI
from altissimo.usps_tracking.router import create_usps_router

app = FastAPI()

# Simple — no callback
app.include_router(create_usps_router())

# With tracking update callback
app.include_router(create_usps_router(on_tracking_update=handle_tracking_update))
```

## Environment Variables

| Variable               | Required | Description                                              |
| ---------------------- | -------- | -------------------------------------------------------- |
| `USPS_CONSUMER_KEY`    | Yes      | USPS API consumer key                                    |
| `USPS_CONSUMER_SECRET` | Yes      | USPS API consumer secret                                 |
| `USPS_API_BASE_URL`    | No       | Override API base URL (default: `https://apis.usps.com`) |

## Testing

```bash
poetry install --with dev
poetry run pytest -v
```

All unit tests use in-memory fakes — no Firestore or network access required.
