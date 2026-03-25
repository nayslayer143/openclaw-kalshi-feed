# openclaw-kalshi-feed

Kalshi prediction-market crawler for the OpenClaw signal bus.

## What This Does

Polls the Kalshi REST API for active prediction markets (Fed decisions, economic indicators, weather, elections), extracts price/volume signals, detects movers and volume anomalies, and writes normalized signals to `~/openclaw/autoresearch/signals/kalshi.json` + local SQLite.

## File Map

| File | Purpose | Max Lines |
|------|---------|-----------|
| `crawler.py` | Main entry, CLI, auth, API polling | 300 |
| `config.py` | Endpoints, categories, thresholds | 50 |
| `signals.py` | Signal extraction + normalization | 100 |
| `storage.py` | Shared storage (SQLite + JSON + archive) | 100 |

## Key Commands

```bash
python crawler.py                    # poll all markets (15min loop)
python crawler.py --category fed     # Fed-related only
python crawler.py --category econ    # economic indicators
python crawler.py --movers           # biggest movers only
python crawler.py --demo             # demo sandbox
python crawler.py --once             # single pass
```

## Auth

Requires either RSA key pair (`KALSHI_API_KEY_ID` + `KALSHI_PRIVATE_KEY_PATH`) or email/password in `.env`. Falls back to unauthenticated if neither is set.

## Constraints

- Follow `~/openclaw/CONSTRAINTS.md` at all times
- Never exceed file line budgets above
- Total project under 600 lines
- Stdlib + httpx + python-dotenv + cryptography only
