"""Basic validation tests for openclaw-kalshi-feed."""
import json
import sys
from pathlib import Path

# Allow imports from parent
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import signals as sig_mod
import storage


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

def test_config_endpoints():
    assert "kalshi" in config.PROD_BASE.lower() or "elections" in config.PROD_BASE
    assert "demo" in config.DEMO_BASE.lower() or "kalshi" in config.DEMO_BASE


def test_config_categories():
    assert "fed" in config.CATEGORIES
    assert "econ" in config.CATEGORIES
    assert len(config.ALL_CATEGORIES) >= 4


def test_config_rate_limits():
    assert config.RATE_LIMIT_RPS == 10
    assert config.RATE_LIMIT_DELAY > 0
    assert config.BACKOFF_MAX > config.BACKOFF_BASE


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------

MOCK_MARKET = {
    "ticker": "FED-RATE-HOLD-2026",
    "title": "Fed holds interest rate at March FOMC meeting",
    "yes_bid": 72,
    "no_bid": 28,
    "last_price": 72,
    "volume": 5000,
    "open_interest": 15000,
    "status": "open",
    "close_time": "2026-04-01T18:00:00Z",
}


def test_build_market_signal():
    sig = sig_mod.build_market_signal(MOCK_MARKET)
    assert sig["id"]
    assert sig["type"] == "prediction"
    assert "KALSHI:" in sig["ticker_or_market"]
    assert sig["source_url"].startswith("https://kalshi.com")
    assert sig["confidence"] > 0
    assert sig["urgency"] in ("realtime", "hours", "days", "weeks")
    assert sig["direction"] in ("bullish", "bearish", "neutral", "unknown")
    assert "fed" in sig["tags"]


def test_signal_id_deterministic():
    sig1 = sig_mod.build_market_signal(MOCK_MARKET)
    sig2 = sig_mod.build_market_signal(MOCK_MARKET)
    assert sig1["id"] == sig2["id"]


def test_classify_category():
    tags = sig_mod._classify_category("Fed holds rate", "FED-RATE-HOLD")
    assert "fed" in tags


def test_classify_econ():
    tags = sig_mod._classify_category("CPI above 3%", "CPI-ABOVE-3")
    assert "econ" in tags


def test_infer_direction_bullish():
    assert sig_mod._infer_direction(0.9, None) == "bullish"


def test_infer_direction_bearish():
    assert sig_mod._infer_direction(0.2, None) == "bearish"


def test_infer_direction_neutral():
    assert sig_mod._infer_direction(0.5, None) == "neutral"


def test_infer_direction_move():
    assert sig_mod._infer_direction(0.8, 0.5) == "bullish"
    assert sig_mod._infer_direction(0.3, 0.6) == "bearish"


def test_confidence_scaling():
    low = sig_mod._confidence(100, 200)
    high = sig_mod._confidence(50000, 100000)
    assert high > low


def test_body_length():
    sig = sig_mod.build_market_signal(MOCK_MARKET)
    assert len(sig["body"]) <= 500


# ---------------------------------------------------------------------------
# Mover / anomaly tests
# ---------------------------------------------------------------------------

def test_detect_price_movers():
    prev = {"FED-RATE-HOLD-2026": {"yes_price": 50, "volume": 1000, "open_interest": 5000}}
    movers = sig_mod.detect_price_movers([MOCK_MARKET], prev)
    assert len(movers) >= 1
    assert movers[0]["type"] == "alert"


def test_detect_volume_anomalies():
    prev = {"FED-RATE-HOLD-2026": {"yes_price": 70, "volume": 100, "open_interest": 5000}}
    anomalies = sig_mod.detect_volume_anomalies([MOCK_MARKET], prev)
    assert len(anomalies) >= 1
    assert "VOL" in anomalies[0]["title"]


def test_no_false_movers():
    prev = {"FED-RATE-HOLD-2026": {"yes_price": 71, "volume": 4500, "open_interest": 14000}}
    movers = sig_mod.detect_price_movers([MOCK_MARKET], prev)
    assert len(movers) == 0


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

def test_storage_init(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "LOCAL_DATA", tmp_path / "data")
    monkeypatch.setattr(storage, "RAW_DIR", tmp_path / "data" / "raw")
    monkeypatch.setattr(storage, "ARCHIVE_DIR", tmp_path / "data" / "archive")
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data" / "signals.db")
    monkeypatch.setattr(storage, "OPENCLAW_SIGNALS", tmp_path / "signals")
    storage.init()
    assert (tmp_path / "data" / "raw").exists()
    assert (tmp_path / "data" / "archive").exists()
    assert (tmp_path / "data" / "signals.db").exists()


def test_write_and_read_signals(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "LOCAL_DATA", tmp_path / "data")
    monkeypatch.setattr(storage, "RAW_DIR", tmp_path / "data" / "raw")
    monkeypatch.setattr(storage, "ARCHIVE_DIR", tmp_path / "data" / "archive")
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data" / "signals.db")
    monkeypatch.setattr(storage, "OPENCLAW_SIGNALS", tmp_path / "signals")
    storage.init()
    sig = sig_mod.build_market_signal(MOCK_MARKET)
    storage.write_signals("kalshi", "test-001", [sig])
    bus = tmp_path / "signals" / "kalshi.json"
    assert bus.exists()
    data = json.loads(bus.read_text())
    assert data["meta"]["total_signals"] == 1
    assert data["signals"][0]["ticker_or_market"] == sig["ticker_or_market"]


# ---------------------------------------------------------------------------
# Signal format compliance
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = [
    "id", "type", "source_url", "source_author", "title", "body",
    "ticker_or_market", "direction", "confidence", "urgency",
    "engagement", "tags", "raw_data", "extracted_at",
]

def test_signal_format_compliance():
    sig = sig_mod.build_market_signal(MOCK_MARKET)
    for field in REQUIRED_FIELDS:
        assert field in sig, f"Missing required field: {field}"
    assert sig["type"] in ("sentiment", "prediction", "alert", "trend", "strategy", "news")
    assert sig["direction"] in ("bullish", "bearish", "neutral", "unknown")
    assert 0 <= sig["confidence"] <= 1.0
    assert sig["urgency"] in ("realtime", "hours", "days", "weeks")
