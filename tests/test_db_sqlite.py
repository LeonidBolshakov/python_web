import sqlite3

from db import connect, init_schema


def test_init_schema_createse_users_table(tmp_path):
    db_file = tmp_path / "test.db"
    conn = connect(db_file)

    try:
        init_schema(conn)

        row = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='users'
            """).fetchone()
        assert row is not None
        assert row["name"] == "users"
    finally:
        conn.close()
