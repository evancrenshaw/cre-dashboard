#!/usr/bin/env python3
"""Snapshot watchlist quotes from Finnhub and compute day and past-hour movers.

Runs from GitHub Actions every ~15 minutes during US market hours. Needs the
repo secret FINNHUB_API_KEY. Writes data/movers.json and keeps a rolling price
history in data/quote_history.json so the 1-hour change can be computed.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = json.loads((ROOT / "watchlist.json").read_text())
OUT = ROOT / "data" / "movers.json"
HIST = ROOT / "data" / "quote_history.json"
NY = ZoneInfo("America/New_York")
KEEP_HOURS = 8


HOLIDAYS = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26",
            "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"}


def market_open(now_ny):
    if now_ny.weekday() >= 5 or now_ny.strftime("%Y-%m-%d") in HOLIDAYS:
        return False
    minutes = now_ny.hour * 60 + now_ny.minute
    return 9 * 60 + 25 <= minutes <= 16 * 60 + 10


def quote(symbol, key):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={key}"
    req = urllib.request.Request(url, headers={"User-Agent": "cre-dashboard"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def price_hour_ago(points, now_ts):
    """Price from the snapshot closest to 60 min ago (accepts 40-90 min)."""
    best = None
    for ts, px in points:
        age = (now_ts - ts) / 60
        if 40 <= age <= 90 and (best is None or abs(age - 60) < abs(best[0] - 60)):
            best = (age, px)
    return best[1] if best else None


def main():
    key = os.environ.get("FINNHUB_API_KEY", "").strip()
    now = datetime.now(timezone.utc)
    now_ny = now.astimezone(NY)
    force = "--force" in sys.argv
    if not key:
        print("FINNHUB_API_KEY not set; skipping quotes.", file=sys.stderr)
        return
    if not market_open(now_ny) and not force:
        print("Market closed; skipping quotes.")
        return

    hist = json.loads(HIST.read_text()) if HIST.exists() else {}
    now_ts = int(now.timestamp())
    cutoff = now_ts - KEEP_HOURS * 3600
    groups, flat = [], []

    for group in WATCHLIST["groups"]:
        rows = []
        for sym, name in group["symbols"]:
            try:
                q = quote(sym, key)
            except Exception as e:
                print(f"skip {sym}: {e}", file=sys.stderr)
                continue
            time.sleep(1.1)  # free tier: 60 calls/min
            price = q.get("c") or 0
            if not price:
                continue
            pts = [p for p in hist.get(sym, []) if p[0] >= cutoff]
            pts.append([now_ts, price])
            hist[sym] = pts
            ago = price_hour_ago(pts, now_ts)
            h1 = round((price / ago - 1) * 100, 2) if ago else None
            row = {"s": sym, "name": name, "price": round(price, 2), "dp": round(q.get("dp") or 0, 2), "h1": h1}
            rows.append(row)
            flat.append(row)
        groups.append({"name": group["name"], "rows": rows})

    if not flat:
        print("No quotes fetched; leaving existing movers.json.", file=sys.stderr)
        return

    with_h1 = [r for r in flat if r["h1"] is not None]
    out = {
        "updated": now.isoformat(),
        "groups": groups,
        "day_up": sorted(flat, key=lambda r: r["dp"], reverse=True)[:5],
        "day_down": sorted(flat, key=lambda r: r["dp"])[:5],
        "hour_up": sorted(with_h1, key=lambda r: r["h1"], reverse=True)[:5],
        "hour_down": sorted(with_h1, key=lambda r: r["h1"])[:5],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    HIST.write_text(json.dumps(hist))
    print(f"quotes: {len(flat)} symbols, {len(with_h1)} with 1h change")


if __name__ == "__main__":
    main()
