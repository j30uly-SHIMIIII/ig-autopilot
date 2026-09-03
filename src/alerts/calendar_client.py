"""Fetches and parses the ForexFactory economic calendar feed.

Uses the public JSON feed ForexFactory's own calendar widget is built on
(https://nfs.faireconomy.media/ff_calendar_thisweek.json) instead of
scraping forexfactory.com's HTML, since that page is JS-rendered while the
feed is the same underlying data, stable, and widely used by other trading
tools.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

import requests

DEFAULT_FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


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
        resp = session.get(feed_url, timeout=timeout)
        resp.raise_for_status()
        raw_events = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise CalendarFetchError(f"failed to fetch calendar feed {feed_url}: {exc}") from exc
    if not isinstance(raw_events, list):
        raise CalendarFetchError(f"unexpected calendar feed payload shape from {feed_url}")
    return parse_events(raw_events)
