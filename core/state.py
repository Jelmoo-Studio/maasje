"""State opslag: alle eerder geziene listings."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from scrapers.base import Listing


STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {"listings": {}, "site_health": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"listings": {}, "site_health": {}}
    data.setdefault("listings", {})
    data.setdefault("site_health", {})
    return data


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def diff_and_update(state: dict, listings: Iterable[Listing]) -> tuple[list[Listing], list[Listing]]:
    """Markeer nieuwe listings en update last_seen voor bestaande.

    Returns (new_listings, currently_available_listings).
    """
    now = _now()
    seen_keys: set[str] = set()
    new_listings: list[Listing] = []
    available: list[Listing] = []

    stored = state["listings"]

    for listing in listings:
        seen_keys.add(listing.key)
        record = stored.get(listing.key)
        if record is None:
            listing.first_seen = now
            listing.last_seen = now
            stored[listing.key] = listing.to_dict()
            new_listings.append(listing)
        else:
            listing.first_seen = record.get("first_seen", now)
            listing.last_seen = now
            merged = {**record, **listing.to_dict()}
            merged["first_seen"] = listing.first_seen
            merged["last_seen"] = now
            stored[listing.key] = merged
        available.append(listing)

    for key, record in list(stored.items()):
        if key not in seen_keys:
            record.setdefault("first_seen", now)

    return new_listings, available


def update_site_health(state: dict, source: str, count: int, ok: bool, error: str = "") -> None:
    health = state["site_health"]
    entry = health.get(source, {"empty_streak": 0, "fail_streak": 0})
    if not ok:
        entry["fail_streak"] = entry.get("fail_streak", 0) + 1
        entry["last_error"] = error
    else:
        entry["fail_streak"] = 0
        entry["last_error"] = ""
        if count == 0:
            entry["empty_streak"] = entry.get("empty_streak", 0) + 1
        else:
            entry["empty_streak"] = 0
    entry["last_count"] = count
    entry["last_run"] = _now()
    health[source] = entry
