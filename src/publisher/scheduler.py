"""Polls the queue table and publishes due posts via ig_client.

Intended to run every 5 minutes from cron (see crontab.txt), matching
account.yaml's scheduler.poll_interval_minutes. Failed publishes are
retried with exponential backoff (account.yaml: retry.*) up to
retry.max_attempts, after which the item is marked 'failed' for manual
review rather than retried forever.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import yaml

from src.common.db import connect, DEFAULT_DB_PATH
from src.publisher.ig_client import IGAPIError, create_ig_client

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "account.yaml"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger(__name__)


def load_config(config_path: Path | str = DEFAULT_CONFIG_PATH) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _now_str(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).strftime(TIMESTAMP_FORMAT)


def fetch_due_items(conn: sqlite3.Connection, now: str) -> list[sqlite3.Row]:
    cursor = conn.execute(
        "SELECT * FROM queue WHERE status = 'pending' AND scheduled_at <= ? ORDER BY scheduled_at ASC",
        (now,),
    )
    return cursor.fetchall()


def _build_caption(item: sqlite3.Row) -> str:
    caption = item["caption"] or ""
    hashtags = item["hashtags"] or ""
    return f"{caption}\n\n{hashtags}".strip()


def _backoff_seconds(base_seconds: int, attempts: int) -> int:
    return base_seconds * (2 ** max(attempts - 1, 0))


def publish_item(
    conn: sqlite3.Connection,
    item: sqlite3.Row,
    client,
    retry_cfg: dict,
    timezone: str,
) -> bool:
    """Attempts to publish one queue item; returns True on success."""
    image_paths = json.loads(item["image_paths"] or "[]")
    caption = _build_caption(item)

    try:
        media_id = client.publish_carousel(image_paths, caption)
    except (IGAPIError, ValueError) as exc:
        attempts = item["attempts"] + 1
        max_attempts = retry_cfg.get("max_attempts", 3)
        if attempts >= max_attempts:
            conn.execute(
                "UPDATE queue SET status = 'failed', attempts = ?, last_error = ?, updated_at = datetime('now') WHERE id = ?",
                (attempts, str(exc), item["id"]),
            )
            logger.error("queue item %s failed permanently after %s attempts: %s", item["id"], attempts, exc)
        else:
            backoff = _backoff_seconds(retry_cfg.get("backoff_base_seconds", 60), attempts)
            next_attempt = datetime.now(ZoneInfo(timezone)).timestamp() + backoff
            next_attempt_str = datetime.fromtimestamp(next_attempt, ZoneInfo(timezone)).strftime(TIMESTAMP_FORMAT)
            conn.execute(
                "UPDATE queue SET attempts = ?, last_error = ?, scheduled_at = ?, updated_at = datetime('now') WHERE id = ?",
                (attempts, str(exc), next_attempt_str, item["id"]),
            )
            logger.warning("queue item %s failed (attempt %s/%s), retrying at %s: %s",
                            item["id"], attempts, max_attempts, next_attempt_str, exc)
        return False

    conn.execute(
        "UPDATE queue SET status = 'published', ig_media_id = ?, updated_at = datetime('now') WHERE id = ?",
        (media_id, item["id"]),
    )
    conn.execute(
        "INSERT INTO posts (queue_id, ig_media_id) VALUES (?, ?)",
        (item["id"], media_id),
    )
    logger.info("queue item %s published as %s", item["id"], media_id)
    return True


def run_once(
    db_path: Path | str = DEFAULT_DB_PATH,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    client=None,
) -> dict:
    config = load_config(config_path)
    timezone = config.get("timezone", "UTC")
    retry_cfg = config.get("retry", {})
    client = client or create_ig_client()

    now = _now_str(timezone)
    summary = {"published": 0, "failed": 0, "retried": 0, "checked": 0}

    with connect(db_path) as conn:
        due_items = fetch_due_items(conn, now)
        summary["checked"] = len(due_items)
        for item in due_items:
            success = publish_item(conn, item, client, retry_cfg, timezone)
            if success:
                summary["published"] += 1
            else:
                refreshed = conn.execute("SELECT status FROM queue WHERE id = ?", (item["id"],)).fetchone()
                if refreshed["status"] == "failed":
                    summary["failed"] += 1
                else:
                    summary["retried"] += 1

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_once()
    logger.info("scheduler run complete: %s", result)
