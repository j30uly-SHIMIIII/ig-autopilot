"""Notification backends for out-of-band alerts (e.g. ForexFactory red-alert).

create_notifier() mirrors src/publisher/ig_client.py's create_ig_client():
it falls back to a no-op notifier when SLACK_WEBHOOK_URL isn't configured,
so the rest of the pipeline can run and be tested without real credentials.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Protocol

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


class NullNotifier:
    """No-op notifier: logs instead of sending, for mock / no-webhook runs."""

    def __init__(self):
        self.sent: List[str] = []

    def send(self, text: str) -> None:
        self.sent.append(text)
        logger.warning("SLACK_WEBHOOK_URL not configured; alert not delivered:\n%s", text)


def create_notifier(webhook_url: Optional[str] = None) -> Notifier:
    webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return NullNotifier()
    return SlackNotifier(webhook_url)
