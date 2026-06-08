"""Pro Housing scraper — server-side HTML, één pagina met alle aanbod.

Pro Housing geeft veel data in de HTML: lat/lng, gestoffeerd, beschikbaarheid,
oppervlakte. We pakken alles wat verbruikbaar is en plaatsen extra info
in listing.extra zodat het dashboard 'gestoffeerd' en 'vanaf augustus'
als al-bekend kan markeren.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

import config
from scrapers.base import (
    Listing,
    classify_type,
    hash_id,
    normalize_text,
    parse_int,
    parse_price,
)

log = logging.getLogger(__name__)

SOURCE = "prohousing"
BASE = "https://www.pro-housing.nl"
LIST_URL = f"{BASE}/nl/te-huur"


def _table_rows(item) -> dict[str, str]:
    """Parse de <td>-paren met icon → tekst uit .houseDetailList."""
    out: dict[str, str] = {}
    for tr in item.css(".houseDetailList tr"):
        tds = tr.css("td")
        if len(tds) < 2:
            continue
        icon = tds[0].css_first("i")
        icon_cls = (icon.attributes.get("class") or "") if icon else ""
        value = normalize_text(tds[1].text(strip=True))
        if "fa-map-marker" in icon_cls:
            out["location"] = value
        elif "fa-home" in icon_cls:
            out["type"] = value
        elif "fa-bed" in icon_cls:
            out["bedrooms"] = value
        elif "icon-curtain" in icon_cls:
            out["furnishing"] = value
        elif "fa-calendar" in icon_cls:
            out["available"] = value
    return out


def _filters_span(item, key: str) -> str:
    node = item.css_first(f".filters .{key}")
    return normalize_text(node.text(strip=True)) if node else ""


def _parse_latlng(text: str) -> tuple[float | None, float | None]:
    m = re.match(r"\s*([-\d.]+)\s*,\s*([-\d.]+)", text or "")
    if not m:
        return None, None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None, None


_AUG_RE = re.compile(r"\b(aug|augustus|sept|september)\b", re.I)


def _availability_flag(text: str) -> str:
    """Geef 'now', 'aug', 'later', 'unknown' terug op basis van de string."""
    t = (text or "").lower().strip()
    if not t or t == "0":
        return "unknown"
    if "direct" in t or "per direct" in t:
        return "now"
    if _AUG_RE.search(t):
        return "aug"
    # Probeer datum YYYY-MM-DD of DD-MM-YYYY
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        month = int(m.group(2))
        if month in (8, 9):
            return "aug"
        return "later"
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})", t)
    if m:
        month = int(m.group(2))
        if month in (8, 9):
            return "aug"
        return "later"
    return "unknown"


def _parse_item(item) -> Listing | None:
    classes = item.attributes.get("class") or ""
    if "unavailable" in classes:
        return None

    rows = _table_rows(item)
    location = rows.get("location") or ""
    if "maastricht" not in location.lower():
        return None

    card = item.css_first(".houseCard")
    data_id = (card.attributes.get("data-id") if card else "") or ""

    # Link
    link = item.css_first("a[href*='/te-huur/']")
    href = link.attributes.get("href") if link else ""
    if not href:
        return None
    url = urljoin(BASE + "/", href)

    title = normalize_text(
        item.css_first(".houseCardHeader h2").text(strip=True)
        if item.css_first(".houseCardHeader h2") else ""
    )
    price_raw = normalize_text(
        item.css_first(".houseCardHeader h4").text(strip=True)
        if item.css_first(".houseCardHeader h4") else ""
    )

    listing_type = classify_type(rows.get("type", ""))
    bedrooms = parse_int(rows.get("bedrooms", ""))
    surface = parse_int(_filters_span(item, "living-space"))
    lat, lng = _parse_latlng(_filters_span(item, "latlng"))

    furnishing = rows.get("furnishing", "").lower()
    is_gestoffeerd = "gestoffeerd" in furnishing or "gemeubileerd" in furnishing
    is_gemeubileerd = "gemeubileerd" in furnishing
    avail = rows.get("available", "")
    avail_flag = _availability_flag(avail)

    listing_id = data_id or hash_id(url)

    extra = {
        "furnishing_raw": rows.get("furnishing", ""),
        "available_raw": avail,
        "available_flag": avail_flag,
        "is_gestoffeerd": is_gestoffeerd,
        "is_gemeubileerd": is_gemeubileerd,
    }

    return Listing(
        source=SOURCE,
        listing_id=listing_id,
        url=url,
        title=f"{(rows.get('type') or 'Woning').capitalize()} {title}".strip(),
        price=parse_price(price_raw),
        price_raw=price_raw,
        type=listing_type,
        address=f"{title}, Maastricht" if title else location,
        city="Maastricht",
        surface_m2=surface,
        rooms=bedrooms,
        date_listed=None,
        lat=lat,
        lng=lng,
        extra=extra,
    )


def fetch() -> list[Listing]:
    headers = {"User-Agent": config.USER_AGENT, "Accept-Language": "nl-NL,nl;q=0.9"}
    out: list[Listing] = []
    seen_keys: set[str] = set()

    with httpx.Client(
        headers=headers, follow_redirects=True, timeout=config.REQUEST_TIMEOUT
    ) as client:
        log.info("prohousing: GET %s", LIST_URL)
        r = client.get(LIST_URL)
        r.raise_for_status()
        tree = HTMLParser(r.text)
        for item in tree.css(".houseItem"):
            listing = _parse_item(item)
            if listing and listing.key not in seen_keys:
                seen_keys.add(listing.key)
                out.append(listing)
    log.info("prohousing: %d unieke listings", len(out))
    return out
