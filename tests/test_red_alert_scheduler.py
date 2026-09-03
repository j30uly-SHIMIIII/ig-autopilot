from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

from src.alerts.calendar_client import CalendarEvent
from src.alerts.notifier import NullNotifier
from src.alerts.red_alert_scheduler import due_events, run_once
from src.common.db import get_connection

TZ = "UTC"


def _write_config(tmp_path, **overrides):
    config = {
        "timezone": TZ,
        "feed_url": "https://example.test/calendar.json",
        "alert_minutes_before": 5,
        "impact_levels": ["high"],
        "currencies": [],
        "poll_interval_minutes": 1,
    }
    config.update(overrides)
    path = tmp_path / "forexfactory.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def _event(title="Non-Farm Employment Change", country="USD", impact="High", minutes_from_now=3, **overrides):
    date = datetime.now(ZoneInfo(TZ)) + timedelta(minutes=minutes_from_now)
    fields = dict(title=title, country=country, impact=impact, date=date, forecast="55K", previous="-23K", url="")
    fields.update(overrides)
    return CalendarEvent(**fields)


def test_due_events_filters_by_impact_and_window():
    now = datetime.now(ZoneInfo(TZ))
    events = [
        _event(title="High soon", impact="High", minutes_from_now=3),
        _event(title="High too far", impact="High", minutes_from_now=30),
        _event(title="Medium soon", impact="Medium", minutes_from_now=3),
        _event(title="High already passed", impact="High", minutes_from_now=-1),
    ]

    result = due_events(events, now, minutes_before=5, impact_levels={"high"})

    assert [e.title for e in result] == ["High soon"]


def test_run_once_sends_alert_for_due_high_impact_event(tmp_path):
    db_path = tmp_path / "queue.db"
    config_path = _write_config(tmp_path)
    notifier = NullNotifier()
    events = [_event(minutes_from_now=3)]

    summary = run_once(db_path=db_path, config_path=config_path, notifier=notifier, events=events)

    assert summary == {"checked": 1, "alerted": 1, "skipped_duplicate": 0}
    assert len(notifier.sent) == 1
    assert "Non-Farm Employment Change" in notifier.sent[0]

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM calendar_alerts").fetchone()
    conn.close()
    assert row["title"] == "Non-Farm Employment Change"
    assert row["country"] == "USD"


def test_run_once_does_not_duplicate_alert_on_second_poll(tmp_path):
    db_path = tmp_path / "queue.db"
    config_path = _write_config(tmp_path)
    event = _event(minutes_from_now=3)

    first = run_once(db_path=db_path, config_path=config_path, notifier=NullNotifier(), events=[event])
    second_notifier = NullNotifier()
    second = run_once(db_path=db_path, config_path=config_path, notifier=second_notifier, events=[event])

    assert first["alerted"] == 1
    assert second == {"checked": 1, "alerted": 0, "skipped_duplicate": 1}
    assert second_notifier.sent == []


def test_run_once_skips_non_high_impact_events(tmp_path):
    db_path = tmp_path / "queue.db"
    config_path = _write_config(tmp_path)
    events = [_event(impact="Medium", minutes_from_now=3), _event(impact="Low", minutes_from_now=3)]

    summary = run_once(db_path=db_path, config_path=config_path, notifier=NullNotifier(), events=events)

    assert summary == {"checked": 2, "alerted": 0, "skipped_duplicate": 0}


def test_run_once_respects_currency_filter(tmp_path):
    db_path = tmp_path / "queue.db"
    config_path = _write_config(tmp_path, currencies=["JPY"])
    events = [_event(country="USD", minutes_from_now=3), _event(country="JPY", minutes_from_now=3, title="Household Spending y/y")]

    notifier = NullNotifier()
    summary = run_once(db_path=db_path, config_path=config_path, notifier=notifier, events=events)

    assert summary == {"checked": 1, "alerted": 1, "skipped_duplicate": 0}
    assert "Household Spending" in notifier.sent[0]


def test_run_once_ignores_event_outside_alert_window(tmp_path):
    db_path = tmp_path / "queue.db"
    config_path = _write_config(tmp_path)
    events = [_event(minutes_from_now=30)]

    summary = run_once(db_path=db_path, config_path=config_path, notifier=NullNotifier(), events=events)

    assert summary == {"checked": 1, "alerted": 0, "skipped_duplicate": 0}
