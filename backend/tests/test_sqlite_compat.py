from __future__ import annotations

from sqlalchemy import create_engine

from app.db.sqlite_compat import ensure_sqlite_compat_columns


def _columns_for(engine, table_name: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
    return {str(row[1]) for row in rows}


def _table_exists(engine, table_name: str) -> bool:
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
    return row is not None


def test_ensure_sqlite_compat_columns_backfills_legacy_tables() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE items (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                title TEXT NOT NULL,
                raw_content TEXT NOT NULL,
                clean_content TEXT,
                short_summary TEXT,
                long_summary TEXT,
                score_value REAL,
                action_suggestion TEXT,
                status TEXT NOT NULL,
                processing_error TEXT,
                created_at DATETIME,
                processed_at DATETIME
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE focus_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                goal_text TEXT,
                duration_minutes INTEGER NOT NULL,
                start_time DATETIME,
                end_time DATETIME,
                summary_text TEXT,
                status TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE knowledge_entries (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source_domain TEXT,
                created_at DATETIME
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE research_jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                keyword TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE research_compare_snapshots (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                tracking_topic_id TEXT,
                name TEXT NOT NULL
            )
            """
        )

    ensure_sqlite_compat_columns(engine)

    item_columns = _columns_for(engine, "items")
    assert {
        "output_language",
        "ingest_route",
        "content_acquisition_status",
        "content_acquisition_note",
        "resolved_from_url",
        "fallback_used",
        "processing_started_at",
        "processing_attempts",
    }.issubset(item_columns)

    focus_session_columns = _columns_for(engine, "focus_sessions")
    assert {
        "output_language",
        "current_window_started_at",
        "paused_at",
        "elapsed_seconds",
    }.issubset(focus_session_columns)

    knowledge_columns = _columns_for(engine, "knowledge_entries")
    assert {"collection_name", "is_pinned", "is_focus_reference", "metadata_payload"}.issubset(
        knowledge_columns
    )

    research_job_columns = _columns_for(engine, "research_jobs")
    assert {"timeline_payload", "metrics_payload"}.issubset(research_job_columns)

    compare_snapshot_columns = _columns_for(engine, "research_compare_snapshots")
    assert {"report_version_id", "metadata_payload"}.issubset(compare_snapshot_columns)

    retrieval_chunk_columns = _columns_for(engine, "research_retrieval_index_chunks")
    assert {
        "user_id",
        "chunk_key",
        "schema_version",
        "document_id",
        "document_type",
        "metadata_payload",
    }.issubset(retrieval_chunk_columns)

    retrieval_checkpoint_columns = _columns_for(engine, "research_retrieval_index_checkpoints")
    assert {"user_id", "schema_version", "backend", "status", "next_offset"}.issubset(
        retrieval_checkpoint_columns
    )

    assert _table_exists(engine, "collector_import_batches")
    collector_import_batch_columns = _columns_for(engine, "collector_import_batches")
    assert {
        "user_id",
        "import_type",
        "source_label",
        "status",
        "output_language",
        "item_ids",
        "created_item_ids",
        "result_payload",
        "source_payload",
    }.issubset(collector_import_batch_columns)

    watchlist_run_columns = _columns_for(engine, "research_watchlist_runs")
    assert {
        "user_id",
        "watchlist_id",
        "run_id",
        "status",
        "attempt_count",
        "retry_count",
        "notification_payload",
    }.issubset(watchlist_run_columns)

    experiment_plan_columns = _columns_for(engine, "research_experiment_plans")
    assert {
        "user_id",
        "name",
        "lane_key",
        "strategy_family",
        "candidate_label",
        "strategy_payload",
        "gate_config_payload",
        "cohort_payload",
        "baseline_payload",
        "latest_gate_payload",
        "gate_history_payload",
        "rollout_payload",
        "status",
        "cohort_frozen_at",
        "baseline_locked_at",
        "last_gate_evaluated_at",
        "promoted_at",
        "rollout_revoked_at",
    }.issubset(experiment_plan_columns)
