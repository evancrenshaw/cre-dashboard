#!/usr/bin/env python3
"""Add a Monday brief, Friday note, or mid-week check-in to data/briefs.json.

Used by Evan's Claude scheduled tasks. Usage:
  python3 scripts/post_brief.py --kind monday|friday|checkin --file entry.json

entry.json fields (all strings unless noted):
  title          e.g. "Market Brief — week of Nov 23"
  summary        2-4 sentence overview
  key_points     list of short strings (3-8)
  talking_point  optional one-liner for clients / LinkedIn
  link           optional URL to the full brief
  label          check-ins only, e.g. "Midday" or "After close"
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "briefs.json"
REQUIRED = ("title", "summary", "key_points")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["monday", "friday", "checkin"])
    ap.add_argument("--file", required=True)
    a = ap.parse_args()

    entry = json.loads(Path(a.file).read_text())
    missing = [k for k in REQUIRED if not entry.get(k)]
    if missing:
        raise SystemExit(f"entry is missing: {', '.join(missing)}")
    if not isinstance(entry["key_points"], list):
        raise SystemExit("key_points must be a list of strings")

    now = datetime.now(timezone.utc)
    entry["posted"] = now.isoformat()
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    data.setdefault("updates", [])
    data.setdefault("archive", [])

    if a.kind == "checkin":
        entry.setdefault("label", "Update")
        data["updates"].insert(0, entry)
    else:
        old = data.get(a.kind)
        if old:
            data["archive"].insert(0, {**old, "kind": a.kind})
            data["archive"] = data["archive"][:16]
        data[a.kind] = entry

    week_ago = now - timedelta(days=7)
    data["updates"] = [u for u in data["updates"] if datetime.fromisoformat(u["posted"]) >= week_ago][:20]
    data["updated"] = now.isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(f"posted {a.kind}: {entry['title']}")


if __name__ == "__main__":
    main()
