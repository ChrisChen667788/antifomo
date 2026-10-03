from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import DatabaseError

from app import models  # noqa: F401
from app.db.base import Base
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
        "key_points",
        "content_score_reasons",
        "content_density",
        "novelty_level",
        "llm_receipts",
        "processing_degraded",
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


def test_ensure_sqlite_compat_columns_installs_full_evidence_integrity_guards() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    ensure_sqlite_compat_columns(engine)

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        user_id = uuid.uuid4().hex
        other_user_id = uuid.uuid4().hex
        item_id = uuid.uuid4().hex
        sibling_item_id = uuid.uuid4().hex
        other_item_id = uuid.uuid4().hex
        source_id = uuid.uuid4().hex
        other_source_id = uuid.uuid4().hex
        asset_id = uuid.uuid4().hex
        other_asset_id = uuid.uuid4().hex
        revision_id = uuid.uuid4().hex
        other_revision_id = uuid.uuid4().hex
        revision_key = "1" * 64
        other_revision_key = "2" * 64
        conn.exec_driver_sql(
            "INSERT INTO users (id, name, created_at) VALUES (?, 'compat-user', CURRENT_TIMESTAMP)",
            (user_id,),
        )
        conn.exec_driver_sql(
            "INSERT INTO users (id, name, created_at) VALUES (?, 'other-user', CURRENT_TIMESTAMP)",
            (other_user_id,),
        )
        for candidate_id, candidate_user_id, raw_content in (
            (item_id, user_id, "primary"),
            (sibling_item_id, user_id, "sibling"),
            (other_item_id, other_user_id, "other"),
        ):
            conn.exec_driver_sql(
                "INSERT INTO items "
                "(id, user_id, source_type, raw_content, status, created_at) "
                "VALUES (?, ?, 'text', ?, 'pending', CURRENT_TIMESTAMP)",
                (candidate_id, candidate_user_id, raw_content),
            )
        conn.exec_driver_sql(
            "INSERT INTO collector_raw_assets "
            "(id, user_id, sha256, mime_type, byte_size, raw_text, metadata_payload, created_at) "
            "VALUES (?, ?, ?, 'text/plain', 3, 'raw', '{}', CURRENT_TIMESTAMP)",
            (asset_id, user_id, "b" * 64),
        )
        conn.exec_driver_sql(
            "INSERT INTO collector_raw_assets "
            "(id, user_id, sha256, mime_type, byte_size, raw_text, metadata_payload, created_at) "
            "VALUES (?, ?, ?, 'text/plain', 5, 'other', '{}', CURRENT_TIMESTAMP)",
            (other_asset_id, other_user_id, "c" * 64),
        )
        conn.exec_driver_sql(
            "INSERT INTO collector_source_items "
            "(id, user_id, item_id, connector, native_item_id, metadata_payload) "
            "VALUES (?, ?, ?, 'manual', 'primary', '{}')",
            (source_id, user_id, item_id),
        )
        conn.exec_driver_sql(
            "INSERT INTO collector_source_items "
            "(id, user_id, item_id, connector, native_item_id, metadata_payload) "
            "VALUES (?, ?, ?, 'manual', 'other', '{}')",
            (other_source_id, other_user_id, other_item_id),
        )
        conn.exec_driver_sql(
            "INSERT INTO collector_document_revisions "
            "(id, source_item_id, raw_asset_id, item_id, revision_key, normalized_sha256, "
            "parser_fingerprint, diagnostics_payload) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')",
            (revision_id, source_id, asset_id, item_id, revision_key, "d" * 64, "e" * 64),
        )
        conn.exec_driver_sql(
            "INSERT INTO collector_document_revisions "
            "(id, source_item_id, raw_asset_id, item_id, revision_key, normalized_sha256, "
            "parser_fingerprint, diagnostics_payload) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')",
            (
                other_revision_id,
                other_source_id,
                other_asset_id,
                other_item_id,
                other_revision_key,
                "f" * 64,
                "a" * 64,
            ),
        )
        conn.exec_driver_sql(
            "UPDATE collector_source_items SET current_revision_key=? WHERE id=?",
            (revision_key, source_id),
        )

    with engine.connect() as conn:
        trigger_names = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND (name LIKE 'af_collector_%' OR name = 'af_items_collector_owner_update')"
            )
        }
    assert {
        "af_collector_source_items_tenant_insert",
        "af_collector_source_items_tenant_update",
        "af_collector_source_items_rebind_update",
        "af_collector_source_items_pointer_insert",
        "af_collector_source_items_pointer_update",
        "af_collector_document_revisions_tenant_insert",
        "af_collector_transform_receipts_tenant_insert",
        "af_items_collector_owner_update",
        "af_collector_revision_pointer_cleanup",
        "af_collector_raw_assets_no_update",
        "af_collector_document_revisions_no_update",
        "af_collector_source_spans_no_update",
        "af_collector_transform_receipts_no_update",
    } <= trigger_names

    with pytest.raises(DatabaseError, match="immutable while retained"):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "UPDATE collector_raw_assets SET raw_text='changed' WHERE id=?",
                (asset_id,),
            )

    with pytest.raises(DatabaseError, match="cannot be rebound"):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "UPDATE collector_source_items SET item_id=? WHERE id=?",
                (sibling_item_id, source_id),
            )

    with pytest.raises(DatabaseError):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "UPDATE collector_source_items SET user_id=?, item_id=? WHERE id=?",
                (other_user_id, other_item_id, source_id),
            )

    with pytest.raises(DatabaseError, match="does not belong"):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "UPDATE collector_source_items SET current_revision_key=? WHERE id=?",
                (other_revision_key, source_id),
            )

    with pytest.raises(DatabaseError, match="crosses user ownership"):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO collector_source_items "
                "(id, user_id, item_id, connector, native_item_id, metadata_payload) "
                "VALUES (?, ?, ?, 'manual', 'cross-tenant', '{}')",
                (uuid.uuid4().hex, user_id, other_item_id),
            )

    with pytest.raises(DatabaseError, match="crosses user ownership"):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO collector_document_revisions "
                "(id, source_item_id, raw_asset_id, item_id, revision_key, normalized_sha256, "
                "parser_fingerprint, diagnostics_payload) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')",
                (
                    uuid.uuid4().hex,
                    source_id,
                    other_asset_id,
                    item_id,
                    "3" * 64,
                    "4" * 64,
                    "5" * 64,
                ),
            )

    with pytest.raises(DatabaseError, match="crosses user ownership"):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO collector_transform_receipts "
                "(id, user_id, revision_id, item_id, stage, input_hash, stage_fingerprint, "
                "output_hash, status, usage_payload, diagnostics_payload) "
                "VALUES (?, ?, ?, ?, 'summary', ?, ?, ?, 'success', '{}', '{}')",
                (
                    uuid.uuid4().hex,
                    other_user_id,
                    revision_id,
                    item_id,
                    "6" * 64,
                    "7" * 64,
                    "8" * 64,
                ),
            )

    with pytest.raises(DatabaseError, match="cannot change ownership"):
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "UPDATE items SET user_id=? WHERE id=?",
                (other_user_id, item_id),
            )

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.exec_driver_sql("DELETE FROM collector_document_revisions WHERE id=?", (revision_id,))
        assert conn.exec_driver_sql(
            "SELECT current_revision_key FROM collector_source_items WHERE id=?", (source_id,)
        ).scalar_one() is None

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.exec_driver_sql("DELETE FROM users WHERE id=?", (user_id,))
        assert conn.exec_driver_sql(
            "SELECT count(*) FROM collector_raw_assets WHERE user_id=?", (user_id,)
        ).scalar_one() == 0


