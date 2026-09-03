"""Notification backends for out-of-band alerts (e.g. ForexFactory red-alert).

create_notifier() mirrors src/publisher/ig_client.py's create_ig_client():
it falls back to a no-op notifier when no webhook is configured, so the
rest of the pipeline can run and be tested without real credentials. When
both SLACK_WEBHOOK_URL and DISCORD_WEBHOOK_URL are set, it fans out to
both via MultiNotifier.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Protocol, Sequence

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class NotifierError(RuntimeError):
    """Raised when a notification could not be delivered."""


class Notifier(Protocol):
    def send(self, text: str) -> None: ...


class SlackNotifier:
    """Posts messages to a Slack Incoming Webhook."""

    def __init__(self, webhook_url: str, session: Optional[requests.Session] = None, timeout: int = 10):
        if not webhook_url:
            raise ValueError("webhook_url is required for SlackNotifier")
        self.webhook_url = webhook_url
        self.session = session or requests.Session()
        self.timeout = timeout

    def send(self, text: str) -> None:
        resp = self.session.post(self.webhook_url, json={"text": text}, timeout=self.timeout)
        if resp.status_code >= 400:
            raise NotifierError(f"Slack webhook returned {resp.status_code}: {resp.text[:200]}")


class DiscordNotifier:
    """Posts messages to a Discord Webhook."""

    def __init__(self, webhook_url: str, session: Optional[requests.Session] = None, timeout: int = 10):
        if not webhook_url:
            raise ValueError("webhook_url is required for DiscordNotifier")
        self.webhook_url = webhook_url
        self.session = session or requests.Session()
        self.timeout = timeout

    def send(self, text: str) -> None:
        resp = self.session.post(self.webhook_url, json={"content": text}, timeout=self.timeout)
        if resp.status_code >= 400:
            raise NotifierError(f"Discord webhook returned {resp.status_code}: {resp.text[:200]}")


class MultiNotifier:
    """Fans a single message out to several notifiers.

    One backend failing doesn't stop delivery to the others; all failures
    are collected and raised together so callers still see them.
    """

    def __init__(self, notifiers: Sequence[Notifier]):
        if not notifiers:
            raise ValueError("notifiers must not be empty")
        self.notifiers = list(notifiers)

    def send(self, text: str) -> None:
        errors = []
        for notifier in self.notifiers:
            try:
                notifier.send(text)
            except NotifierError as exc:
                logger.error("notifier %s failed: %s", type(notifier).__name__, exc)
                errors.append(exc)
        if errors:
            raise NotifierError("; ".join(str(e) for e in errors))


class NullNotifier:
    """No-op notifier: logs instead of sending, for mock / no-webhook runs."""

    def __init__(self):
        self.sent: List[str] = []

    def send(self, text: str) -> None:
        self.sent.append(text)
        logger.warning("no notification webhook configured; alert not delivered:\n%s", text)


def create_notifier(
    slack_webhook_url: Optional[str] = None,
    discord_webhook_url: Optional[str] = None,
) -> Notifier:
    slack_webhook_url = slack_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    discord_webhook_url = discord_webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    notifiers: List[Notifier] = []
    if slack_webhook_url:
        notifiers.append(SlackNotifier(slack_webhook_url))
    if discord_webhook_url:
        notifiers.append(DiscordNotifier(discord_webhook_url))

    if not notifiers:
        return NullNotifier()
    if len(notifiers) == 1:
        return notifiers[0]
    return MultiNotifier(notifiers)
