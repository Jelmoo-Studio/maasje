"""Huurwoningen.com scraper — server-side HTML, separate URLs per type."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

import config
import re

from scrapers.base import (
    Listing,
    classify_type,
    extract_wijk_from_subtitle,
    hash_id,
    normalize_text,
    parse_int,
    parse_price,
)

_POSTCODE_RE = re.compile(r"(\d{4})\s*([A-Z]{2})")

log = logging.getLogger(__name__)

SOURCE = "huurwoningen"
BASE = "https://www.huurwoningen.com"

# URL-filter iets ruimer dan onze hard max om borderline incl./excl. cases mee te krijgen.
# Filter slaat alsnog strikt af op config.MAX_PRICE.
_URL_PRICE_BUFFER = 100

URLS = [
    f"{BASE}/appartement/huren/maastricht/?price=0-{config.MAX_PRICE + _URL_PRICE_BUFFER}",
    f"{BASE}/studio/huren/maastricht/?price=0-{config.MAX_PRICE + _URL_PRICE_BUFFER}",
]


def _parse(html: str) -> list[Listing]:
    tree = HTMLParser(html)
    listings: list[Listing] = []

    for section in tree.css("section.listing-search-item"):
        site_id = section.attributes.get("data-listing-search-item-id") or ""
        link_node = section.css_first("a.listing-search-item__link--depiction")
        href = (link_node.attributes.get("href") if link_node else None) or ""
        if not href:
            continue
        url = urljoin(BASE + "/", href)

        title = normalize_text(
            section.css_first(".listing-search-item__title").text(strip=True)
            if section.css_first(".listing-search-item__title")
            else ""
        )
        subtitle = normalize_text(
            section.css_first(".listing-search-item__sub-title").text(strip=True)
            if section.css_first(".listing-search-item__sub-title")
            else ""
        )
        price_raw = normalize_text(
            section.css_first(".listing-search-item__price").text(strip=True)
            if section.css_first(".listing-search-item__price")
            else ""
        )

        surface_node = section.css_first(
            ".illustrated-features__item--surface-area"
        )
        rooms_node = section.css_first(
            ".illustrated-features__item--number-of-rooms"
        )

        surface_m2 = parse_int(surface_node.text(strip=True)) if surface_node else None
        rooms = parse_int(rooms_node.text(strip=True)) if rooms_node else None

        # Classify type — title starts with "Appartement" / "Studio" / etc.
        listing_type = classify_type(title)

        # City / address — subtitle is like "6228 GK Maastricht (De Heeg)"
        city = "Maastricht" if "maastricht" in subtitle.lower() else ""
        pc_match = _POSTCODE_RE.search((subtitle or "").upper())
        postcode = f"{pc_match.group(1)} {pc_match.group(2)}" if pc_match else None
        wijk = extract_wijk_from_subtitle(subtitle)

        listing_id = site_id or hash_id(url)

        listings.append(
            Listing(
                source=SOURCE,
                listing_id=listing_id,
                url=url,
                title=title or "(geen titel)",
                price=parse_price(price_raw),
                price_raw=price_raw,
                type=listing_type,
                address=subtitle,
                city=city,
                postcode=postcode,
                wijk=wijk,
                surface_m2=surface_m2,
                rooms=rooms,
            )
        )
    return listings


def fetch() -> list[Listing]:
    headers = {"User-Agent": config.USER_AGENT, "Accept-Language": "nl-NL,nl;q=0.9"}
    out: list[Listing] = []
    seen_keys: set[str] = set()

    with httpx.Client(
        headers=headers,
        follow_redirects=True,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        for url in URLS:
            log.info("huurwoningen: GET %s", url)
            r = client.get(url)
            r.raise_for_status()
            for listing in _parse(r.text):
                if listing.key in seen_keys:
                    continue
                seen_keys.add(listing.key)
                out.append(listing)
    log.info("huurwoningen: %d unieke listings", len(out))
    return out
