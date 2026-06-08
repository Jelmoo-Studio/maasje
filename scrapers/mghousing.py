"""M&G Housing scraper — embedded JSON in SSR HTML (Payload/SvelteKit).

De /aanbod-pagina rendert een <script type="application/json"> tag met
de Listings.docs lijst. We pakken die. Detail-URLs construeren we als
https://mghousing.nl/aanbod/huur/{id}.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

import config
from scrapers.base import Listing, normalize_text

log = logging.getLogger(__name__)

SOURCE = "mghousing"
BASE = "https://mghousing.nl"
LIST_URL = f"{BASE}/aanbod"

_SCRIPT_RE = re.compile(
    r'<script[^>]*application/json[^>]*>(.*?)</script>', re.S
)


def _extract_listings(html: str) -> list[dict]:
    """Loop alle JSON-scripts af, retourneer eerste Listings.docs lijst."""
    for m in _SCRIPT_RE.finditer(html):
        raw = m.group(1).strip()
        try:
            wrapper = json.loads(raw)
        except json.JSONDecodeError:
            continue
        body = wrapper.get("body")
        if not isinstance(body, str):
            continue
        try:
            inner = json.loads(body)
        except json.JSONDecodeError:
            continue
        listings = (
            (inner.get("data") or {}).get("Listings", {}).get("docs")
        )
        if isinstance(listings, list) and listings:
            return listings
    return []


def _classify(item: dict, surface: int | None, rooms: int | None) -> str:
    types = ((item.get("details") or {}).get("type") or {}).get("mainType") or []
    type_ids = [
        (t.get("identifier") if isinstance(t, dict) else str(t)).lower()
        for t in types
    ]
    title = (item.get("title") or "").lower()
    if "studio" in title or "studio" in type_ids:
        return "studio"
    if any(t in type_ids for t in ("apartment", "house")):
        # Klein 1-kamer ≤25m² behandelen we als studio
        if surface is not None and surface <= 25 and (rooms or 0) <= 1:
            return "studio"
        return "appartement"
    return "overig"


def _availability_flag(date_str: str) -> str:
    if not date_str:
        return "unknown"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if not m:
        return "unknown"
    month = int(m.group(2))
    if month in (8, 9):
        return "aug"
    if month <= 7:
        return "now"
    return "later"


def _parse_item(item: dict) -> Listing | None:
    if item.get("status") != "available":
        return None
    if not (item.get("price") or {}).get("isRentals"):
        return None

    addr = item.get("address") or {}
    if (addr.get("city") or "").lower() != "maastricht":
        return None

    listing_id = item.get("id") or ""
    if not listing_id:
        return None
    url = f"{BASE}/aanbod/huur/{listing_id}"

    street = normalize_text(addr.get("street") or "")
    house_nr = normalize_text(addr.get("houseNumber") or "")
    house_ext = normalize_text(addr.get("houseNumberExtension") or "")
    address_parts = [street]
    if house_nr:
        address_parts.append(house_nr)
    if house_ext:
        address_parts.append(house_ext)
    address = " ".join(address_parts).strip()
    postcode = (addr.get("postalCode") or "").strip() or None
    if postcode and len(postcode) == 6 and " " not in postcode:
        postcode = f"{postcode[:4]} {postcode[4:]}"

    location = addr.get("location") or []
    lat = location[0] if len(location) >= 2 else None
    lng = location[1] if len(location) >= 2 else None
    if isinstance(lat, str):
        try: lat = float(lat)
        except ValueError: lat = None
    if isinstance(lng, str):
        try: lng = float(lng)
        except ValueError: lng = None

    rentals = (item.get("price") or {}).get("rentals") or {}
    price = rentals.get("amount")
    if not isinstance(price, (int, float)) or price is None:
        return None
    price = int(price)
    price_raw = f"€ {price} p.m."
    if rentals.get("includesGas") and rentals.get("includesWater") and rentals.get("includesElectricity"):
        price_raw += " incl."
    is_furnished = bool(rentals.get("isFurnished"))
    is_decorated = bool(rentals.get("isDecorated"))
    is_partly = bool(rentals.get("isPartlyFurnished"))
    is_gestoffeerd = is_furnished or is_decorated or is_partly

    details = item.get("details") or {}
    surface = (details.get("surface") or {}).get("amount")
    rooms = (details.get("rooms") or {}).get("amount")
    if isinstance(surface, str):
        try: surface = int(surface)
        except ValueError: surface = None
    if isinstance(rooms, str):
        try: rooms = int(rooms)
        except ValueError: rooms = None

    listing_type = _classify(item, surface, rooms)

    accept = (item.get("price") or {}).get("acceptance") or {}
    accept_date = accept.get("date") or ""
    avail_flag = _availability_flag(accept_date)

    type_label = "Studio" if listing_type == "studio" else (
        "Appartement" if listing_type == "appartement" else "Woning"
    )
    title = f"{type_label} {address or item.get('title') or ''}".strip()

    extra = {
        "furnishing_raw": "gestoffeerd" if is_gestoffeerd else "",
        "available_raw": accept_date,
        "available_flag": avail_flag,
        "is_gestoffeerd": is_gestoffeerd,
        "is_gemeubileerd": is_furnished,
    }

    return Listing(
        source=SOURCE,
        listing_id=listing_id,
        url=url,
        title=title,
        price=price,
        price_raw=price_raw,
        type=listing_type,
        address=address,
        city="Maastricht",
        postcode=postcode,
        surface_m2=surface,
        rooms=rooms,
        lat=lat,
        lng=lng,
        extra=extra,
    )


def fetch() -> list[Listing]:
    headers = {"User-Agent": config.USER_AGENT, "Accept-Language": "nl-NL,nl;q=0.9"}
    log.info("mghousing: GET %s", LIST_URL)
    with httpx.Client(headers=headers, follow_redirects=True, timeout=config.REQUEST_TIMEOUT) as client:
        r = client.get(LIST_URL)
        r.raise_for_status()
        raw_items = _extract_listings(r.text)

    out: list[Listing] = []
    seen: set[str] = set()
    for item in raw_items:
        listing = _parse_item(item)
        if not listing:
            continue
        if listing.key in seen:
            continue
        seen.add(listing.key)
        out.append(listing)
    log.info("mghousing: %d unieke listings", len(out))
    return out
