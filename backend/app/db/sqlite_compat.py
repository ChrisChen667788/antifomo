from __future__ import annotations

import json
import re
from urllib import parse as urllib_parse

from sqlalchemy.engine import Engine

from app.services.source_url_privacy import (
    canonicalize_persisted_url,
    redact_sensitive_url_values,
)


_LEGACY_HTTP_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", flags=re.IGNORECASE)
_LEGACY_TRAILING_URL_PUNCTUATION_PATTERN = re.compile(r"[),.;，。；）】》]+$")


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


def _canonicalize_legacy_wechat_url(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    try:
        parsed = urllib_parse.urlsplit(raw)
        hostname = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return value
    if hostname != "mp.weixin.qq.com":
        return value
    canonical = canonicalize_persisted_url(value)
    if canonical is not None:
        return canonical
    # A malformed legacy port is unusable but the hostname remains clear.
    # Rebuild without the port so signed query values are still removed.
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return value
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    values_by_key: dict[str, list[str]] = {
        key: [] for key in ("__biz", "mid", "idx", "sn", "chksm")
    }
    for key, item in urllib_parse.parse_qsl(parsed.query, keep_blank_values=True):
        if key in values_by_key:
            values_by_key[key].append(item)
    query = urllib_parse.urlencode(
        [
            (key, item)
            for key in ("__biz", "mid", "idx", "sn", "chksm")
            for item in sorted(values_by_key[key])
        ],
        doseq=True,
    )
    return urllib_parse.urlunsplit((scheme, hostname, path, query, ""))


def _redact_legacy_wechat_urls(value: object) -> str:
    text = str(value or "")

    def replace(match: re.Match[str]) -> str:
        candidate = match.group(0)
        trailing_match = _LEGACY_TRAILING_URL_PUNCTUATION_PATTERN.search(candidate)
        trailing = trailing_match.group(0) if trailing_match else ""
        core = candidate[: -len(trailing)] if trailing else candidate
        canonical = _canonicalize_legacy_wechat_url(core)
        return f"{canonical if canonical is not None else '[invalid-url]'}{trailing}"

    return _LEGACY_HTTP_URL_PATTERN.sub(replace, text)


def _scrub_legacy_json_text(value: object) -> str:
    try:
        decoded = json.loads(str(value)) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return _redact_legacy_wechat_urls(value)
    scrubbed = redact_sensitive_url_values(decoded)
    return json.dumps(scrubbed, ensure_ascii=False, separators=(",", ":"))


def _sqlite_columns(conn, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
    }


def _merge_sqlite_collector_source_duplicate(conn, row, canonical_url: str) -> bool:
    duplicate = conn.exec_driver_sql(
        "SELECT id, note, enabled, last_collected_at, last_error, created_at, updated_at "
        "FROM collector_sources WHERE user_id = ? AND source_url = ? AND id <> ? LIMIT 1",
        (row["user_id"], canonical_url, row["id"]),
    ).mappings().first()
    if duplicate is None:
        return False
    newest_collection = max(
        (value for value in (duplicate["last_collected_at"], row["last_collected_at"]) if value is not None),
        default=None,
    )
    incoming_error = (
        _redact_legacy_wechat_urls(row["last_error"])
        if row["last_error"] is not None
        else None
    )
    duplicate_error = (
        _redact_legacy_wechat_urls(duplicate["last_error"])
        if duplicate["last_error"] is not None
        else None
    )
    merged_error = (
        incoming_error
        if newest_collection == row["last_collected_at"] and incoming_error is not None
        else duplicate_error or incoming_error
    )
    conn.exec_driver_sql(
        "UPDATE collector_sources SET note = ?, enabled = ?, last_collected_at = ?, "
        "last_error = ?, created_at = ?, updated_at = ? WHERE id = ?",
        (
            duplicate["note"] or row["note"],
            1 if duplicate["enabled"] or row["enabled"] else 0,
            newest_collection,
            merged_error,
            min(duplicate["created_at"], row["created_at"]),
            max(duplicate["updated_at"], row["updated_at"]),
            duplicate["id"],
        ),
    )
    conn.exec_driver_sql("DELETE FROM collector_sources WHERE id = ?", (row["id"],))
    return True


def _scrub_sqlite_text_table(
    conn,
    *,
    table_name: str,
    url_columns: tuple[str, ...] = (),
    text_columns: tuple[str, ...] = (),
) -> None:
    columns = _sqlite_columns(conn, table_name)
    transforms = {
        **{name: _canonicalize_legacy_wechat_url for name in url_columns if name in columns},
        **{name: _redact_legacy_wechat_urls for name in text_columns if name in columns},
    }
    if not transforms:
        return
    selected_columns = ["id", *transforms]
    if table_name == "collector_sources":
        selected_columns.extend(
            [
                "user_id",
                "note",
                "enabled",
                "last_collected_at",
                "created_at",
                "updated_at",
            ]
        )
    selected = ", ".join(dict.fromkeys(selected_columns))
    predicates = " OR ".join(
        f"lower(coalesce(CAST({name} AS TEXT), '')) LIKE ?" for name in transforms
    )
    rows = list(
        conn.exec_driver_sql(
            f"SELECT {selected} FROM {table_name} WHERE {predicates}",
            tuple("%mp.weixin.qq.com%" for _ in transforms),
        ).mappings()
    )
    for row in rows:
        updates = {
            name: transformed
            for name, transform in transforms.items()
            if (transformed := transform(row[name])) != row[name]
        }
        if not updates:
            continue
        if (
            table_name == "collector_sources"
            and isinstance(updates.get("source_url"), str)
            and _merge_sqlite_collector_source_duplicate(
                conn, row, updates["source_url"]
            )
        ):
            continue
        assignments = ", ".join(f"{name} = ?" for name in updates)
        conn.exec_driver_sql(
            f"UPDATE {table_name} SET {assignments} WHERE id = ?",
            (*updates.values(), row["id"]),
        )


def _scrub_sqlite_json_column(conn, *, table_name: str, column_name: str) -> None:
    if column_name not in _sqlite_columns(conn, table_name):
        return
    rows = list(
        conn.exec_driver_sql(
            f"SELECT id, {column_name} FROM {table_name} "
            f"WHERE lower(coalesce(CAST({column_name} AS TEXT), '')) LIKE ?",
            ("%mp.weixin.qq.com%",),
        ).mappings()
    )
    for row in rows:
        scrubbed = _scrub_legacy_json_text(row[column_name])
        if scrubbed != row[column_name]:
            conn.exec_driver_sql(
                f"UPDATE {table_name} SET {column_name} = ? WHERE id = ?",
                (scrubbed, row["id"]),
            )


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
    item_additions = (
        ("key_points", "JSON NOT NULL DEFAULT '[]'"),
        ("content_score_reasons", "JSON NOT NULL DEFAULT '[]'"),
        ("content_density", "VARCHAR(20) NULL"),
        ("novelty_level", "VARCHAR(20) NULL"),
        ("llm_receipts", "JSON NOT NULL DEFAULT '[]'"),
        ("processing_degraded", "BOOLEAN NOT NULL DEFAULT 0"),
    )
    for column_name, column_sql in item_additions:
        if _table_exists(engine, "items") and not _table_has_column(engine, "items", column_name):
            statements.append(f"ALTER TABLE items ADD COLUMN {column_name} {column_sql}")
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
    if _table_exists(engine, "research_jobs") and not _table_has_column(engine, "research_jobs", "metrics_payload"):
        statements.append(
            "ALTER TABLE research_jobs ADD COLUMN metrics_payload JSON NOT NULL DEFAULT '{}'"
        )
    if _table_exists(engine, "research_jobs") and not _table_has_column(engine, "research_jobs", "request_payload"):
        statements.append(
            "ALTER TABLE research_jobs ADD COLUMN request_payload JSON NOT NULL DEFAULT '{}'"
        )
    if _table_exists(engine, "research_jobs") and not _table_has_column(engine, "research_jobs", "worker_id"):
        statements.append(
            "ALTER TABLE research_jobs ADD COLUMN worker_id VARCHAR(80) NOT NULL DEFAULT ''"
        )
    if _table_exists(engine, "research_jobs") and not _table_has_column(engine, "research_jobs", "lease_expires_at"):
        statements.append(
            "ALTER TABLE research_jobs ADD COLUMN lease_expires_at DATETIME NULL"
        )
    if _table_exists(engine, "research_jobs") and not _table_has_column(engine, "research_jobs", "execution_attempts"):
        statements.append(
            "ALTER TABLE research_jobs ADD COLUMN execution_attempts INTEGER NOT NULL DEFAULT 0"
        )
    if _table_exists(engine, "research_jobs"):
        statements.append(
            "CREATE INDEX IF NOT EXISTS idx_research_jobs_worker_lease ON research_jobs (worker_id, lease_expires_at)"
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
    if not _table_exists(engine, "collector_import_batches"):
        statements.extend(
            [
                """
                CREATE TABLE collector_import_batches (
                    id CHAR(32) NOT NULL PRIMARY KEY,
                    user_id CHAR(32) NOT NULL,
                    import_type VARCHAR(40) NOT NULL DEFAULT 'wechat_favorites',
                    source_label VARCHAR(120) NOT NULL DEFAULT '微信收藏',
                    status VARCHAR(30) NOT NULL DEFAULT 'queued',
                    output_language VARCHAR(10) NOT NULL DEFAULT 'zh-CN',
                    processing_deferred BOOLEAN NOT NULL DEFAULT 1,
                    total_candidates INTEGER NOT NULL DEFAULT 0,
                    created_count INTEGER NOT NULL DEFAULT 0,
                    deduplicated_count INTEGER NOT NULL DEFAULT 0,
                    invalid_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    item_ids JSON NOT NULL DEFAULT '[]',
                    created_item_ids JSON NOT NULL DEFAULT '[]',
                    result_payload JSON NOT NULL DEFAULT '[]',
                    source_payload JSON NOT NULL DEFAULT '{}',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_collector_import_batches_user_created ON collector_import_batches (user_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_collector_import_batches_type_status ON collector_import_batches (import_type, status)",
            ]
        )
    if not _table_exists(engine, "research_watchlist_runs"):
        statements.extend(
            [
                """
                CREATE TABLE research_watchlist_runs (
                    id CHAR(32) NOT NULL PRIMARY KEY,
                    user_id CHAR(32) NOT NULL,
                    watchlist_id CHAR(32) NULL,
                    run_id VARCHAR(80) NOT NULL,
                    watchlist_name VARCHAR(120) NOT NULL DEFAULT '',
                    status VARCHAR(20) NOT NULL DEFAULT 'refreshed',
                    change_count INTEGER NOT NULL DEFAULT 0,
                    attempt_count INTEGER NOT NULL DEFAULT 1,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    summary TEXT NOT NULL DEFAULT '',
                    error TEXT NULL,
                    notification_level VARCHAR(20) NOT NULL DEFAULT 'low',
                    notification_payload JSON NOT NULL DEFAULT '{}',
                    started_at DATETIME NULL,
                    completed_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY(watchlist_id) REFERENCES research_watchlists (id) ON DELETE SET NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_research_watchlist_runs_user_created ON research_watchlist_runs (user_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_research_watchlist_runs_watchlist_created ON research_watchlist_runs (watchlist_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_research_watchlist_runs_run_id ON research_watchlist_runs (run_id)",
            ]
        )
    if not _table_exists(engine, "research_experiment_plans"):
        statements.extend(
            [
                """
                CREATE TABLE research_experiment_plans (
                    id CHAR(32) NOT NULL PRIMARY KEY,
                    user_id CHAR(32) NOT NULL,
                    name VARCHAR(160) NOT NULL,
                    lane_key VARCHAR(60) NOT NULL,
                    strategy_family VARCHAR(40) NOT NULL,
                    candidate_label VARCHAR(180) NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    strategy_payload JSON NOT NULL DEFAULT '{}',
                    gate_config_payload JSON NOT NULL DEFAULT '{}',
                    cohort_payload JSON NOT NULL DEFAULT '{}',
                    baseline_payload JSON NOT NULL DEFAULT '{}',
                    latest_gate_payload JSON NOT NULL DEFAULT '{}',
                    gate_history_payload JSON NOT NULL DEFAULT '[]',
                    rollout_payload JSON NOT NULL DEFAULT '{}',
                    status VARCHAR(32) NOT NULL DEFAULT 'draft',
                    cohort_frozen_at DATETIME NULL,
                    baseline_locked_at DATETIME NULL,
                    last_gate_evaluated_at DATETIME NULL,
                    promoted_at DATETIME NULL,
                    rollout_revoked_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_research_experiment_plans_user_updated_at ON research_experiment_plans (user_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_research_experiment_plans_lane_status ON research_experiment_plans (lane_key, status)",
            ]
        )
    if _table_exists(engine, "research_experiment_plans") and not _table_has_column(
        engine, "research_experiment_plans", "gate_history_payload"
    ):
        statements.append(
            "ALTER TABLE research_experiment_plans ADD COLUMN gate_history_payload JSON NOT NULL DEFAULT '[]'"
        )
    if _table_exists(engine, "research_experiment_plans") and not _table_has_column(
        engine, "research_experiment_plans", "rollout_payload"
    ):
        statements.append(
            "ALTER TABLE research_experiment_plans ADD COLUMN rollout_payload JSON NOT NULL DEFAULT '{}'"
        )
    if _table_exists(engine, "research_experiment_plans") and not _table_has_column(
        engine, "research_experiment_plans", "promoted_at"
    ):
        statements.append("ALTER TABLE research_experiment_plans ADD COLUMN promoted_at DATETIME NULL")
    if _table_exists(engine, "research_experiment_plans") and not _table_has_column(
        engine, "research_experiment_plans", "rollout_revoked_at"
    ):
        statements.append("ALTER TABLE research_experiment_plans ADD COLUMN rollout_revoked_at DATETIME NULL")

    evidence_tables = {
        "collector_source_items",
        "collector_raw_assets",
        "collector_document_revisions",
        "collector_source_spans",
        "collector_transform_receipts",
    }
    if _table_exists(engine, "items") and all(
        _table_exists(engine, table_name) for table_name in evidence_tables
    ):
        # Base.metadata.create_all() is the local demo bootstrap path. Install
        # the same ownership, pointer, and erasure guards as Alembic 0041 so a
        # demo database cannot bypass the evidence-chain contract.
        statements.extend(
            [
                """
                CREATE TRIGGER IF NOT EXISTS af_collector_source_items_tenant_insert
                BEFORE INSERT ON collector_source_items
                WHEN NEW.item_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM items
                    WHERE id = NEW.item_id AND user_id = NEW.user_id
                )
                BEGIN
                    SELECT RAISE(ABORT, 'Collector source item crosses user ownership');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS af_collector_source_items_tenant_update
                BEFORE UPDATE OF user_id, item_id ON collector_source_items
                WHEN NEW.item_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM items
                    WHERE id = NEW.item_id AND user_id = NEW.user_id
                )
                BEGIN
                    SELECT RAISE(ABORT, 'Collector source item crosses user ownership');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS af_collector_source_items_rebind_update
                BEFORE UPDATE OF user_id, item_id ON collector_source_items
                WHEN (
                    NEW.user_id IS NOT OLD.user_id
                    OR NEW.item_id IS NOT OLD.item_id
                ) AND EXISTS (
                    SELECT 1 FROM collector_document_revisions
                    WHERE source_item_id = OLD.id
                )
                BEGIN
                    SELECT RAISE(ABORT, 'Collector source item with revisions cannot be rebound');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS af_collector_source_items_pointer_insert
                BEFORE INSERT ON collector_source_items
                WHEN NEW.current_revision_key IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM collector_document_revisions
                    WHERE source_item_id = NEW.id
                      AND revision_key = NEW.current_revision_key
                )
                BEGIN
                    SELECT RAISE(ABORT, 'Collector current revision does not belong to source item');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS af_collector_source_items_pointer_update
                BEFORE UPDATE OF current_revision_key ON collector_source_items
                WHEN NEW.current_revision_key IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM collector_document_revisions
                    WHERE source_item_id = NEW.id
                      AND revision_key = NEW.current_revision_key
                )
                BEGIN
                    SELECT RAISE(ABORT, 'Collector current revision does not belong to source item');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS af_collector_document_revisions_tenant_insert
                BEFORE INSERT ON collector_document_revisions
                WHEN NOT EXISTS (
                    SELECT 1
                    FROM collector_source_items AS source
                    JOIN collector_raw_assets AS raw
                      ON raw.id = NEW.raw_asset_id AND raw.user_id = source.user_id
                    LEFT JOIN items AS item ON item.id = NEW.item_id
                    WHERE source.id = NEW.source_item_id
                      AND (
                        (NEW.item_id IS NULL AND source.item_id IS NULL)
                        OR (
                          NEW.item_id IS NOT NULL
                          AND source.item_id = NEW.item_id
                          AND item.user_id = source.user_id
                        )
                      )
                )
                BEGIN
                    SELECT RAISE(ABORT, 'Collector revision crosses user ownership');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS af_collector_transform_receipts_tenant_insert
                BEFORE INSERT ON collector_transform_receipts
                WHEN NOT EXISTS (
                    SELECT 1
                    FROM collector_document_revisions AS revision
                    JOIN collector_source_items AS source ON source.id = revision.source_item_id
                    JOIN items AS item ON item.id = NEW.item_id
                    WHERE revision.id = NEW.revision_id
                      AND revision.item_id = NEW.item_id
                      AND source.user_id = NEW.user_id
                      AND item.user_id = NEW.user_id
                )
                BEGIN
                    SELECT RAISE(ABORT, 'Collector receipt crosses user ownership');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS af_items_collector_owner_update
                BEFORE UPDATE OF user_id ON items
                WHEN NEW.user_id IS NOT OLD.user_id AND (
                    EXISTS (
                        SELECT 1 FROM collector_source_items
                        WHERE item_id = OLD.id
                    )
                    OR EXISTS (
                        SELECT 1 FROM collector_document_revisions
                        WHERE item_id = OLD.id
                    )
                    OR EXISTS (
                        SELECT 1 FROM collector_transform_receipts
                        WHERE item_id = OLD.id
                    )
                )
                BEGIN
                    SELECT RAISE(ABORT, 'Item with collector evidence cannot change ownership');
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS af_collector_revision_pointer_cleanup
                AFTER DELETE ON collector_document_revisions
                BEGIN
                    UPDATE collector_source_items
                    SET current_revision_key = NULL
                    WHERE id = OLD.source_item_id
                      AND current_revision_key = OLD.revision_key;
                END
                """,
            ]
        )

    # Local demo startup uses Base.metadata.create_all() instead of Alembic. Keep
    # the immutable-while-retained evidence contract identical in that path.
    # DELETE remains available for explicit parent-row privacy erasure.
    immutable_evidence_tables = (
        ("collector_raw_assets", "af_collector_raw_assets"),
        ("collector_document_revisions", "af_collector_document_revisions"),
        ("collector_source_spans", "af_collector_source_spans"),
        ("collector_transform_receipts", "af_collector_transform_receipts"),
    )
    for table_name, trigger_prefix in immutable_evidence_tables:
        if not _table_exists(engine, table_name):
            continue
        statements.append(
            f"CREATE TRIGGER IF NOT EXISTS {trigger_prefix}_no_update "
            f"BEFORE UPDATE ON {table_name} BEGIN "
            "SELECT RAISE(ABORT, 'Collector evidence is immutable while retained'); END"
        )

    privacy_text_surfaces = (
        (
            "items",
            ("source_url", "resolved_from_url"),
            (
                "raw_content",
                "clean_content",
                "processing_error",
                "content_acquisition_note",
            ),
        ),
        ("collector_ingest_attempts", ("source_url",), ("error_detail",)),
        ("collector_sources", ("source_url",), ("last_error",)),
        ("collector_feed_sources", ("source_url",), ("last_error",)),
        ("collector_feed_entries", ("source_url",), ()),
        ("session_export_items", ("source_url_snapshot",), ()),
        ("session_export_artifacts", (), ("markdown",)),
        ("daily_brief_snapshots", (), ("audio_script",)),
    )
    privacy_json_surfaces = (
        ("collector_feed_entries", "raw_payload"),
        ("collector_import_batches", "result_payload"),
        ("collector_import_batches", "source_payload"),
        ("daily_brief_snapshots", "items_payload"),
    )
    existing_privacy_tables = {
        table_name
        for table_name, *_rest in privacy_text_surfaces
        if _table_exists(engine, table_name)
    } | {
        table_name
        for table_name, _column_name in privacy_json_surfaces
        if _table_exists(engine, table_name)
    }
    if not statements and not existing_privacy_tables:
        return

    with engine.begin() as conn:
        for statement in statements:
            conn.exec_driver_sql(statement)
        for table_name, url_columns, text_columns in privacy_text_surfaces:
            if table_name in existing_privacy_tables:
                _scrub_sqlite_text_table(
                    conn,
                    table_name=table_name,
                    url_columns=url_columns,
                    text_columns=text_columns,
                )
        for table_name, column_name in privacy_json_surfaces:
            if table_name in existing_privacy_tables:
                _scrub_sqlite_json_column(
                    conn,
                    table_name=table_name,
                    column_name=column_name,
                )
