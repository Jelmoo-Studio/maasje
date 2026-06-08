"""Mijn Huis en Ik scraper — JSON API (OGonline platform).

Endpoint geeft alle huur-listings terug; we filteren op city Maastricht
en statusOrig 'available'. Bevat rijke gestructureerde data incl. wijk,
postcode, lat/lng, gestoffeerd, balkon/tuin, beschikbaarheid.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx

import config
from scrapers.base import Listing, hash_id, normalize_text

log = logging.getLogger(__name__)

SOURCE = "mijnhuisenik"
BASE = "https://www.mijnhuisenik.com"
API_URL = f"{BASE}/nl/realtime-listings/consumer/rentals"


def _classify(item: dict) -> str:
    apt = (item.get("apartmentType") or "").lower()
    main = (item.get("mainType") or "").lower()
    if "studio" in apt:
        return "studio"
    if apt == "student_room" or "student" in apt or "room" in apt:
        return "kamer"  # zal uitgesloten worden
    if main == "apartment":
        return "appartement"
    if main == "house":
        return "appartement"
    return "overig"


def _availability_flag(text: str) -> str:
    t = (text or "").lower().strip()
    if not t:
        return "unknown"
    if "direct" in t:
        return "now"
    if "aug" in t or "sept" in t:
        return "aug"
    return "later"


def _parse_item(item: dict) -> Listing | None:
    if (item.get("city") or "").lower() != "maastricht":
        return None
    if item.get("statusOrig") != "available":
        return None
    if not item.get("isRentals"):
        return None

    listing_id = item.get("_id") or ""
    rel_url = item.get("url") or ""
    url = urljoin(BASE + "/", rel_url) if rel_url else ""
    if not url:
        return None

    listing_type = _classify(item)
    address = normalize_text(item.get("address") or "")
    postcode = (item.get("zipcode") or "").strip() or None
    wijk = item.get("neighbourhood") or item.get("district") or ""
    if wijk:
        wijk = normalize_text(wijk)

    price_int = item.get("rentalsPrice") or item.get("price") or 0
    price_raw = item.get("price") or (f"€ {price_int}" if price_int else "")
    price_raw = normalize_text(price_raw.replace("&euro;", "€"))

    surface = item.get("livingSurface") or None
    if isinstance(surface, str):
        try:
            surface = int(surface)
        except ValueError:
            surface = None
    rooms = item.get("rooms") or None

    lat = item.get("lat")
    lng = item.get("lng")
    if isinstance(lat, str):
        try: lat = float(lat)
        except ValueError: lat = None
    if isinstance(lng, str):
        try: lng = float(lng)
        except ValueError: lng = None

    is_furnished = bool(item.get("isFurnished"))
    is_partly = bool(item.get("isPartlyFurnished"))
    is_decorated = bool(item.get("isDecorated"))
    is_gestoffeerd = is_furnished or is_partly or is_decorated
    is_gemeubileerd = is_furnished
    has_balcony = bool(item.get("balcony"))
    has_garden = bool(item.get("garden"))
    acceptance = item.get("acceptance") or ""
    avail_flag = _availability_flag(acceptance)
    photo = item.get("photo") or ""

    type_label = "Studio" if listing_type == "studio" else (
        "Appartement" if listing_type == "appartement" else "Woning"
    )
    title = f"{type_label} {address}".strip()

    extra = {
        "furnishing_raw": item.get("decoration") or "",
        "available_raw": acceptance,
        "available_flag": avail_flag,
        "is_gestoffeerd": is_gestoffeerd,
        "is_gemeubileerd": is_gemeubileerd,
        "has_balcony": has_balcony,
        "has_garden": has_garden,
        "photo": photo,
        "mhi_type": item.get("type"),
    }

    return Listing(
        source=SOURCE,
        listing_id=listing_id or hash_id(url),
        url=url,
        title=title,
        price=int(price_int) if isinstance(price_int, (int, float)) and price_int else None,
        price_raw=price_raw,
        type=listing_type,
        address=address,
        city="Maastricht",
        postcode=postcode,
        wijk=wijk,
        surface_m2=surface,
        rooms=rooms,
        lat=lat,
        lng=lng,
        extra=extra,
    )


def fetch() -> list[Listing]:
    headers = {
        "User-Agent": config.USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "nl-NL,nl;q=0.9",
    }
    log.info("mijnhuisenik: GET %s", API_URL)
    with httpx.Client(headers=headers, follow_redirects=True, timeout=config.REQUEST_TIMEOUT) as client:
        r = client.get(API_URL)
        r.raise_for_status()
        items = r.json()

    out: list[Listing] = []
    seen: set[str] = set()
    for item in items:
        listing = _parse_item(item)
        if not listing:
            continue
        if listing.key in seen:
            continue
        seen.add(listing.key)
        out.append(listing)
    log.info("mijnhuisenik: %d unieke listings", len(out))
    return out
