from __future__ import annotations

from sqlalchemy.engine import Engine


def _table_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
    if not rows:
        return False
    return any(str(row[1]) == column_name for row in rows)


def ensure_sqlite_compat_columns(engine: Engine) -> None:
    if not str(engine.url).startswith("sqlite"):
        return

    statements: list[str] = []
    if not _table_has_column(engine, "items", "output_language"):
        statements.append(
            "ALTER TABLE items ADD COLUMN output_language VARCHAR(10) NOT NULL DEFAULT 'zh-CN'"
        )
    if not _table_has_column(engine, "items", "processing_started_at"):
        statements.append(
            "ALTER TABLE items ADD COLUMN processing_started_at DATETIME NULL"
        )
    if not _table_has_column(engine, "items", "processing_attempts"):
        statements.append(
            "ALTER TABLE items ADD COLUMN processing_attempts INTEGER NOT NULL DEFAULT 0"
        )
    if not _table_has_column(engine, "focus_sessions", "output_language"):
        statements.append(
            "ALTER TABLE focus_sessions ADD COLUMN output_language VARCHAR(10) NOT NULL DEFAULT 'zh-CN'"
        )
    if not _table_has_column(engine, "knowledge_entries", "metadata_payload"):
        statements.append(
            "ALTER TABLE knowledge_entries ADD COLUMN metadata_payload JSON NULL"
        )

    if not statements:
        return

    with engine.begin() as conn:
        for statement in statements:
            conn.exec_driver_sql(statement)
