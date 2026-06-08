# Deployment

Eenmalige stappen om de tool live te zetten op GitHub.

## 1. Repo aanmaken + pushen

```bash
cd huur-scraper
gh repo create <repo-naam> --private --source=. --remote=origin --push
```

## 2. GitHub Pages aanzetten

```bash
gh api repos/Jelmoo-Studio/<repo-naam>/pages \
  -X POST \
  -f source[branch]=main \
  -f source[path]=/docs
```

Of via UI: **Settings → Pages → Source: `Deploy from a branch` → `main` / `/docs`**.

De URL wordt: `https://Jelmoo-Studio.github.io/<repo-naam>/`

## 3. Telegram-bot opzetten (optioneel)

1. Open [@BotFather](https://t.me/BotFather) in Telegram
2. Stuur `/newbot`, kies een naam (bv "Huur Maastricht"), kies een username (moet eindigen op `bot`)
3. Bewaar het token (lange string)
4. Stuur je nieuwe bot een berichtje (`/start` of wat dan ook) zodat hij jou kent
5. Open in browser: `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Zoek `"chat":{"id": ...}` — dat getal is je chat_id

Zet de secrets:

```bash
gh secret set TELEGRAM_BOT_TOKEN --body "<token>"
gh secret set TELEGRAM_CHAT_ID --body "<chat_id>"
```

## 4. Eerste run handmatig triggeren

```bash
gh workflow run scrape.yml
```

Of via UI: **Actions → scrape → Run workflow**.

Na ±30 sec staat het dashboard op de Pages-URL. Hierna draait de cron elk uur vanzelf.

## 5. Bookmark + dagelijks gebruiken

- Bookmark `https://Jelmoo-Studio.github.io/<repo-naam>/`
- Je krijgt een Telegram-bericht per nieuwe match (geen uurspam)
- Bewaar/verberg via ♥ / ✕ knoppen op de cards

## Beheer

| Wat | Hoe |
|---|---|
| Run handmatig | `gh workflow run scrape.yml` |
| Logs bekijken | `gh run list --workflow scrape.yml` |
| Filters aanpassen | edit `config.py` → push |
| Wijken aanpassen | edit `config.py` → `WIJKEN` + `WIJKEN_DISPLAY` |
| Workflow pauzeren | `gh workflow disable scrape.yml` |
