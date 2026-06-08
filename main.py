"""Orchestratie: run alle scrapers, filter, diff, notify, dashboard."""

from __future__ import annotations

import importlib
import logging
import random
import sys
import time
from pathlib import Path

# Zorg dat sub-packages vindbaar zijn als script wordt aangeroepen.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
from core import dashboard, filters, geocode, notify, state  # noqa: E402
from scrapers.base import Listing  # noqa: E402


SCRAPERS = (
    "scrapers.huurwoningen",
    "scrapers.directwonen",
    "scrapers.prohousing",
    "scrapers.mijnhuisenik",
    "scrapers.mghousing",
)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run() -> int:
    _setup_logging()
    log = logging.getLogger("main")

    st = state.load_state()
    all_listings: list[Listing] = []

    for idx, dotted in enumerate(SCRAPERS):
        module = importlib.import_module(dotted)
        source = getattr(module, "SOURCE", dotted.split(".")[-1])
        if idx > 0:
            time.sleep(random.uniform(*config.INTER_SITE_DELAY_RANGE))
        try:
            listings = module.fetch()
            log.info("%s: %d listings", source, len(listings))
            state.update_site_health(st, source, len(listings), ok=True)
            all_listings.extend(listings)
        except NotImplementedError as e:
            log.info("%s: nog niet geimplementeerd (%s)", source, e)
            continue
        except Exception as e:  # noqa: BLE001
            log.exception("%s: scraper crashte: %s", source, e)
            state.update_site_health(st, source, 0, ok=False, error=str(e))

    # Stap 1: basis-filter (type/prijs/Maastricht) vóór geocode om API-calls te besparen.
    basic = filters.apply_basic(all_listings)
    log.info("basic filter: %d/%d listings", len(basic), len(all_listings))

    # Hergebruik eerder geocode-coords + wijk uit state.
    for l in basic:
        record = st["listings"].get(l.key)
        if record:
            if l.lat is None:
                l.lat = record.get("lat")
            if l.lng is None:
                l.lng = record.get("lng")
            if not l.postcode:
                l.postcode = record.get("postcode")
            if not l.wijk:
                l.wijk = record.get("wijk")

    # Stap 2: geocode (vult lat/lng + wijk aan voor listings die ze nog niet hebben).
    try:
        geocode.enrich(basic)
    except Exception as e:  # noqa: BLE001
        log.warning("geocode-stap faalde: %s", e)

    # Stap 3: definitieve filter incl. wijk-check.
    matches = filters.apply(basic)
    log.info("wijk filter: %d/%d listings voldoen", len(matches), len(basic))

    new_listings, current = state.diff_and_update(st, matches)
    log.info("diff: %d nieuwe, %d actueel beschikbaar", len(new_listings), len(current))

    notify.notify(new_listings)

    # Health check: meld sites die te lang leeg blijven.
    for source, entry in st["site_health"].items():
        if entry.get("empty_streak", 0) >= config.HEALTHCHECK_MIN_RUNS_EMPTY:
            notify.warn(
                f"{source} geeft al {entry['empty_streak']} runs 0 resultaten — selector kapot?"
            )

    dashboard.render(current)
    state.save_state(st)

    log.info("klaar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
