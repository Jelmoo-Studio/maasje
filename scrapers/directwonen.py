"""Direct Wonen scraper — server-side HTML, type-specifieke URLs.

Direct Wonen toont per type ~30 nieuwste listings op de eerste pagina;
?page= heeft geen effect in de HTML (rest is JS). We pakken die top-30
per type, dedupliceren op entityId. Veel detailpagina's vereisen Premium
account, dus de URL kan een paywall zijn — we slaan de redirect-target
op zodat de gebruiker zelf de juiste URL ziet.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, unquote, urlparse

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

SOURCE = "directwonen"
BASE = "https://directwonen.nl"

URLS = [
    f"{BASE}/appartement-huren/maastricht",
    f"{BASE}/studio-huren/maastricht",
]

_ENTITY_ID_RE = re.compile(r"-(\d{5,})(?:$|[?/])")


def _resolve_url(href: str) -> tuple[str, str, bool]:
    """Geef (publieke_url, entityId, paywall_bool) terug.

    Direct Wonen wikkelt sommige detailpagina's in een /premiumaccountpayment
    redirect — die markeren we als paywall.
    """
    if not href:
        return "", "", False
    if href.startswith("/"):
        href = BASE + href
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    is_paywall = "/premiumaccountpayment" in parsed.path.lower()
    target = href
    entity_id = ""
    if "returnUrl" in qs:
        target = unquote(qs["returnUrl"][0])
    if "entityId" in qs:
        entity_id = qs["entityId"][0]
    if not entity_id:
        m = _ENTITY_ID_RE.search(target)
        if m:
            entity_id = m.group(1)
    return target, entity_id, is_paywall


def _parse_section(section, type_hint: str) -> Listing | None:
    link = section.css_first("a.inner-content[href]")
    href = link.attributes.get("href") if link else ""
    url, entity_id, is_paywall = _resolve_url(href or "")
    if not url:
        return None

    type_node = section.css_first(".advert-location-header")
    type_text = normalize_text(type_node.text(strip=True) if type_node else "")

    price_node = section.css_first(".advert-location-price")
    price_raw = normalize_text(price_node.text(strip=True) if price_node else "")

    kale_node = section.css_first(".kale-huur")
    incl_excl = normalize_text(kale_node.text(strip=True) if kale_node else "")
    if incl_excl:
        price_raw = f"{price_raw} {incl_excl}".strip()

    loc_node = section.css_first(".location-text")
    address = normalize_text(loc_node.text(strip=True) if loc_node else "")

    rooms_node = section.css_first(".small-banner.rooms .small-banner-top")
    rooms = parse_int(rooms_node.text(strip=True)) if rooms_node else None

    surface_node = section.css_first(".small-banner.surface .small-banner-top")
    surface = parse_int(surface_node.text(strip=True)) if surface_node else None

    listing_type = classify_type(type_text) or type_hint

    # Bouw titel: "Appartement Grote Gracht" (type + straat)
    street = address.split(",")[0].strip() if address else ""
    title = f"{type_text or type_hint.capitalize()} {street}".strip()
    if not title:
        title = "(geen titel)"

    listing_id = entity_id or hash_id(url)
    city = "Maastricht" if "maastricht" in (address or "").lower() else ""

    return Listing(
        source=SOURCE,
        listing_id=listing_id,
        url=url,
        title=title,
        price=parse_price(price_raw),
        price_raw=price_raw,
        type=listing_type,
        address=address,
        city=city,
        surface_m2=surface,
        rooms=rooms,
        extra={"paywall": is_paywall},
    )


def fetch() -> list[Listing]:
    headers = {"User-Agent": config.USER_AGENT, "Accept-Language": "nl-NL,nl;q=0.9"}
    seen_keys: set[str] = set()
    out: list[Listing] = []

    with httpx.Client(
        headers=headers,
        follow_redirects=True,
        timeout=config.REQUEST_TIMEOUT,
    ) as client:
        for url in URLS:
            type_hint = "appartement" if "appartement" in url else "studio"
            log.info("directwonen: GET %s", url)
            r = client.get(url)
            r.raise_for_status()
            tree = HTMLParser(r.text)
            for section in tree.css(".new-search-advert"):
                listing = _parse_section(section, type_hint)
                if listing and listing.key not in seen_keys:
                    seen_keys.add(listing.key)
                    out.append(listing)
    log.info("directwonen: %d unieke listings", len(out))
    return out
