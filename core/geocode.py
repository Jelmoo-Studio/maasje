"""Geocode listings via Nominatim (OpenStreetMap), met file-cache.

Vult lat/lng aan, en — als de listing nog geen wijk heeft — ook de wijk
op basis van het 'neighbourhood' veld van Nominatim's addressdetails.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from pathlib import Path
from typing import Iterable, Optional

import httpx

from scrapers.base import Listing

log = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "geocache.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_UA = "huur-scraper-maastricht/1.0 (personal)"
RATE_LIMIT_SEC = 1.1

MAASTRICHT_CENTER = (50.8514, 5.6909)

_POSTCODE_RE = re.compile(r"(\d{4})\s*([A-Z]{2})")


def extract_postcode(text: str) -> Optional[str]:
    if not text:
        return None
    m = _POSTCODE_RE.search(text.upper())
    if not m:
        return None
    return f"{m.group(1)} {m.group(2)}"


def _query_key(listing: Listing) -> Optional[str]:
    """Bouw beste Nominatim-query voor een listing: postcode > straat."""
    pc = listing.postcode or extract_postcode(listing.address or "")
    if pc:
        return f"{pc}, Maastricht, Nederland"
    if listing.address:
        # Pak het eerste segment (straatnaam, evt. met huisnr)
        first = listing.address.split(",")[0].strip()
        if first:
            return f"{first}, Maastricht, Nederland"
    return None


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _pick_wijk(addr: dict) -> str | None:
    """Voorkeur: neighbourhood > suburb (vermijd 'quarter' want dat is te grof)."""
    return addr.get("neighbourhood") or addr.get("suburb") or addr.get("city_district")


def _nominatim(client: httpx.Client, q: str) -> dict:
    """Forward search. Geeft lat/lng/wijk."""
    params = {
        "q": q, "format": "json", "limit": 1,
        "countrycodes": "nl", "addressdetails": 1,
    }
    try:
        r = client.get(NOMINATIM_URL, params=params, timeout=15)
        r.raise_for_status()
        results = r.json()
        if not results:
            return {}
        first = results[0]
        addr = first.get("address") or {}
        return {
            "lat": float(first["lat"]),
            "lng": float(first["lon"]),
            "wijk": _pick_wijk(addr),
        }
    except Exception as e:
        log.warning("nominatim search faalt voor %r: %s", q, e)
        return {}


def _nominatim_reverse(client: httpx.Client, lat: float, lng: float) -> dict:
    """Reverse: lat/lng → wijk via neighbourhood."""
    params = {
        "lat": lat, "lon": lng, "format": "json",
        "addressdetails": 1, "zoom": 17,
    }
    try:
        r = client.get(NOMINATIM_REVERSE_URL, params=params, timeout=15)
        r.raise_for_status()
        result = r.json()
        addr = result.get("address") or {}
        return {"wijk": _pick_wijk(addr)}
    except Exception as e:
        log.warning("nominatim reverse faalt voor %r,%r: %s", lat, lng, e)
        return {}


def _jitter(key: str, radius_m: float = 60.0) -> tuple[float, float]:
    h = hashlib.md5(key.encode("utf-8")).digest()
    angle = (h[0] << 8 | h[1]) / 65535.0 * 2 * math.pi
    dist = ((h[2] << 8 | h[3]) / 65535.0) * radius_m
    dlat = (dist * math.cos(angle)) / 111111.0
    dlng = (dist * math.sin(angle)) / (111111.0 * math.cos(math.radians(50.85)))
    return dlat, dlng


def enrich(listings: Iterable[Listing]) -> dict:
    """Vul lat/lng en (indien nog leeg) wijk in op listings.

    Strategie:
    - Listing met lat/lng + zonder wijk → reverse geocode (precies)
    - Listing zonder lat/lng → forward geocode op postcode/straat (vult beide)
    """
    cache = _load_cache()
    api_calls = 0

    headers = {"User-Agent": NOMINATIM_UA, "Accept-Language": "nl"}

    with httpx.Client(headers=headers) as client:
        for listing in listings:
            needs_coords = listing.lat is None or listing.lng is None
            needs_wijk = not (listing.wijk or "").strip()

            if not needs_coords and not needs_wijk:
                continue

            listing.postcode = listing.postcode or extract_postcode(listing.address or "")

            if not needs_coords:
                # Reverse lookup voor wijk
                key = f"rev:{round(listing.lat, 5)},{round(listing.lng, 5)}"
                entry = cache.get(key)
                if entry is None:
                    if api_calls > 0:
                        time.sleep(RATE_LIMIT_SEC)
                    result = _nominatim_reverse(client, listing.lat, listing.lng)
                    entry = {"wijk": result.get("wijk")}
                    cache[key] = entry
                    api_calls += 1
                if needs_wijk and entry.get("wijk"):
                    listing.wijk = entry["wijk"]
            else:
                # Forward lookup voor coords (+ wijk)
                q = _query_key(listing)
                if not q:
                    continue
                entry = cache.get(q)
                if entry is None or "wijk" not in entry:
                    if api_calls > 0:
                        time.sleep(RATE_LIMIT_SEC)
                    result = _nominatim(client, q)
                    entry = {
                        "lat": result.get("lat"),
                        "lng": result.get("lng"),
                        "wijk": result.get("wijk"),
                    }
                    cache[q] = entry
                    api_calls += 1
                if entry.get("lat") is not None and entry.get("lng") is not None:
                    dlat, dlng = _jitter(listing.key)
                    listing.lat = entry["lat"] + dlat
                    listing.lng = entry["lng"] + dlng
                if needs_wijk and entry.get("wijk"):
                    listing.wijk = entry["wijk"]

    _save_cache(cache)
    log.info("geocode: %d nieuwe lookups, cache nu %d entries", api_calls, len(cache))
    return cache
