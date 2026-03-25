#!/usr/bin/env python3
"""
openclaw-kalshi-feed — Kalshi prediction-market crawler.
Polls Kalshi REST API for active markets, extracts signals, writes to signal bus.

Usage:
    python crawler.py                    # poll all markets
    python crawler.py --category fed     # only Fed-related
    python crawler.py --movers           # biggest moves today
    python crawler.py --demo             # use demo sandbox
    python crawler.py --once             # single pass, no loop
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time, uuid
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

import config, signals as sig_mod, storage

config.LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler(config.LOG_DIR / f"kalshi_{datetime.now():%Y%m%d}.log")])
log = logging.getLogger("kalshi.crawler")

# -- Auth ------------------------------------------------------------------

def _load_rsa_key(path: str) -> str | None:
    p = Path(path).expanduser()
    return p.read_text() if p.exists() else None

def _build_rsa_headers(key_id: str, pem: str) -> dict:
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        import base64
        ts = str(int(time.time() * 1000))
        msg = f"{ts}GET/trade-api/v2/portfolio/balance".encode()
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        sig = key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
        return {"KALSHI-ACCESS-KEY": key_id,
                "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
                "KALSHI-ACCESS-TIMESTAMP": ts}
    except Exception as e:
        log.error("RSA auth failed: %s", e); return {}

def _login_email(client: httpx.Client, base: str) -> str | None:
    if not config.KALSHI_EMAIL or not config.KALSHI_PASSWORD:
        return None
    try:
        r = client.post(f"{base}/login",
                        json={"email": config.KALSHI_EMAIL, "password": config.KALSHI_PASSWORD})
        r.raise_for_status()
        tok = r.json().get("token")
        if tok: log.info("Logged in via email/password.")
        return tok
    except Exception as e:
        log.error("Email login error: %s", e); return None

def build_auth_headers(client: httpx.Client, base: str) -> dict:
    if config.KALSHI_API_KEY_ID and config.KALSHI_PRIVATE_KEY_PATH:
        pem = _load_rsa_key(config.KALSHI_PRIVATE_KEY_PATH)
        if pem:
            h = _build_rsa_headers(config.KALSHI_API_KEY_ID, pem)
            if h: log.info("Using RSA key auth."); return h
    tok = _login_email(client, base)
    if tok: return {"Authorization": f"Bearer {tok}"}
    return {}

# -- API -------------------------------------------------------------------

def _req(client, method, url, **kw):
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            time.sleep(config.RATE_LIMIT_DELAY)
            r = getattr(client, method)(url, **kw)
            if r.status_code in (429, 500, 502, 503):
                w = min(config.BACKOFF_BASE ** (attempt + 1), config.BACKOFF_MAX)
                log.warning("HTTP %d, backoff %.1fs", r.status_code, w); time.sleep(w); continue
            r.raise_for_status(); return r
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                log.error("Auth error %d.", e.response.status_code); return None
            log.warning("HTTP error attempt %d: %s", attempt + 1, e)
        except (httpx.TimeoutException, httpx.RequestError) as e:
            log.warning("Network error attempt %d: %s", attempt + 1, e)
        if attempt < config.MAX_RETRIES:
            time.sleep(config.BACKOFF_BASE ** (attempt + 1))
    log.error("Retries exhausted for %s", url); return None

def fetch_markets(client, base, headers, category=None):
    markets, cursor, page = [], None, 0
    max_pages = config.MAX_PAGES
    while page < max_pages:
        params = {"limit": config.PAGE_SIZE, "status": "open"}
        if cursor: params["cursor"] = cursor
        r = _req(client, "get", f"{base}/markets", params=params, headers=headers)
        if not r: break
        data = r.json(); batch = data.get("markets", [])
        if not batch: break
        markets.extend(batch)
        cursor = data.get("cursor")
        page += 1
        if not cursor: break
        log.info("Fetched %d markets so far... (page %d/%d)", len(markets), page, max_pages)
    if category:
        kws = config.CATEGORIES.get(category, [])
        if kws:
            markets = [m for m in markets
                       if any(k in f"{m.get('title','')} {m.get('ticker','')}".upper() for k in kws)]
        log.info("Filtered to %d markets (%s)", len(markets), category)
    else:
        log.info("Fetched %d total markets.", len(markets))
    return markets

# -- Snapshot --------------------------------------------------------------
_prev: dict = {}

def _snap(markets):
    return {m.get("ticker",""): {"yes_price": m.get("yes_bid",0) or m.get("last_price",0),
            "volume": m.get("volume",0) or 0, "open_interest": m.get("open_interest",0) or 0}
            for m in markets}

# -- Crawl -----------------------------------------------------------------

def run_crawl(client, base, headers, category, movers_only):
    global _prev
    cid = f"kalshi-{uuid.uuid4().hex[:8]}"
    log.info("=== Crawl %s ===", cid)
    markets = fetch_markets(client, base, headers, category)
    if not markets:
        log.warning("No markets. Skipping."); return 0
    sigs = []
    if movers_only and _prev:
        sigs.extend(sig_mod.detect_price_movers(markets, _prev))
        sigs.extend(sig_mod.detect_volume_anomalies(markets, _prev))
    else:
        sigs = [sig_mod.build_market_signal(m, _prev or None) for m in markets]
        if _prev:
            sigs.extend(sig_mod.detect_price_movers(markets, _prev))
            sigs.extend(sig_mod.detect_volume_anomalies(markets, _prev))
    _prev = _snap(markets)
    if sigs:
        storage.write_signals(config.PLATFORM, cid, sigs)
        log.info("Wrote %d signals.", len(sigs))
    storage.cleanup()
    return len(sigs)

# -- CLI -------------------------------------------------------------------

def main():
    load_dotenv()
    for attr in ("KALSHI_API_KEY_ID","KALSHI_PRIVATE_KEY_PATH","KALSHI_EMAIL","KALSHI_PASSWORD"):
        setattr(config, attr, os.getenv(attr, ""))
    p = argparse.ArgumentParser(description="OpenClaw Kalshi crawler")
    p.add_argument("--category", choices=config.ALL_CATEGORIES)
    p.add_argument("--movers", action="store_true", help="Only report biggest movers")
    p.add_argument("--demo", action="store_true", help="Use demo sandbox API")
    p.add_argument("--once", action="store_true", help="Single pass then exit")
    p.add_argument("--interval", type=int, default=config.POLL_INTERVAL_SECONDS)
    args = p.parse_args()
    use_demo = args.demo or os.getenv("KALSHI_ENV","") == "demo"
    base = config.DEMO_BASE if use_demo else config.PROD_BASE
    log.info("Starting — env=%s base=%s", "demo" if use_demo else "prod", base)
    storage.init()
    client = httpx.Client(timeout=30.0)
    headers = build_auth_headers(client, base)
    if not headers:
        log.warning("No credentials. Set KALSHI_API_KEY_ID+KALSHI_PRIVATE_KEY_PATH "
                     "or KALSHI_EMAIL+KALSHI_PASSWORD in .env. Trying unauthenticated...")
    try:
        if args.once:
            n = run_crawl(client, base, headers, args.category, args.movers)
            log.info("Single pass done. %d signals.", n); return
        log.info("Poll loop (interval=%ds). Ctrl+C to stop.", args.interval)
        while True:
            try: run_crawl(client, base, headers, args.category, args.movers)
            except Exception as e: log.error("Crawl error: %s", e, exc_info=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        client.close()

if __name__ == "__main__":
    main()
