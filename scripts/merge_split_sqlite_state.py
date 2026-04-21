#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


ROW_ID_TABLES = [
    "items",
    "focus_sessions",
    "item_tags",
    "feedbacks",
    "knowledge_entries",
    "session_items",
    "collector_ingest_attempts",
    "work_tasks",
]


def table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA main.table_info({table_name})").fetchall()
    return [str(row[1]) for row in rows]


def insert_missing_by_id(conn: sqlite3.Connection, table_name: str) -> int:
    columns = table_columns(conn, table_name)
    if not columns or "id" not in columns:
        return 0
    column_sql = ", ".join(columns)
    select_sql = ", ".join(f"source_db.{table_name}.{column}" for column in columns)
    before = conn.total_changes
    conn.execute(
        f"""
        INSERT INTO main.{table_name} ({column_sql})
        SELECT {select_sql}
        FROM source_db.{table_name}
        WHERE source_db.{table_name}.id NOT IN (
            SELECT id FROM main.{table_name}
        )
        """
    )
    return conn.total_changes - before


def upsert_knowledge_rule(conn: sqlite3.Connection) -> int:
    source_rows = conn.execute(
        """
        SELECT user_id, enabled, min_score_value, archive_on_like, archive_on_save, created_at, updated_at
        FROM source_db.knowledge_rules
        """
    ).fetchall()
    changes = 0
    for row in source_rows:
        existing = conn.execute(
            "SELECT id, updated_at FROM main.knowledge_rules WHERE user_id = ?",
            (row[0],),
        ).fetchone()
        if existing is None:
            before = conn.total_changes
            conn.execute(
                """
                INSERT INTO main.knowledge_rules
                (id, user_id, enabled, min_score_value, archive_on_like, archive_on_save, created_at, updated_at)
                SELECT id, user_id, enabled, min_score_value, archive_on_like, archive_on_save, created_at, updated_at
                FROM source_db.knowledge_rules
                WHERE user_id = ?
                """,
                (row[0],),
            )
            changes += conn.total_changes - before
            continue
        if (row[6] or "") > (existing[1] or ""):
            before = conn.total_changes
            conn.execute(
                """
                UPDATE main.knowledge_rules
                SET enabled = ?,
                    min_score_value = ?,
                    archive_on_like = ?,
                    archive_on_save = ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (row[1], row[2], row[3], row[4], row[6], row[0]),
            )
            changes += conn.total_changes - before
    return changes


def upsert_preference_table(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    key_column: str,
) -> int:
    source_rows = conn.execute(
        f"SELECT id, user_id, {key_column}, preference_score, updated_at FROM source_db.{table_name}"
    ).fetchall()
    changes = 0
    for row in source_rows:
        existing = conn.execute(
            f"SELECT id, updated_at FROM main.{table_name} WHERE user_id = ? AND {key_column} = ?",
            (row[1], row[2]),
        ).fetchone()
        if existing is None:
            before = conn.total_changes
            conn.execute(
                f"""
                INSERT INTO main.{table_name} (id, user_id, {key_column}, preference_score, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row[0], row[1], row[2], row[3], row[4]),
            )
            changes += conn.total_changes - before
            continue
        if (row[4] or "") > (existing[1] or ""):
            before = conn.total_changes
            conn.execute(
                f"""
                UPDATE main.{table_name}
                SET preference_score = ?,
                    updated_at = ?
                WHERE user_id = ? AND {key_column} = ?
                """,
                (row[3], row[4], row[1], row[2]),
            )
            changes += conn.total_changes - before
    return changes


def merge_databases(source_db: Path, dest_db: Path) -> dict[str, int]:
    conn = sqlite3.connect(dest_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"ATTACH DATABASE '{source_db}' AS source_db")
    results: dict[str, int] = {}
    try:
        with conn:
            for table_name in ROW_ID_TABLES:
                results[table_name] = insert_missing_by_id(conn, table_name)
            results["knowledge_rules"] = upsert_knowledge_rule(conn)
            results["source_preferences"] = upsert_preference_table(
                conn,
                table_name="source_preferences",
                key_column="source_domain",
            )
            results["topic_preferences"] = upsert_preference_table(
                conn,
                table_name="topic_preferences",
                key_column="tag_name",
            )
    finally:
        conn.execute("DETACH DATABASE source_db")
        conn.close()
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge rows from a split local SQLite state DB into the main DB.")
    parser.add_argument("--source-db", required=True, help="Path to the smaller/source SQLite database.")
    parser.add_argument("--dest-db", required=True, help="Path to the main/destination SQLite database.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    source_db = Path(args.source_db).resolve()
    dest_db = Path(args.dest_db).resolve()
    if not source_db.exists():
        raise SystemExit(f"Source database not found: {source_db}")
    if not dest_db.exists():
        raise SystemExit(f"Destination database not found: {dest_db}")
    results = merge_databases(source_db, dest_db)
    for key, value in results.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
