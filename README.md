# usps-tracking

USPS tracking & subscription client with optional Firestore persistence.

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