def test_ensure_sqlite_compat_scrubs_legacy_wechat_item_urls_idempotently() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    user_id = uuid.uuid4().hex
    item_id = uuid.uuid4().hex
    attempt_id = uuid.uuid4().hex
    legacy_url = (
        "https://mp.weixin.qq.com/s?__biz=MzCompat&mid=8&idx=1&sn=stable"
        "&scene=21&pass_ticket=compat-secret&key=temporary"
    )
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO users (id, name, created_at) VALUES (?, 'compat-url-user', CURRENT_TIMESTAMP)",
            (user_id,),
        )
        conn.exec_driver_sql(
            "INSERT INTO items "
            "(id, user_id, source_type, source_url, resolved_from_url, raw_content, "
            "clean_content, status, "
            "processing_error, content_acquisition_note, created_at) "
            "VALUES (?, ?, 'url', ?, ?, ?, ?, 'ready', ?, ?, CURRENT_TIMESTAMP)",
            (
                item_id,
                user_id,
                legacy_url,
                legacy_url,
                f"legacy link: {legacy_url}",
                f"clean link: {legacy_url}",
                f"fetch failed for {legacy_url}",
                f"body unavailable at {legacy_url}",
            ),
        )
        conn.exec_driver_sql(
            "INSERT INTO collector_ingest_attempts "
            "(id, user_id, item_id, source_url, source_type, route_type, resolver, "
            "attempt_status, error_detail, created_at) VALUES "
            "(?, ?, ?, ?, 'url', 'direct_url', 'legacy', 'failed', ?, CURRENT_TIMESTAMP)",
            (
                attempt_id,
                user_id,
                item_id,
                legacy_url,
                f"attempt failed for {legacy_url}",
            ),
        )

    ensure_sqlite_compat_columns(engine)
    ensure_sqlite_compat_columns(engine)

    with engine.connect() as conn:
        source_url, resolved_from_url = conn.exec_driver_sql(
            "SELECT source_url, resolved_from_url FROM items WHERE id = ?",
            (item_id,),
        ).one()
        assert source_url == (
            "https://mp.weixin.qq.com/s?__biz=MzCompat&mid=8&idx=1&sn=stable"
        )
        assert resolved_from_url == source_url
        assert "pass_ticket" not in source_url
        assert "compat-secret" not in resolved_from_url
        assert "key=temporary" not in source_url
        processing_error, content_note = conn.exec_driver_sql(
            "SELECT processing_error, content_acquisition_note FROM items WHERE id = ?",
            (item_id,),
        ).one()
        raw_content, clean_content = conn.exec_driver_sql(
            "SELECT raw_content, clean_content FROM items WHERE id = ?",
            (item_id,),
        ).one()
        attempt_url, attempt_error = conn.exec_driver_sql(
            "SELECT source_url, error_detail FROM collector_ingest_attempts WHERE id = ?",
            (attempt_id,),
        ).one()
        for persisted_value in (
            processing_error,
            content_note,
            raw_content,
            clean_content,
            attempt_url,
            attempt_error,
        ):
            assert "pass_ticket" not in persisted_value
            assert "compat-secret" not in persisted_value
            assert "key=temporary" not in persisted_value
        assert conn.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    engine.dispose()
