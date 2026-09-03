import pytest

from src.alerts.notifier import (
    NotifierError,
    NullNotifier,
    SlackNotifier,
    create_notifier,
)


class _FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class _FakeSession:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.posted = []

    def post(self, url, json=None, timeout=None):
        self.posted.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse(self.status_code)


def test_slack_notifier_sends_text_payload():
    session = _FakeSession()
    notifier = SlackNotifier("https://hooks.slack.test/xyz", session=session)

    notifier.send("hello")

    assert session.posted == [
        {"url": "https://hooks.slack.test/xyz", "json": {"text": "hello"}, "timeout": 10}
    ]


def test_slack_notifier_raises_on_error_status():
    session = _FakeSession(status_code=500)
    notifier = SlackNotifier("https://hooks.slack.test/xyz", session=session)

    with pytest.raises(NotifierError):
        notifier.send("hello")


def test_slack_notifier_requires_webhook_url():
    with pytest.raises(ValueError):
        SlackNotifier("")


def test_null_notifier_records_without_raising():
    notifier = NullNotifier()
    notifier.send("hello")
    assert notifier.sent == ["hello"]


def test_create_notifier_falls_back_to_null_without_webhook(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    notifier = create_notifier()
    assert isinstance(notifier, NullNotifier)


def test_create_notifier_uses_env_webhook(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/from-env")
    notifier = create_notifier()
    assert isinstance(notifier, SlackNotifier)
    assert notifier.webhook_url == "https://hooks.slack.test/from-env"


def test_create_notifier_explicit_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/from-env")
    notifier = create_notifier(webhook_url="https://hooks.slack.test/explicit")
    assert notifier.webhook_url == "https://hooks.slack.test/explicit"
