"""Kalshi crawler configuration — endpoints, categories, rate limits."""
import os
from pathlib import Path

PLATFORM = "kalshi"

# API endpoints
PROD_BASE = "https://api.elections.kalshi.com/trade-api/v2"
DEMO_BASE = "https://demo-api.kalshi.co/trade-api/v2"

# Auth — set via environment or .env
KALSHI_API_KEY_ID = os.getenv("KALSHI_API_KEY_ID", "")
KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
KALSHI_EMAIL = os.getenv("KALSHI_EMAIL", "")
KALSHI_PASSWORD = os.getenv("KALSHI_PASSWORD", "")

# Rate limiting
RATE_LIMIT_RPS = 10          # 10 reads/sec free tier
RATE_LIMIT_DELAY = 0.12      # slight buffer over 1/10
BACKOFF_BASE = 2.0
BACKOFF_MAX = 120.0
MAX_RETRIES = 3

# Polling
POLL_INTERVAL_SECONDS = 900  # 15 minutes

# Market categories for filtering
CATEGORIES = {
    "fed":      ["FOMC", "FED", "RATE", "INTEREST"],
    "econ":     ["CPI", "GDP", "JOBS", "NONFARM", "UNEMPLOYMENT", "INFLATION", "PPI"],
    "weather":  ["HURRICANE", "TEMPERATURE", "WEATHER", "CLIMATE"],
    "election": ["PRESIDENT", "SENATE", "HOUSE", "GOVERNOR", "ELECTION", "VOTE"],
    "crypto":   ["BITCOIN", "BTC", "ETH", "CRYPTO"],
}

ALL_CATEGORIES = list(CATEGORIES.keys())

# Volume anomaly threshold — flag if volume > N * trailing avg
VOLUME_ANOMALY_MULTIPLIER = 3.0

# Price move threshold — flag if price shifts > N points in one poll
PRICE_MOVE_THRESHOLD = 0.10  # 10 percentage points

# Logging
LOG_DIR = Path(__file__).parent / "logs"

# Pagination
PAGE_SIZE = 100  # Kalshi API max cursor page size
