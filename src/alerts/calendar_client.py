"""Fetches and parses the ForexFactory economic calendar feed.

Uses the public JSON feed ForexFactory's own calendar widget is built on
(https://nfs.faireconomy.media/ff_calendar_thisweek.json) instead of
scraping forexfactory.com's HTML, since that page is JS-rendered while the
feed is the same underlying data, stable, and widely used by other trading
tools.

fetch_calendar_events_cached() wraps fetch_calendar_events() with a
file-based cache: red_alert_scheduler runs as a fresh process every poll
(cron / Windows Task Scheduler), so without caching it re-downloads the
whole feed every single poll, which is what tripped the feed's rate limit
(HTTP 429) polling every 1 minute. A stale cache is also used as a
fallback when a fetch fails, so a transient rate limit / outage doesn't
stop alerts for events already known from an earlier successful fetch.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

import requests

DEFAULT_FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ig-autopilot-forexfactory-alert/1.0)"
}

logger = logging.getLogger(__name__)


class CalendarFetchError(RuntimeError):
    """Raised when the calendar feed can't be fetched or parsed."""


@dataclass(frozen=True)
class CalendarEvent:
    title: str
    country: str
    impact: str
    date: datetime
    forecast: str = ""
    previous: str = ""
    url: str = ""


def _extract_impact(raw: dict) -> str:
    impact = raw.get("impact")
    if isinstance(impact, dict):
        impact = impact.get("title") or impact.get("name")
    return str(impact or "").strip()


def _parse_date(raw_date: str) -> datetime:
    value = raw_date.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise CalendarFetchError(f"calendar event date has no timezone offset: {raw_date!r}")
    return dt


def parse_event(raw: dict) -> Optional[CalendarEvent]:
    title = str(raw.get("title") or "").strip()
    country = str(raw.get("country") or "").strip()
    raw_date = raw.get("date")
    if not title or not raw_date:
        return None
    try:
        date = _parse_date(str(raw_date))
    except (ValueError, CalendarFetchError):
        return None
    return CalendarEvent(
        title=title,
        country=country,
        impact=_extract_impact(raw),
        date=date,
        forecast=str(raw.get("forecast") or "").strip(),
        previous=str(raw.get("previous") or "").strip(),
        url=str(raw.get("url") or "").strip(),
    )


def parse_events(raw_events: Sequence[dict]) -> list[CalendarEvent]:
    events = [parse_event(raw) for raw in raw_events]
    return [event for event in events if event is not None]


def fetch_calendar_events(
    feed_url: str = DEFAULT_FEED_URL,
    session: Optional[requests.Session] = None,
    timeout: int = 15,
) -> list[CalendarEvent]:
    session = session or requests.Session()
    try:
        resp = session.get(feed_url, timeout=timeout, headers=DEFAULT_HEADERS)
        resp.raise_for_status()
        raw_events = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise CalendarFetchError(f"failed to fetch calendar feed {feed_url}: {exc}") from exc
    if not isinstance(raw_events, list):
        raise CalendarFetchError(f"unexpected calendar feed payload shape from {feed_url}")
    return parse_events(raw_events)


def _read_cache(cache_path: Path) -> list[CalendarEvent]:
    raw_events = json.loads(cache_path.read_text(encoding="utf-8"))
    return parse_events(raw_events)


def _write_cache(cache_path: Path, raw_events: list) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(raw_events), encoding="utf-8")


def fetch_calendar_events_cached(
    feed_url: str = DEFAULT_FEED_URL,
    cache_path: Optional[Path] = None,
    cache_ttl_seconds: int = 300,
    session: Optional[requests.Session] = None,
    timeout: int = 15,
) -> list[CalendarEvent]:
    """Like fetch_calendar_events(), but reuses a file cache within
    cache_ttl_seconds instead of re-fetching, and falls back to a stale
    cache (if any) when a fresh fetch fails."""
    if cache_path is None:
        return fetch_calendar_events(feed_url, session=session, timeout=timeout)

    cache_path = Path(cache_path)
    if cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < cache_ttl_seconds:
            try:
                return _read_cache(cache_path)
            except (ValueError, OSError):
                logger.warning("calendar cache at %s is unreadable; re-fetching", cache_path)

    session = session or requests.Session()
    try:
        resp = session.get(feed_url, timeout=timeout, headers=DEFAULT_HEADERS)
        resp.raise_for_status()
        raw_events = resp.json()
    except (requests.RequestException, ValueError) as exc:
        if cache_path.exists():
            logger.warning("calendar feed fetch failed (%s); falling back to stale cache", exc)
            return _read_cache(cache_path)
        raise CalendarFetchError(f"failed to fetch calendar feed {feed_url}: {exc}") from exc

    if not isinstance(raw_events, list):
        raise CalendarFetchError(f"unexpected calendar feed payload shape from {feed_url}")

    _write_cache(cache_path, raw_events)
    return parse_events(raw_events)
