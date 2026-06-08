"""Filterregels: locatie, wijk, type, prijs, uitsluitwoorden."""

from __future__ import annotations

from typing import Iterable

import config
from scrapers.base import Listing, normalize_wijk


def _has_excluded(listing: Listing) -> bool:
    blob = " ".join([
        listing.title or "",
        listing.address or "",
        listing.type or "",
    ]).lower()
    return any(kw in blob for kw in config.EXCLUDE_KEYWORDS)


def _is_maastricht(listing: Listing) -> bool:
    city = (listing.city or "").lower()
    if config.CITY in city:
        return True
    addr = (listing.address or "").lower()
    return config.CITY in addr


def _wijk_normalized(listing: Listing) -> str:
    return normalize_wijk(listing.wijk or "")


def in_target_wijk(listing: Listing) -> bool:
    w = _wijk_normalized(listing)
    if not w:
        return False
    return w in config.WIJKEN


def passes_basic(listing: Listing) -> bool:
    """Filtercheck die geen wijk-info vereist (te draaien vóór geocode)."""
    if listing.type not in config.ALLOWED_TYPES:
        return False
    if _has_excluded(listing):
        return False
    if not _is_maastricht(listing):
        return False
    if listing.price is None:
        return False
    if listing.price > config.MAX_PRICE:
        return False
    return True


def passes(listing: Listing) -> bool:
    """Volledige filter incl. wijk-check (te draaien ná geocode)."""
    return passes_basic(listing) and in_target_wijk(listing)


def is_preferred(listing: Listing) -> bool:
    return listing.price is not None and listing.price <= config.PREFERRED_PRICE


def apply_basic(listings: Iterable[Listing]) -> list[Listing]:
    return [l for l in listings if passes_basic(l)]


def apply(listings: Iterable[Listing]) -> list[Listing]:
    return [l for l in listings if passes(l)]
