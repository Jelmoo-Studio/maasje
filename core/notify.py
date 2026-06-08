"""Telegram-meldingen voor nieuwe matches. No-op zonder secrets."""

from __future__ import annotations

import logging
import os
from typing import Iterable

import httpx

import config
from core import filters
from scrapers.base import Listing

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _format(listing: Listing) -> str:
    flag = "  ⭐ voorkeur" if filters.is_preferred(listing) else ""
    bits = [f"<b>{listing.title}</b>{flag}"]
    bits.append(f"€{listing.price}/mnd  ·  {listing.type}")

    if listing.wijk:
        bits.append(f"📍 <b>{listing.wijk}</b>")

    extras = []
    if listing.surface_m2:
        extras.append(f"{listing.surface_m2} m²")
    if listing.rooms:
        extras.append(f"{listing.rooms} kamer{'s' if listing.rooms != 1 else ''}")
    if extras:
        bits.append(" · ".join(extras))

    bits.append("⚠ check: gestoffeerd · vanaf aug · huurtoeslag · buiten · keuken apart")
    bits.append(f"<i>{listing.source}</i>")
    bits.append(f'<a href="{listing.url}">Bekijk woning</a>')
    return "\n".join(bits)


def notify(new_listings: Iterable[Listing]) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    listings = list(new_listings)

    if not listings:
        return

    if not token or not chat_id:
        log.info(
            "Telegram secrets ontbreken — skip notify (%d nieuwe matches gevonden).",
            len(listings),
        )
        for l in listings:
            log.info("NIEUW: %s — €%s — %s", l.title, l.price, l.url)
        return

    url = TELEGRAM_API.format(token=token)
    with httpx.Client(timeout=config.REQUEST_TIMEOUT) as client:
        for listing in listings:
            payload = {
                "chat_id": chat_id,
                "text": _format(listing),
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
            try:
                r = client.post(url, json=payload)
                r.raise_for_status()
            except Exception as e:
                log.warning("Telegram-melding mislukt voor %s: %s", listing.key, e)


def warn(message: str) -> None:
    """Korte gezondheidswaarschuwing naar Telegram (of log)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("HEALTH: %s", message)
        return
    try:
        httpx.post(
            TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": f"⚠️ {message}"},
            timeout=config.REQUEST_TIMEOUT,
        )
    except Exception as e:
        log.warning("Health-melding mislukt: %s", e)
