# openclaw-kalshi-feed

Kalshi prediction-market crawler for OpenClaw. Polls CFTC-regulated prediction markets for Fed decisions, economic indicators, weather events, and elections. Extracts price moves, volume anomalies, and settlement events into the shared signal bus.

## Setup

```bash
cd ~/openclaw/crawlers/openclaw-kalshi-feed
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## API Key Setup

Kalshi requires authentication. Two options:

### Option A: RSA Key Auth (recommended)

1. Log into [kalshi.com](https://kalshi.com) and go to Settings > API Keys
2. Create an API key and download the private key (.pem file)
3. Set in `.env`:
   ```
   KALSHI_API_KEY_ID=your-key-id-here
   KALSHI_PRIVATE_KEY_PATH=/path/to/your/private-key.pem
   ```

### Option B: Email/Password

```
KALSHI_EMAIL=you@example.com
KALSHI_PASSWORD=your-password
```

### No credentials

The crawler will attempt unauthenticated access and show a setup reminder. Use `--demo` to hit the sandbox API which may have lighter requirements.

## Usage

```bash
# Start polling loop (every 15 minutes)
python crawler.py

# Single pass
python crawler.py --once

# Filter by category
python crawler.py --category fed      # Fed rate decisions
python crawler.py --category econ     # CPI, GDP, jobs, etc.
python crawler.py --category weather  # hurricanes, temperature
python crawler.py --category election # political markets
python crawler.py --category crypto   # BTC/ETH markets

# Biggest movers only
python crawler.py --movers

# Use demo/sandbox API
python crawler.py --demo

# Custom poll interval (seconds)
python crawler.py --interval 300
```

## Output

Signals are written to:

- **Signal bus:** `~/openclaw/autoresearch/signals/kalshi.json`
- **Raw snapshots:** `./data/raw/kalshi_YYYYMMDD_HHMMSS.json`
- **SQLite DB:** `./data/signals.db`
- **Archives:** `./data/archive/` (gzipped after 7 days, purged after 90)
- **Logs:** `./logs/kalshi_YYYYMMDD.log`

## Signal Format

Each signal follows the shared OpenClaw schema:

```json
{
  "id": "abc123...",
  "type": "prediction|alert",
  "source_url": "https://kalshi.com/markets/TICKER",
  "ticker_or_market": "KALSHI:TICKER",
  "direction": "bullish|bearish|neutral",
  "confidence": 0.0-1.0,
  "urgency": "realtime|hours|days|weeks"
}
```

## Tests

```bash
python -m pytest tests/ -v
```
