"""Fetch business profile data from the Google Places API (New), Text Search."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
PAGE_SIZE = 20  # API maximum per page
MAX_RESULTS_PER_QUERY = 60  # API returns at most 3 pages per query

BASE_FIELDS = [
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.websiteUri",
    "places.nationalPhoneNumber",
    "places.rating",
    "places.userRatingCount",
    "places.photos",
    "places.regularOpeningHours",
    "places.businessStatus",
    "places.googleMapsUri",
    "places.primaryTypeDisplayName",
]
REVIEW_FIELDS = ["places.reviews"]


class PlacesError(RuntimeError):
    pass


def _field_mask(include_reviews: bool) -> str:
    fields = BASE_FIELDS + (REVIEW_FIELDS if include_reviews else [])
    return ",".join(fields + ["nextPageToken"])


def _days_since(iso_ts: str | None) -> int | None:
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, (datetime.now(timezone.utc) - ts).days)


def normalize(place: dict, city: str, niche: str) -> dict:
    """Flatten one Places API result into the fields the audit cares about."""
    reviews = place.get("reviews") or []
    ages = [d for d in (_days_since(r.get("publishTime")) for r in reviews) if d is not None]
    return {
        "place_id": place.get("id", ""),
        "name": (place.get("displayName") or {}).get("text", "Unknown"),
        "niche": niche,
        "search_city": city,
        "address": place.get("formattedAddress", ""),
        "phone": place.get("nationalPhoneNumber", ""),
        "website": place.get("websiteUri", ""),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount", 0) or 0,
        # The API returns at most 10 photos, so 10 means "10 or more".
        "photo_count": len(place.get("photos") or []),
        "has_hours": bool(place.get("regularOpeningHours")),
        # None means review data was not requested or not returned.
        "days_since_last_review": min(ages) if ages else None,
        "reviews_checked": bool(reviews),
        "business_status": place.get("businessStatus", ""),
        "maps_url": place.get("googleMapsUri", ""),
        "category": (place.get("primaryTypeDisplayName") or {}).get("text", ""),
    }


def search(
    niche: str,
    city: str,
    api_key: str,
    limit: int = 40,
    include_reviews: bool = True,
    session: requests.Session | None = None,
) -> list[dict]:
    """Return up to `limit` businesses for "<niche> in <city>"."""
    http = session or requests.Session()
    limit = min(limit, MAX_RESULTS_PER_QUERY)
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _field_mask(include_reviews),
    }
    body: dict = {"textQuery": f"{niche} in {city}", "pageSize": min(PAGE_SIZE, limit)}
    results: list[dict] = []

    while len(results) < limit:
        resp = http.post(ENDPOINT, headers=headers, json=body, timeout=30)
        if resp.status_code != 200:
            try:
                msg = resp.json().get("error", {}).get("message", resp.text)
            except ValueError:
                msg = resp.text
            raise PlacesError(f"Places API error {resp.status_code} for '{city}': {msg}")
        data = resp.json()
        for place in data.get("places", []):
            if place.get("businessStatus") in ("CLOSED_PERMANENTLY",):
                continue
            results.append(normalize(place, city, niche))
        token = data.get("nextPageToken")
        if not token:
            break
        body["pageToken"] = token
        time.sleep(1.5)  # page tokens need a moment to become valid

    return results[:limit]
