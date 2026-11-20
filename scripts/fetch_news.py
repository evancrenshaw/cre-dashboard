#!/usr/bin/env python3
"""Pull CRE / business / finance headlines from RSS feeds into data/news.json.

Runs from GitHub Actions. Standard library only. A feed that fails is skipped,
so one broken source never empties the dashboard.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "news.json"
MAX_ITEMS = 80
MAX_AGE_HOURS = 72


def gnews(query):
    q = urllib.parse.quote_plus(query + " when:2d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


# (feed url, default tag). Tags: CRE, Local, Finance, Business
FEEDS = [
    (gnews('"commercial real estate"'), "CRE"),
    (gnews("retail real estate leasing OR retail vacancy OR store openings"), "CRE"),
    (gnews('"office market" OR "office vacancy" OR "office leasing"'), "CRE"),
    (gnews("CMBS OR \"CRE lending\" OR \"commercial mortgage\""), "CRE"),
    (gnews("site:globest.com"), "CRE"),
    (gnews("site:bisnow.com"), "CRE"),
    (gnews("site:commercialobserver.com"), "CRE"),
    (gnews("Chattanooga development OR Chattanooga business OR Chattanooga real estate"), "Local"),
    (gnews("site:chattanoogan.com business OR development"), "Local"),
    (gnews("site:timesfreepress.com business"), "Local"),
    (gnews("Hixson OR \"Highway 153\" Chattanooga"), "Local"),
    (gnews("Tennessee commercial real estate OR Tennessee development"), "Local"),
    (gnews("Federal Reserve interest rates OR Treasury yields"), "Finance"),
    (gnews("stock market today"), "Finance"),
    (gnews("retail sales OR consumer spending OR jobs report OR inflation report"), "Business"),
    ("https://www.cnbc.com/id/10000115/device/rss/rss.html", "CRE"),      # CNBC real estate
    ("https://www.cnbc.com/id/10001147/device/rss/rss.html", "Business"), # CNBC business
    ("https://www.cnbc.com/id/20910258/device/rss/rss.html", "Finance"),  # CNBC economy
]

# Headlines must hit at least one of these to be kept (keeps the feed job-relevant).
RELEVANT = re.compile(
    r"real estate|\bCRE\b|lease|leasing|tenant|landlord|retail|store|mall|shopping center|"
    r"office|vacanc|sublease|industrial|warehouse|multifamily|apartment|developer|development|"
    r"rezon|zoning|property|properties|REIT|cap rate|CMBS|mortgage|lending|lender|loan|bank|"
    r"Fed\b|Federal Reserve|rate cut|rate hike|interest rate|Treasury|yield|inflation|CPI|jobs|"
    r"payroll|unemployment|GDP|consumer|spending|retail sales|earnings|stocks?|market|Dow|S&P|Nasdaq|"
    r"bankrupt|closing|closure|opening|acquir|acquisition|merger|sells?|sold|buys?|deal|"
    r"Chattanooga|Hixson|Hamilton County|Tennessee|Food City",
    re.I,
)
LOCAL = re.compile(r"Chattanooga|Hixson|Hamilton County|Red Bank|Ooltewah|East Ridge|Signal Mountain|Tennessee|\bTN\b|Food City", re.I)
CRE = re.compile(r"real estate|\bCRE\b|leas|tenant|landlord|office|vacanc|sublease|REIT|cap rate|CMBS|shopping center|mall|multifamily|industrial|property|properties|square feet|sq\. ft", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (cre-dashboard news fetcher)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def text(el, tag):
    found = el.find(tag)
    return (found.text or "").strip() if found is not None and found.text else ""


def parse(xml_bytes, default_tag):
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter("item"):
        title = text(it, "title")
        link = text(it, "link")
        if not title or not link:
            continue
        source = text(it, "source")
        # Google News titles end in " - Source"; split it off.
        m = re.match(r"^(.*)\s+-\s+([^-]{2,60})$", title)
        if m and (not source or source == m.group(2).strip()):
            title, source = m.group(1).strip(), m.group(2).strip()
        if not source:
            source = urllib.parse.urlparse(link).netloc.replace("www.", "")
        pub = text(it, "pubDate")
        try:
            ts = parsedate_to_datetime(pub).astimezone(timezone.utc)
        except Exception:
            ts = datetime.now(timezone.utc)
        items.append({"title": title, "link": link, "source": source, "published": ts.isoformat(), "tag": default_tag})
    return items


def tag_for(item):
    t = item["title"]
    if LOCAL.search(t):
        return "Local"
    if CRE.search(t):
        return "CRE"
    return item["tag"]


def norm(title):
    return re.sub(r"[^a-z0-9 ]", "", title.lower())[:70]


def main():
    now = datetime.now(timezone.utc)
    collected, ok = [], 0
    for url, tag in FEEDS:
        try:
            collected += parse(fetch(url), tag)
            ok += 1
        except Exception as e:  # keep going on any single-feed failure
            print(f"skip feed ({e.__class__.__name__}): {url[:90]}", file=sys.stderr)

    seen, kept = set(), []
    for it in sorted(collected, key=lambda x: x["published"], reverse=True):
        age_h = (now - datetime.fromisoformat(it["published"])).total_seconds() / 3600
        if age_h > MAX_AGE_HOURS or age_h < -2:
            continue
        if it["tag"] in ("Finance", "Business") and not RELEVANT.search(it["title"]):
            continue
        key = norm(it["title"])
        if key in seen:
            continue
        seen.add(key)
        it["tag"] = tag_for(it)
        kept.append(it)
        if len(kept) >= MAX_ITEMS:
            break

    if ok == 0 or not kept:
        print("No feeds succeeded; leaving existing news.json in place.", file=sys.stderr)
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated": now.isoformat(), "items": kept}, indent=1))
    print(f"news: {len(kept)} items from {ok}/{len(FEEDS)} feeds")


if __name__ == "__main__":
    main()
