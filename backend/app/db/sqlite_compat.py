from __future__ import annotations

from sqlalchemy.engine import Engine


def _table_exists(engine: Engine, table_name: str) -> bool:
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name",
            {"table_name": table_name},
        ).fetchone()
    return row is not None


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
    if _table_exists(engine, "items") and not _table_has_column(engine, "items", "output_language"):
        statements.append(
            "ALTER TABLE items ADD COLUMN output_language VARCHAR(10) NOT NULL DEFAULT 'zh-CN'"
        )
    if _table_exists(engine, "items") and not _table_has_column(engine, "items", "ingest_route"):
        statements.append(
            "ALTER TABLE items ADD COLUMN ingest_route VARCHAR(40) NULL"
        )
    if _table_exists(engine, "items") and not _table_has_column(engine, "items", "content_acquisition_status"):
        statements.append(
            "ALTER TABLE items ADD COLUMN content_acquisition_status VARCHAR(30) NOT NULL DEFAULT 'pending'"
        )
    if _table_exists(engine, "items") and not _table_has_column(engine, "items", "content_acquisition_note"):
        statements.append(
            "ALTER TABLE items ADD COLUMN content_acquisition_note TEXT NULL"
        )
    if _table_exists(engine, "items") and not _table_has_column(engine, "items", "resolved_from_url"):
        statements.append(
            "ALTER TABLE items ADD COLUMN resolved_from_url TEXT NULL"
        )
    if _table_exists(engine, "items") and not _table_has_column(engine, "items", "fallback_used"):
        statements.append(
            "ALTER TABLE items ADD COLUMN fallback_used BOOLEAN NOT NULL DEFAULT 0"
        )
    if _table_exists(engine, "items") and not _table_has_column(engine, "items", "processing_started_at"):
        statements.append(
            "ALTER TABLE items ADD COLUMN processing_started_at DATETIME NULL"
        )
    if _table_exists(engine, "items") and not _table_has_column(engine, "items", "processing_attempts"):
        statements.append(
            "ALTER TABLE items ADD COLUMN processing_attempts INTEGER NOT NULL DEFAULT 0"
        )
    if _table_exists(engine, "focus_sessions") and not _table_has_column(engine, "focus_sessions", "output_language"):
        statements.append(
            "ALTER TABLE focus_sessions ADD COLUMN output_language VARCHAR(10) NOT NULL DEFAULT 'zh-CN'"
        )
    if _table_exists(engine, "focus_sessions") and not _table_has_column(
        engine, "focus_sessions", "current_window_started_at"
    ):
        statements.append(
            "ALTER TABLE focus_sessions ADD COLUMN current_window_started_at DATETIME NULL"
        )
    if _table_exists(engine, "focus_sessions") and not _table_has_column(engine, "focus_sessions", "paused_at"):
        statements.append(
            "ALTER TABLE focus_sessions ADD COLUMN paused_at DATETIME NULL"
        )
    if _table_exists(engine, "focus_sessions") and not _table_has_column(engine, "focus_sessions", "elapsed_seconds"):
        statements.append(
            "ALTER TABLE focus_sessions ADD COLUMN elapsed_seconds INTEGER NOT NULL DEFAULT 0"
        )
    if _table_exists(engine, "knowledge_entries") and not _table_has_column(engine, "knowledge_entries", "collection_name"):
        statements.append(
            "ALTER TABLE knowledge_entries ADD COLUMN collection_name VARCHAR(80) NULL"
        )
    if _table_exists(engine, "knowledge_entries") and not _table_has_column(engine, "knowledge_entries", "is_pinned"):
        statements.append(
            "ALTER TABLE knowledge_entries ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0"
        )
    if _table_exists(engine, "knowledge_entries") and not _table_has_column(engine, "knowledge_entries", "is_focus_reference"):
        statements.append(
            "ALTER TABLE knowledge_entries ADD COLUMN is_focus_reference BOOLEAN NOT NULL DEFAULT 0"
        )
    if _table_exists(engine, "knowledge_entries") and not _table_has_column(engine, "knowledge_entries", "metadata_payload"):
        statements.append(
            "ALTER TABLE knowledge_entries ADD COLUMN metadata_payload JSON NULL"
        )
    if _table_exists(engine, "research_jobs") and not _table_has_column(engine, "research_jobs", "timeline_payload"):
        statements.append(
            "ALTER TABLE research_jobs ADD COLUMN timeline_payload JSON NOT NULL DEFAULT '[]'"
        )
    if _table_exists(engine, "research_compare_snapshots") and not _table_has_column(
        engine, "research_compare_snapshots", "report_version_id"
    ):
        statements.append(
            "ALTER TABLE research_compare_snapshots ADD COLUMN report_version_id CHAR(32) NULL"
        )
    if _table_exists(engine, "research_compare_snapshots") and not _table_has_column(
        engine, "research_compare_snapshots", "metadata_payload"
    ):
        statements.append(
            "ALTER TABLE research_compare_snapshots ADD COLUMN metadata_payload JSON NULL"
        )
    if not _table_exists(engine, "research_retrieval_index_chunks"):
        statements.extend(
            [
                """
                CREATE TABLE research_retrieval_index_chunks (
                    id CHAR(32) NOT NULL PRIMARY KEY,
                    user_id CHAR(32) NOT NULL,
                    chunk_key VARCHAR(160) NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    document_id VARCHAR(80) NOT NULL,
                    document_type VARCHAR(40) NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL DEFAULT '',
                    field_key VARCHAR(80) NOT NULL DEFAULT 'content',
                    label VARCHAR(120) NOT NULL DEFAULT '',
                    source_tier VARCHAR(20) NOT NULL DEFAULT 'media',
                    source_url TEXT NOT NULL DEFAULT '',
                    parent_chunk_id VARCHAR(160) NOT NULL DEFAULT '',
                    topic_id VARCHAR(80) NOT NULL DEFAULT '',
                    topic_name VARCHAR(120) NOT NULL DEFAULT '',
                    region VARCHAR(80) NOT NULL DEFAULT '',
                    industry VARCHAR(80) NOT NULL DEFAULT '',
                    priority INTEGER NOT NULL DEFAULT 0,
                    metadata_payload JSON NOT NULL DEFAULT '{}',
                    indexed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_research_retrieval_chunks_user_key UNIQUE (user_id, chunk_key),
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_research_retrieval_chunks_user_updated ON research_retrieval_index_chunks (user_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_research_retrieval_chunks_document ON research_retrieval_index_chunks (document_type, document_id)",
                "CREATE INDEX IF NOT EXISTS idx_research_retrieval_chunks_topic ON research_retrieval_index_chunks (topic_id)",
                "CREATE INDEX IF NOT EXISTS idx_research_retrieval_chunks_source_tier ON research_retrieval_index_chunks (source_tier)",
            ]
        )
    if not _table_exists(engine, "research_retrieval_index_checkpoints"):
        statements.extend(
            [
                """
                CREATE TABLE research_retrieval_index_checkpoints (
                    id CHAR(32) NOT NULL PRIMARY KEY,
                    user_id CHAR(32) NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    backend VARCHAR(30) NOT NULL DEFAULT 'sqlite',
                    status VARCHAR(20) NOT NULL DEFAULT 'idle',
                    total_chunks INTEGER NOT NULL DEFAULT 0,
                    indexed_chunks INTEGER NOT NULL DEFAULT 0,
                    next_offset INTEGER NOT NULL DEFAULT 0,
                    checkpoint_payload JSON NOT NULL DEFAULT '{}',
                    started_at DATETIME NULL,
                    completed_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_research_retrieval_checkpoint_user_schema UNIQUE (user_id, schema_version, backend),
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_research_retrieval_checkpoint_user_updated ON research_retrieval_index_checkpoints (user_id, updated_at)",
            ]
        )

    if not statements:
        return

    with engine.begin() as conn:
        for statement in statements:
            conn.exec_driver_sql(statement)
