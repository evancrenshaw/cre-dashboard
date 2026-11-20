# CRE Desk

Evan's always-on second-monitor dashboard: clock, Chattanooga weather, markets, CRE news and the weekly Claude briefs.

**Live page:** https://evancrenshaw.github.io/cre-dashboard/

## How it updates
| Section | Source | How often |
|---|---|---|
| Clock, market status | the page itself | every second |
| Weather | Open-Meteo (no key) | every 15 min |
| Ticker tape, whole-market movers, economic calendar | TradingView widgets | live |
| Watchlist + past-hour / today movers | Finnhub via GitHub Actions (`scripts/fetch_quotes.py`) | ~15 min, market hours |
| News | RSS feeds via GitHub Actions (`scripts/fetch_news.py`) | ~15 min |
| Monday brief, Friday note, weekday check-ins | Claude scheduled tasks → `scripts/post_brief.py` | Mon 6:39 AM, Fri 6:44 AM, weekdays midday + after close |

## Changing things
- Watchlist: edit `watchlist.json`.
- News sources and keywords: `FEEDS` and `RELEVANT` in `scripts/fetch_news.py`.
- Finnhub key: repo **Settings → Secrets and variables → Actions → FINNHUB_API_KEY**.
