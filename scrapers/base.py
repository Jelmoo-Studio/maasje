"""Gedeeld datamodel en helpers voor scrapers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Listing:
    source: str
    listing_id: str
    url: str
    title: str
    price: Optional[int]
    price_raw: str
    type: str
    address: str = ""
    city: str = ""
    surface_m2: Optional[int] = None
    rooms: Optional[int] = None
    date_listed: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    postcode: Optional[str] = None
    wijk: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.listing_id}"

    def to_dict(self) -> dict:
        return asdict(self)


_PRICE_RE = re.compile(r"(\d[\d.\s,]*)")


def parse_price(text: str) -> Optional[int]:
    """Pak het eerste getal uit een prijsstring en geef het terug als hele euro's."""
    if not text:
        return None
    cleaned = text.replace("\xa0", " ")
    match = _PRICE_RE.search(cleaned)
    if not match:
        return None
    digits = re.sub(r"[^\d]", "", match.group(1))
    if not digits:
        return None
    try:
        value = int(digits)
    except ValueError:
        return None
    if value < 50:
        return None
    return value


def parse_int(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def hash_id(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"|")
    return h.hexdigest()[:16]


def normalize_wijk(text: str) -> str:
    """lowercase + strip diacritics + vervang koppeltekens door spaties."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    no_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", no_accents.lower().replace("-", " ")).strip()


_WIJK_PAREN_RE = re.compile(r"\(([^)]+)\)")


def extract_wijk_from_subtitle(subtitle: str) -> Optional[str]:
    """Pak het deel tussen haakjes uit 'Postcode Stad (Wijk)'."""
    if not subtitle:
        return None
    m = _WIJK_PAREN_RE.search(subtitle)
    if not m:
        return None
    return normalize_text(m.group(1))


def classify_type(text: str) -> str:
    t = (text or "").lower()
    if "studio" in t:
        return "studio"
    if "appartement" in t or "apartment" in t:
        return "appartement"
    if "kamer" in t or "room" in t:
        return "kamer"
    if "huis" in t or "woning" in t:
        return "appartement"
    return "overig"
