"""Signal extraction and normalization for Kalshi prediction markets."""
from __future__ import annotations
import hashlib, logging
from datetime import datetime
from config import CATEGORIES, PRICE_MOVE_THRESHOLD, VOLUME_ANOMALY_MULTIPLIER

log = logging.getLogger("kalshi.signals")

def _signal_id(ticker: str, stype: str) -> str:
    day = datetime.utcnow().strftime("%Y%m%d")
    return hashlib.sha256(f"{ticker}:{stype}:{day}".encode()).hexdigest()[:16]

def _classify_category(title: str, ticker: str) -> list[str]:
    combined = f"{title} {ticker}".upper()
    tags = [c for c, kws in CATEGORIES.items() if any(k in combined for k in kws)]
    return tags or ["other"]

def _infer_direction(price: float, prev: float | None) -> str:
    if prev is None:
        return "bullish" if price >= 0.7 else ("bearish" if price <= 0.3 else "neutral")
    d = price - prev
    return "bullish" if d > PRICE_MOVE_THRESHOLD else ("bearish" if d < -PRICE_MOVE_THRESHOLD else "neutral")

def _confidence(vol: int, oi: int) -> float:
    s = 0.3
    if vol > 1000: s += 0.2
    if vol > 10000: s += 0.2
    if oi > 5000: s += 0.15
    if oi > 50000: s += 0.15
    return min(s, 1.0)

def _urgency(market: dict) -> str:
    close = market.get("close_time") or market.get("expected_expiration_time", "")
    if not close: return "days"
    try:
        dt = datetime.fromisoformat(close.replace("Z", "+00:00"))
        d = (dt - datetime.now(dt.tzinfo)).total_seconds()
        return "realtime" if d < 3600 else "hours" if d < 86400 else "days" if d < 604800 else "weeks"
    except (ValueError, TypeError): return "days"

def _norm(p): return p / 100 if p > 1 else p

def build_market_signal(market: dict, prev_snap: dict | None = None) -> dict:
    ticker = market.get("ticker", "")
    title = market.get("title", market.get("subtitle", ""))
    yes_p = market.get("yes_bid", 0) or market.get("last_price", 0)
    vol = market.get("volume", 0) or 0
    oi = market.get("open_interest", 0) or 0
    prev_p = prev_snap[ticker].get("yes_price") if prev_snap and ticker in prev_snap else None
    direction = _infer_direction(_norm(yes_p), _norm(prev_p) if prev_p else None)
    pct = _norm(yes_p)
    body = f"{ticker}: Yes={pct:.0%}, Vol={vol:,}, OI={oi:,}. Direction: {direction}."[:500]
    return {
        "id": _signal_id(ticker, "market"), "type": "prediction",
        "source_url": f"https://kalshi.com/markets/{ticker}",
        "source_author": "kalshi-market", "title": f"[Kalshi] {title}"[:200],
        "body": body, "ticker_or_market": f"KALSHI:{ticker}",
        "direction": direction, "confidence": _confidence(vol, oi),
        "urgency": _urgency(market),
        "engagement": {"volume": vol, "open_interest": oi},
        "tags": _classify_category(title, ticker),
        "raw_data": {"ticker": ticker, "yes_price": yes_p,
                     "no_price": market.get("no_bid", 0), "volume": vol,
                     "open_interest": oi, "status": market.get("status", ""),
                     "close_time": market.get("close_time", "")},
        "extracted_at": datetime.utcnow().isoformat(),
    }

def detect_price_movers(markets: list[dict], prev: dict) -> list[dict]:
    movers = []
    for m in markets:
        t = m.get("ticker", "")
        if t not in prev: continue
        cur = _norm(m.get("yes_bid", 0) or m.get("last_price", 0))
        prv = _norm(prev[t].get("yes_price", 0))
        delta = abs(cur - prv)
        if delta >= PRICE_MOVE_THRESHOLD:
            s = build_market_signal(m, prev)
            s["id"] = _signal_id(t, "mover")
            s["type"] = "alert"
            s["title"] = f"[Kalshi MOVER] {m.get('title',t)} ({delta:+.0%})"[:200]
            movers.append(s)
    return movers

def detect_volume_anomalies(markets: list[dict], prev: dict) -> list[dict]:
    out = []
    for m in markets:
        t = m.get("ticker", "")
        if t not in prev: continue
        cv = m.get("volume", 0) or 0
        pv = prev[t].get("volume", 0) or 1
        if pv > 0 and cv > pv * VOLUME_ANOMALY_MULTIPLIER:
            s = build_market_signal(m, prev)
            s["id"] = _signal_id(t, "vol-anomaly")
            s["type"] = "alert"
            s["title"] = f"[Kalshi VOL] {m.get('title',t)} vol {pv:,}->{cv:,}"[:200]
            out.append(s)
    return out
