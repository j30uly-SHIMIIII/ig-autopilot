from src.common.db import connect, get_connection, init_db


def test_init_db_creates_tables(tmp_path):
    db_path = tmp_path / "queue.db"
    init_db(db_path)

    conn = get_connection(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    conn.close()

    assert {"queue", "posts"}.issubset(tables)


def test_connect_inserts_and_commits(tmp_path):
    db_path = tmp_path / "queue.db"

    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO queue (caption, scheduled_at) VALUES (?, ?)",
            ("test caption", "2026-07-20 19:00:00"),
        )

    conn = get_connection(db_path)
    row = conn.execute("SELECT caption, status FROM queue").fetchone()
    conn.close()

    assert row["caption"] == "test caption"
    assert row["status"] == "pending"
