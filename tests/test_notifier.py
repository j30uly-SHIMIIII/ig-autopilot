import pytest

from src.alerts.notifier import (
    DiscordNotifier,
    MultiNotifier,
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


class _RecordingNotifier:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def send(self, text):
        if self.fail:
            raise NotifierError("simulated failure")
        self.sent.append(text)


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


def test_discord_notifier_sends_content_payload():
    session = _FakeSession()
    notifier = DiscordNotifier("https://discord.test/webhook", session=session)

    notifier.send("hello")

    assert session.posted == [
        {"url": "https://discord.test/webhook", "json": {"content": "hello"}, "timeout": 10}
    ]


def test_discord_notifier_raises_on_error_status():
    session = _FakeSession(status_code=500)
    notifier = DiscordNotifier("https://discord.test/webhook", session=session)

    with pytest.raises(NotifierError):
        notifier.send("hello")


def test_discord_notifier_requires_webhook_url():
    with pytest.raises(ValueError):
        DiscordNotifier("")


def test_multi_notifier_sends_to_all():
    a, b = _RecordingNotifier(), _RecordingNotifier()
    MultiNotifier([a, b]).send("hello")
    assert a.sent == ["hello"]
    assert b.sent == ["hello"]


def test_multi_notifier_continues_after_one_fails():
    failing, ok = _RecordingNotifier(fail=True), _RecordingNotifier()
    with pytest.raises(NotifierError):
        MultiNotifier([failing, ok]).send("hello")
    assert ok.sent == ["hello"]


def test_multi_notifier_requires_notifiers():
    with pytest.raises(ValueError):
        MultiNotifier([])


def test_null_notifier_records_without_raising():
    notifier = NullNotifier()
    notifier.send("hello")
    assert notifier.sent == ["hello"]


def test_create_notifier_falls_back_to_null_without_any_webhook(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    notifier = create_notifier()
    assert isinstance(notifier, NullNotifier)


def test_create_notifier_uses_env_slack_webhook(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/from-env")
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    notifier = create_notifier()
    assert isinstance(notifier, SlackNotifier)
    assert notifier.webhook_url == "https://hooks.slack.test/from-env"


def test_create_notifier_uses_env_discord_webhook(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/from-env")
    notifier = create_notifier()
    assert isinstance(notifier, DiscordNotifier)
    assert notifier.webhook_url == "https://discord.test/from-env"


def test_create_notifier_fans_out_when_both_configured(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/from-env")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/from-env")
    notifier = create_notifier()
    assert isinstance(notifier, MultiNotifier)
    assert {type(n) for n in notifier.notifiers} == {SlackNotifier, DiscordNotifier}


def test_create_notifier_explicit_args_override_env(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/from-env")
    notifier = create_notifier(slack_webhook_url="https://hooks.slack.test/explicit")
    assert notifier.webhook_url == "https://hooks.slack.test/explicit"
