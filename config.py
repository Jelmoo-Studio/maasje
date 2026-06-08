"""Filtercriteria, sitelijst en drempels voor de huur-scraper."""

from __future__ import annotations

CITY = "maastricht"

# Prijsdrempels (in euro per maand, op getoonde hoofdprijs)
MAX_PRICE = 1000          # Hard maximum (Maximaal €1.000 incl.)
PREFERRED_PRICE = 900     # Voorkeur — gemarkeerd in dashboard + Telegram

ALLOWED_TYPES = {"studio", "appartement"}

EXCLUDE_KEYWORDS = (
    "kamer",
    "studentenkamer",
    "room",
    "student",
    "gedeeld",
    "shared",
    "anti-kraak",
    "antikraak",
)

# Gewenste wijken, in genormaliseerde vorm (lowercase, geen koppeltekens, geen diacritics).
# De display-namen staan in WIJKEN_DISPLAY.
WIJKEN = {
    "binnenstad",
    "jekerkwartier",
    "frontenkwartier",
    "jekerdal",
    "villawijk",
    "blauwdorp",
    "wyck",
    "wyckerpoort",
    "sint maartenspoort",
    "ceramique",
    "heugemerveld",
    "randwyck",
    "wittevrouwenveld",
}

WIJKEN_DISPLAY = {
    "binnenstad": "Binnenstad",
    "jekerkwartier": "Jekerkwartier",
    "frontenkwartier": "Frontenkwartier",
    "jekerdal": "Jekerdal",
    "villawijk": "Villawijk",
    "blauwdorp": "Blauwdorp",
    "wyck": "Wyck",
    "wyckerpoort": "Wyckerpoort",
    "sint maartenspoort": "Sint-Maartenspoort",
    "ceramique": "Ceramique",
    "heugemerveld": "Heugemerveld",
    "randwyck": "Randwyck",
    "wittevrouwenveld": "Wittevrouwenveld",
}

# Punten die je niet uit een previewkaart kunt aflezen — toon als checklist op de kaart.
TE_VERIFIEREN = (
    "Gestoffeerd",
    "Vanaf augustus",
    "Huurtoeslag mogelijk",
    "Buitenruimte",
    "Slaap/keuken apart",
    "Privé voorzieningen",
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 20.0

INTER_SITE_DELAY_RANGE = (1.5, 4.0)

HEALTHCHECK_MIN_RUNS_EMPTY = 3
