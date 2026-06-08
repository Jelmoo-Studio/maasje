# Huur-scraper Maastricht

Persoonlijke tool die elk uur 5 huurwebsites controleert en nieuwe studio's
en appartementen in Maastricht (≤ €1200) meldt via Telegram. Genereert een
overzichtspagina via GitHub Pages.

## Status

| Fase | Site | Status |
|------|------|--------|
| 0 | Scaffold | ✅ |
| 1 | Huurwoningen.com | ✅ |
| 2 | Direct Wonen | ✅ |
| 2 | Pro Housing | ✅ |
| 3 | Mijn Huis en Ik | ✅ (JSON API) |
| 3 | M&G Housing | ✅ (embedded JSON in SSR) |
| 4 | GitHub Pages dashboard | ✅ |
| 5 | GitHub Actions cron | ✅ |
| 6 | Health checks / LLM parsing | ⏳ (basic health al aanwezig) |

## Lokaal draaien

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Zonder Telegram-secrets draait alles, maar meldingen worden alleen gelogd
in plaats van verstuurd. Het overzicht komt in `docs/index.html`.

## Telegram opzetten

1. Praat met [@BotFather](https://t.me/BotFather) in Telegram → `/newbot` →
   bewaar het token.
2. Stuur je nieuwe bot een berichtje, ga dan naar
   `https://api.telegram.org/bot<TOKEN>/getUpdates` → noteer `chat.id`.
3. Zet ze als GitHub Secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

Voor lokaal testen: `export TELEGRAM_BOT_TOKEN=... ; export TELEGRAM_CHAT_ID=...`

## GitHub Pages

Repo Settings → Pages → Source: `Deploy from a branch` → branch `main`, folder
`/docs`. Het overzicht verschijnt op `https://<user>.github.io/<repo>/`.

## Bestanden

- `main.py` — orkestratie
- `config.py` — filters en drempels
- `scrapers/` — één module per site (Listing-objecten teruggeven)
- `core/state.py` — `data/state.json` lezen/schrijven, diff bepalen
- `core/filters.py` — filterregels (Maastricht, type, prijs, uitsluiten)
- `core/notify.py` — Telegram-meldingen
- `core/dashboard.py` — genereert `docs/index.html`
- `.github/workflows/scrape.yml` — uurlijkse cron

## Filters (zie `config.py`)

- Stad: Maastricht
- Type: `studio` of `appartement` (kamer/student/shared wordt uitgesloten)
- Max prijs: €1200
- Voorkeur: ≤ €1050 (gemarkeerd in dashboard + Telegram)
