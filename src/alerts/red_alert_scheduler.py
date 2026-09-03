"""Polls the ForexFactory economic calendar and sends a Slack alert N minutes
before each high-impact ("red") event, so trading/posting decisions aren't
made blind into releases like NFP.

Intended to run frequently from cron (poll_interval_minutes in
config/forexfactory.yaml, e.g. every 1 minute) since the alert window is
only alert_minutes_before wide. Already-alerted events are recorded in the
calendar_alerts table so repeated polls before the event fires don't send
duplicate messages for the same event.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import yaml

from src.alerts.calendar_client import CalendarEvent, DEFAULT_FEED_URL, fetch_calendar_events
from src.alerts.notifier import Notifier, create_notifier
from src.common.db import DEFAULT_DB_PATH, connect

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "forexfactory.yaml"

logger = logging.getLogger(__name__)


def load_config(config_path: Path | str = DEFAULT_CONFIG_PATH) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _event_key(event: CalendarEvent) -> str:
    return f"{event.country}|{event.title}|{event.date.isoformat()}"


def _already_alerted(conn, event_key: str) -> bool:
    row = conn.execute("SELECT 1 FROM calendar_alerts WHERE event_key = ?", (event_key,)).fetchone()
    return row is not None


def _mark_alerted(conn, event_key: str, event: CalendarEvent) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO calendar_alerts (event_key, title, country, event_at) VALUES (?, ?, ?, ?)",
        (event_key, event.title, event.country, event.date.isoformat()),
    )


def _format_message(event: CalendarEvent, minutes_before: int, timezone: str) -> str:
    local_time = event.date.astimezone(ZoneInfo(timezone)).strftime("%H:%M")
    lines = [
        f":rotating_light: *{minutes_before}分後* [{event.country}] {event.title}",
        f"時刻: {local_time} ({timezone})",
    ]
    if event.forecast:
        lines.append(f"予想: {event.forecast}")
    if event.previous:
        lines.append(f"前回: {event.previous}")
    if event.url:
        lines.append(event.url)
    return "\n".join(lines)


def due_events(
    events: list[CalendarEvent],
    now: datetime,
    minutes_before: int,
    impact_levels: set[str],
) -> list[CalendarEvent]:
    """Events whose start time falls within [now, now + minutes_before]."""
    window_end = now + timedelta(minutes=minutes_before)
    return [
        event
        for event in events
        if event.impact.lower() in impact_levels and now <= event.date <= window_end
    ]


def run_once(
    db_path: Path | str = DEFAULT_DB_PATH,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    notifier: Optional[Notifier] = None,
    events: Optional[list[CalendarEvent]] = None,
) -> dict:
    config = load_config(config_path)
    timezone = config.get("timezone", "Asia/Tokyo")
    minutes_before = config.get("alert_minutes_before", 5)
    impact_levels = {str(level).lower() for level in config.get("impact_levels") or ["high"]}
    currencies = config.get("currencies")
    feed_url = config.get("feed_url", DEFAULT_FEED_URL)

    notifier = notifier or create_notifier()
    now = datetime.now(ZoneInfo(timezone))

    if events is None:
        events = fetch_calendar_events(feed_url)

    if currencies:
        allowed = {c.upper() for c in currencies}
        events = [event for event in events if event.country.upper() in allowed]

    summary = {"checked": len(events), "alerted": 0, "skipped_duplicate": 0}

    with connect(db_path) as conn:
        for event in due_events(events, now, minutes_before, impact_levels):
            key = _event_key(event)
            if _already_alerted(conn, key):
                summary["skipped_duplicate"] += 1
                continue
            message = _format_message(event, minutes_before, timezone)
            notifier.send(message)
            _mark_alerted(conn, key, event)
            summary["alerted"] += 1
            logger.info("alerted for %s (%s)", event.title, event.country)

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_once()
    logger.info("forexfactory red-alert run complete: %s", result)
