import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

from src.common.db import connect, get_connection
from src.publisher.ig_client import IGAPIError, MockIGClient
from src.publisher.scheduler import TIMESTAMP_FORMAT, run_once

TZ = "UTC"


class AlwaysFailingClient:
    def publish_carousel(self, image_urls, caption):
        raise IGAPIError("simulated permanent failure")


def _write_config(tmp_path, **retry_overrides):
    config = {
        "timezone": TZ,
        "posting": {"feed_per_day": 1, "feed_times": ["19:00"]},
        "rate_limit": {"max_posts_per_24h": 25},
        "retry": {"max_attempts": 3, "backoff_base_seconds": 60, **retry_overrides},
        "scheduler": {"poll_interval_minutes": 5},
    }
    path = tmp_path / "account.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def _insert_queue_item(db_path, *, scheduled_at, status="pending", attempts=0):
    with connect(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO queue (caption, hashtags, image_paths, scheduled_at, status, attempts)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("テストキャプション", "#NISA #投資", json.dumps(["slide_01.png"]), scheduled_at, status, attempts),
        )
        return cursor.lastrowid


def _fmt(dt: datetime) -> str:
    return dt.strftime(TIMESTAMP_FORMAT)


def test_run_once_publishes_due_item(tmp_path):
    db_path = tmp_path / "queue.db"
    config_path = _write_config(tmp_path)
    past = _fmt(datetime.now(ZoneInfo(TZ)) - timedelta(minutes=5))
    queue_id = _insert_queue_item(db_path, scheduled_at=past)

    client = MockIGClient()
    summary = run_once(db_path=db_path, config_path=config_path, client=client)

    assert summary == {"published": 1, "failed": 0, "retried": 0, "checked": 1}

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM queue WHERE id = ?", (queue_id,)).fetchone()
    posts = conn.execute("SELECT * FROM posts WHERE queue_id = ?", (queue_id,)).fetchall()
    conn.close()

    assert row["status"] == "published"
    assert row["ig_media_id"] is not None
    assert len(posts) == 1


def test_run_once_skips_future_item(tmp_path):
    db_path = tmp_path / "queue.db"
    config_path = _write_config(tmp_path)
    future = _fmt(datetime.now(ZoneInfo(TZ)) + timedelta(hours=2))
    _insert_queue_item(db_path, scheduled_at=future)

    summary = run_once(db_path=db_path, config_path=config_path, client=MockIGClient())

    assert summary == {"published": 0, "failed": 0, "retried": 0, "checked": 0}


def test_run_once_retries_then_reschedules(tmp_path):
    db_path = tmp_path / "queue.db"
    config_path = _write_config(tmp_path, max_attempts=3)
    past = _fmt(datetime.now(ZoneInfo(TZ)) - timedelta(minutes=5))
    queue_id = _insert_queue_item(db_path, scheduled_at=past)

    summary = run_once(db_path=db_path, config_path=config_path, client=AlwaysFailingClient())

    assert summary == {"published": 0, "failed": 0, "retried": 1, "checked": 1}

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM queue WHERE id = ?", (queue_id,)).fetchone()
    conn.close()

    assert row["status"] == "pending"
    assert row["attempts"] == 1
    # rescheduled into the future (backoff), so it won't be picked up immediately
    assert row["scheduled_at"] > past


def test_run_once_marks_failed_after_max_attempts(tmp_path):
    db_path = tmp_path / "queue.db"
    config_path = _write_config(tmp_path, max_attempts=1)
    past = _fmt(datetime.now(ZoneInfo(TZ)) - timedelta(minutes=5))
    queue_id = _insert_queue_item(db_path, scheduled_at=past)

    summary = run_once(db_path=db_path, config_path=config_path, client=AlwaysFailingClient())

    assert summary == {"published": 0, "failed": 1, "retried": 0, "checked": 1}

    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM queue WHERE id = ?", (queue_id,)).fetchone()
    conn.close()

    assert row["status"] == "failed"
    assert row["last_error"]
