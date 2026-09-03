from datetime import timedelta

import pytest
import requests

from src.alerts.calendar_client import (
    CalendarFetchError,
    fetch_calendar_events,
    parse_event,
    parse_events,
)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"http {self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self._status_code = status_code
        self.requested_url = None

    def get(self, url, timeout=None):
        self.requested_url = url
        return _FakeResponse(self._payload, self._status_code)


def _raw_event(**overrides):
    raw = {
        "title": "Non-Farm Employment Change",
        "country": "USD",
        "date": "2026-09-04T12:30:00-04:00",
        "impact": "High",
        "forecast": "55K",
        "previous": "-23K",
        "url": "https://www.forexfactory.com/calendar",
    }
    raw.update(overrides)
    return raw


def test_parse_event_basic_fields():
    event = parse_event(_raw_event())

    assert event.title == "Non-Farm Employment Change"
    assert event.country == "USD"
    assert event.impact == "High"
    assert event.forecast == "55K"
    assert event.previous == "-23K"
    assert event.date.tzinfo is not None
    assert event.date.utcoffset() == timedelta(hours=-4)


def test_parse_event_handles_nested_impact_object():
    event = parse_event(_raw_event(impact={"title": "High"}))
    assert event.impact == "High"


def test_parse_event_handles_z_suffix_date():
    event = parse_event(_raw_event(date="2026-09-04T16:30:00Z"))
    assert event.date.utcoffset() == timedelta(0)


def test_parse_event_returns_none_when_title_missing():
    raw = _raw_event()
    del raw["title"]
    assert parse_event(raw) is None


def test_parse_event_returns_none_when_date_missing():
    raw = _raw_event()
    del raw["date"]
    assert parse_event(raw) is None


def test_parse_event_returns_none_on_unparseable_date():
    assert parse_event(_raw_event(date="not-a-date")) is None


def test_parse_events_skips_invalid_entries():
    raw_events = [_raw_event(), {"title": "missing date"}]
    events = parse_events(raw_events)
    assert len(events) == 1
    assert events[0].title == "Non-Farm Employment Change"


def test_fetch_calendar_events_parses_payload():
    session = _FakeSession([_raw_event(), _raw_event(title="Unemployment Rate")])
    events = fetch_calendar_events(feed_url="https://example.test/calendar.json", session=session)

    assert session.requested_url == "https://example.test/calendar.json"
    assert [e.title for e in events] == ["Non-Farm Employment Change", "Unemployment Rate"]


def test_fetch_calendar_events_raises_on_non_list_payload():
    session = _FakeSession({"not": "a list"})
    with pytest.raises(CalendarFetchError):
        fetch_calendar_events(session=session)


def test_fetch_calendar_events_raises_on_http_error():
    session = _FakeSession([_raw_event()], status_code=500)
    with pytest.raises(CalendarFetchError):
        fetch_calendar_events(session=session)
