"""Add collector source, revision, span and transform evidence.

Revision ID: 20261003_0041
Revises: 20261001_0040

The migration is expand-only. Evidence rows are immutable while retained, but
privacy erasure remains possible through parent-row delete cascades. Rollback
disables writers while retaining evidence, so downgrade does not drop tables.
"""

import json
import re
from urllib import parse as urllib_parse

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20261003_0041"
down_revision = "20261001_0040"
branch_labels = None
depends_on = None

_LEGACY_HTTP_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", flags=re.IGNORECASE)
_LEGACY_TRAILING_URL_PUNCTUATION_PATTERN = re.compile(r"[),.;，。；）】》]+$")


def _uuid_type():
    return sa.Uuid(as_uuid=True)


def _parent_uuid_type(table_name: str):
    """Match the actual referenced parent affinity on the current database."""

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        for column in sa.inspect(bind).get_columns(table_name):
            if column["name"] == "id":
                return column["type"]
        raise RuntimeError(f"Cannot resolve {table_name}.id type for collector evidence migration")
    return postgresql.UUID(as_uuid=True)


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def _canonicalize_legacy_wechat_url(value: str | None) -> str | None:
    """Scrub historical WeChat session parameters without changing other URLs."""

    if value is None:
        return None
    raw = str(value).strip()
    try:
        parsed = urllib_parse.urlsplit(raw)
        hostname = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return value
    try:
        port = parsed.port
    except ValueError:
        # A malformed legacy port must not preserve a signed query forever.
        # The hostname is still unambiguous, so discard the unusable port.
        port = None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or hostname != "mp.weixin.qq.com":
        return value

    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    values_by_key: dict[str, list[str]] = {
        key: [] for key in ("__biz", "mid", "idx", "sn", "chksm")
    }
    for key, item in urllib_parse.parse_qsl(parsed.query, keep_blank_values=True):
        if key in values_by_key:
            values_by_key[key].append(item)
    stable_query = urllib_parse.urlencode(
        [
            (key, item)
            for key in ("__biz", "mid", "idx", "sn", "chksm")
            for item in sorted(values_by_key[key])
        ],
        doseq=True,
    )
    return urllib_parse.urlunsplit(
        parsed._replace(
            scheme=scheme,
            netloc=netloc,
            path=path,
            query=stable_query,
            fragment="",
        )
    )


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


def _scrub_legacy_payload(value):
    if isinstance(value, str):
        return _redact_legacy_wechat_urls(value)
    if isinstance(value, list):
        return [_scrub_legacy_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _scrub_legacy_payload(item) for key, item in value.items()}
    return value


def _later_value(left, right):
    if left is None:
        return right
    if right is None:
        return left
    try:
        return max(left, right)
    except TypeError:
        return left if str(left) >= str(right) else right


def _earlier_value(left, right):
    if left is None:
        return right
    if right is None:
        return left
    try:
        return min(left, right)
    except TypeError:
        return left if str(left) <= str(right) else right


def _merge_collector_source_duplicate(bind, row, canonical_url: str) -> bool:
    duplicate = bind.execute(
        sa.text(
            "SELECT id, note, enabled, last_collected_at, last_error, created_at, updated_at "
            "FROM collector_sources "
            "WHERE user_id = :user_id AND source_url = :source_url AND id <> :row_id "
            "LIMIT 1"
        ),
        {
            "user_id": row["user_id"],
            "source_url": canonical_url,
            "row_id": row["id"],
        },
    ).mappings().first()
    if duplicate is None:
        return False

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
    newest_collection = _later_value(
        duplicate["last_collected_at"], row["last_collected_at"]
    )
    merged_error = (
        incoming_error
        if newest_collection == row["last_collected_at"] and incoming_error is not None
        else duplicate_error or incoming_error
    )
    bind.execute(
        sa.text(
            "UPDATE collector_sources SET note = :note, enabled = :enabled, "
            "last_collected_at = :last_collected_at, last_error = :last_error, "
            "created_at = :created_at, updated_at = :updated_at WHERE id = :target_id"
        ),
        {
            "note": duplicate["note"] or row["note"],
            "enabled": bool(duplicate["enabled"]) or bool(row["enabled"]),
            "last_collected_at": newest_collection,
            "last_error": merged_error,
            "created_at": _earlier_value(duplicate["created_at"], row["created_at"]),
            "updated_at": _later_value(duplicate["updated_at"], row["updated_at"]),
            "target_id": duplicate["id"],
        },
    )
    bind.execute(
        sa.text("DELETE FROM collector_sources WHERE id = :row_id"),
        {"row_id": row["id"]},
    )
    return True


def _scrub_legacy_text_table(
    bind,
    *,
    table_name: str,
    url_columns: tuple[str, ...] = (),
    text_columns: tuple[str, ...] = (),
) -> None:
    tables = set(sa.inspect(bind).get_table_names())
    if table_name not in tables:
        return
    existing = _column_names(table_name)
    transforms = {
        **{name: _canonicalize_legacy_wechat_url for name in url_columns if name in existing},
        **{name: _redact_legacy_wechat_urls for name in text_columns if name in existing},
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
        f"lower(CAST({name} AS TEXT)) LIKE :wechat_host" for name in transforms
    )
    rows = list(
        bind.execute(
            sa.text(f"SELECT {selected} FROM {table_name} WHERE {predicates}"),
            {"wechat_host": "%mp.weixin.qq.com%"},
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
            and _merge_collector_source_duplicate(bind, row, updates["source_url"])
        ):
            continue
        assignments = ", ".join(f"{name} = :{name}" for name in updates)
        bind.execute(
            sa.text(f"UPDATE {table_name} SET {assignments} WHERE id = :row_id"),
            {**updates, "row_id": row["id"]},
        )


def _scrub_legacy_json_column(bind, *, table_name: str, column_name: str) -> None:
    tables = set(sa.inspect(bind).get_table_names())
    if table_name not in tables or column_name not in _column_names(table_name):
        return
    rows = list(
        bind.execute(
            sa.text(
                f"SELECT id, {column_name} FROM {table_name} "
                f"WHERE lower(CAST({column_name} AS TEXT)) LIKE :wechat_host"
            ),
            {"wechat_host": "%mp.weixin.qq.com%"},
        ).mappings()
    )
    update_statement = sa.text(
        f"UPDATE {table_name} SET {column_name} = :payload WHERE id = :row_id"
    ).bindparams(sa.bindparam("payload", type_=sa.JSON()))
    for row in rows:
        original = row[column_name]
        decoded = original
        if isinstance(original, str):
            try:
                decoded = json.loads(original)
            except (TypeError, ValueError):
                decoded = original
        scrubbed = _scrub_legacy_payload(decoded)
        if scrubbed != decoded:
            bind.execute(update_statement, {"payload": scrubbed, "row_id": row["id"]})


def _scrub_legacy_wechat_metadata(bind) -> None:
    """Remove historical fetch credentials from URL and diagnostic surfaces."""

    text_surfaces = (
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
    for table_name, url_columns, text_columns in text_surfaces:
        _scrub_legacy_text_table(
            bind,
            table_name=table_name,
            url_columns=url_columns,
            text_columns=text_columns,
        )
    for table_name, column_name in (
        ("collector_feed_entries", "raw_payload"),
        ("collector_import_batches", "result_payload"),
        ("collector_import_batches", "source_payload"),
        ("daily_brief_snapshots", "items_payload"),
    ):
        _scrub_legacy_json_column(bind, table_name=table_name, column_name=column_name)


def _compiled_type(type_: sa.types.TypeEngine, bind) -> str:
    return re.sub(r"\s+", " ", str(type_.compile(dialect=bind.dialect)).strip().upper())


def _normalized_default(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    # PostgreSQL reflection includes casts such as 'local'::character varying.
    text = re.sub(r"::[a-z_ ]+(?:\[\])?", "", text)
    while text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    if text in {"current_timestamp", "current_timestamp()", "now()"}:
        return "now"
    if len(text) >= 2 and text[0] == text[-1] == "'":
        text = text[1:-1].replace("''", "'")
    return text


def _evidence_schema_specs(bind) -> dict[str, dict]:
    internal_uuid = _compiled_type(_uuid_type(), bind)
    user_uuid = _compiled_type(_parent_uuid_type("users"), bind)
    item_uuid = _compiled_type(_parent_uuid_type("items"), bind)
    varchar = lambda length: _compiled_type(sa.String(length), bind)
    text_type = _compiled_type(sa.Text(), bind)
    integer = _compiled_type(sa.Integer(), bind)
    json_type = _compiled_type(sa.JSON(), bind)
    datetime_type = _compiled_type(sa.DateTime(timezone=True), bind)

    def column(type_name: str, nullable: bool, default: str | None = None) -> tuple[str, bool, str | None]:
        return type_name, nullable, default

    return {
        "collector_source_items": {
            "columns": {
                "id": column(internal_uuid, False),
                "user_id": column(user_uuid, False),
                "item_id": column(item_uuid, True),
                "connector": column(varchar(80), False),
                "account_scope": column(varchar(160), False, "local"),
                "native_item_id": column(varchar(512), False),
                "native_version": column(varchar(255), True),
                "canonical_url": column(text_type, True),
                "state": column(varchar(30), False, "active"),
                "current_revision_key": column(varchar(64), True),
                "metadata_payload": column(json_type, False, "{}"),
                "first_seen_at": column(datetime_type, False, "now"),
                "last_seen_at": column(datetime_type, False, "now"),
                "tombstoned_at": column(datetime_type, True),
            },
            "foreign_keys": {
                (("user_id",), "users", ("id",), "CASCADE"),
                (("item_id",), "items", ("id",), "CASCADE"),
            },
            "uniques": {("user_id", "connector", "account_scope", "native_item_id")},
        },
        "collector_raw_assets": {
            "columns": {
                "id": column(internal_uuid, False),
                "user_id": column(user_uuid, False),
                "sha256": column(varchar(64), False),
                "mime_type": column(varchar(120), False, "text/plain"),
                "byte_size": column(integer, False),
                "storage_uri": column(text_type, True),
                "raw_text": column(text_type, True),
                "metadata_payload": column(json_type, False, "{}"),
                "created_at": column(datetime_type, False, "now"),
            },
            "foreign_keys": {(("user_id",), "users", ("id",), "CASCADE")},
            "uniques": {("user_id", "sha256")},
        },
        "collector_document_revisions": {
            "columns": {
                "id": column(internal_uuid, False),
                "source_item_id": column(internal_uuid, False),
                "raw_asset_id": column(internal_uuid, False),
                "item_id": column(item_uuid, True),
                "revision_key": column(varchar(64), False),
                "native_version": column(varchar(255), True),
                "normalized_sha256": column(varchar(64), False),
                "parser_fingerprint": column(varchar(64), False),
                "parse_status": column(varchar(30), False, "captured"),
                "diagnostics_payload": column(json_type, False, "{}"),
                "created_at": column(datetime_type, False, "now"),
            },
            "foreign_keys": {
                (("source_item_id",), "collector_source_items", ("id",), "CASCADE"),
                (("raw_asset_id",), "collector_raw_assets", ("id",), "CASCADE"),
                (("item_id",), "items", ("id",), "CASCADE"),
            },
            "uniques": {("source_item_id", "revision_key")},
        },
        "collector_source_spans": {
            "columns": {
                "id": column(internal_uuid, False),
                "revision_id": column(internal_uuid, False),
                "span_key": column(varchar(160), False),
                "kind": column(varchar(40), False, "text"),
                "text": column(text_type, False),
                "text_sha256": column(varchar(64), False),
                "page_no": column(integer, True),
                "bbox_payload": column(json_type, True),
                "dom_selector": column(text_type, True),
                "char_start": column(integer, True),
                "char_end": column(integer, True),
                "metadata_payload": column(json_type, False, "{}"),
                "created_at": column(datetime_type, False, "now"),
            },
            "foreign_keys": {
                (("revision_id",), "collector_document_revisions", ("id",), "CASCADE")
            },
            "uniques": {("revision_id", "span_key")},
        },
        "collector_transform_receipts": {
            "columns": {
                "id": column(internal_uuid, False),
                "user_id": column(user_uuid, False),
                "revision_id": column(internal_uuid, False),
                "item_id": column(item_uuid, False),
                "stage": column(varchar(80), False),
                "input_hash": column(varchar(64), False),
                "stage_fingerprint": column(varchar(64), False),
                "output_hash": column(varchar(64), False),
                "status": column(varchar(30), False),
                "provider": column(varchar(80), True),
                "model": column(varchar(160), True),
                "prompt_name": column(varchar(160), True),
                "schema_fingerprint": column(varchar(64), True),
                "usage_payload": column(json_type, False, "{}"),
                "diagnostics_payload": column(json_type, False, "{}"),
                "created_at": column(datetime_type, False, "now"),
            },
            "foreign_keys": {
                (("user_id",), "users", ("id",), "CASCADE"),
                (("revision_id",), "collector_document_revisions", ("id",), "CASCADE"),
                (("item_id",), "items", ("id",), "CASCADE"),
            },
            "uniques": {
                ("user_id", "revision_id", "stage", "input_hash", "stage_fingerprint", "output_hash")
            },
        },
    }


def _table_matches_spec(inspector, bind, table_name: str, spec: dict) -> bool:
    actual_columns = {column["name"]: column for column in inspector.get_columns(table_name)}
    if set(actual_columns) != set(spec["columns"]):
        return False
    for name, (expected_type, expected_nullable, expected_default) in spec["columns"].items():
        actual = actual_columns[name]
        if _compiled_type(actual["type"], bind) != expected_type:
            return False
        if bool(actual["nullable"]) != expected_nullable:
            return False
        if _normalized_default(actual.get("default")) != expected_default:
            return False

    primary_key = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
    if tuple(primary_key) != ("id",):
        return False

    actual_foreign_keys = {
        (
            tuple(foreign_key.get("constrained_columns") or []),
            foreign_key.get("referred_table"),
            tuple(foreign_key.get("referred_columns") or []),
            str((foreign_key.get("options") or {}).get("ondelete") or "").upper(),
        )
        for foreign_key in inspector.get_foreign_keys(table_name)
    }
    if actual_foreign_keys != spec["foreign_keys"]:
        return False

    actual_uniques = {
        tuple(unique.get("column_names") or [])
        for unique in inspector.get_unique_constraints(table_name)
        if unique.get("column_names")
    }
    return actual_uniques == spec["uniques"]


def _install_integrity_guards(bind) -> None:
    """Keep evidence ownership consistent and repair the mutable revision pointer."""

    if bind.dialect.name == "sqlite":
        trigger_statements = (
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
        )
        for statement in trigger_statements:
            op.execute(sa.text(statement))
        return

    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION af_validate_collector_source_tenant() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
              IF TG_OP = 'UPDATE'
                 AND (NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.item_id IS DISTINCT FROM OLD.item_id)
                 AND EXISTS (
                   SELECT 1 FROM collector_document_revisions WHERE source_item_id = OLD.id
                 ) THEN
                RAISE EXCEPTION 'Collector source item with revisions cannot be rebound';
              END IF;
              IF NEW.item_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM items WHERE id = NEW.item_id AND user_id = NEW.user_id
              ) THEN
                RAISE EXCEPTION 'Collector source item crosses user ownership';
              END IF;
              IF NEW.current_revision_key IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM collector_document_revisions
                WHERE source_item_id = NEW.id AND revision_key = NEW.current_revision_key
              ) THEN
                RAISE EXCEPTION 'Collector current revision does not belong to source item';
              END IF;
              RETURN NEW;
            END; $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION af_validate_collector_revision_tenant() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
              IF NOT EXISTS (
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
              ) THEN
                RAISE EXCEPTION 'Collector revision crosses user ownership';
              END IF;
              RETURN NEW;
            END; $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION af_validate_collector_receipt_tenant() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
              IF NOT EXISTS (
                SELECT 1
                FROM collector_document_revisions AS revision
                JOIN collector_source_items AS source ON source.id = revision.source_item_id
                JOIN items AS item ON item.id = NEW.item_id
                WHERE revision.id = NEW.revision_id
                  AND revision.item_id = NEW.item_id
                  AND source.user_id = NEW.user_id
                  AND item.user_id = NEW.user_id
              ) THEN
                RAISE EXCEPTION 'Collector receipt crosses user ownership';
              END IF;
              RETURN NEW;
            END; $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION af_validate_item_collector_owner() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
              IF NEW.user_id IS DISTINCT FROM OLD.user_id AND (
                EXISTS (SELECT 1 FROM collector_source_items WHERE item_id = OLD.id)
                OR EXISTS (SELECT 1 FROM collector_document_revisions WHERE item_id = OLD.id)
                OR EXISTS (SELECT 1 FROM collector_transform_receipts WHERE item_id = OLD.id)
              ) THEN
                RAISE EXCEPTION 'Item with collector evidence cannot change ownership';
              END IF;
              RETURN NEW;
            END; $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION af_cleanup_collector_revision_pointer() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
              UPDATE collector_source_items
              SET current_revision_key = NULL
              WHERE id = OLD.source_item_id AND current_revision_key = OLD.revision_key;
              RETURN OLD;
            END; $$
            """
        )
    )
    postgres_triggers = (
        (
            "af_collector_source_items_tenant",
            "collector_source_items",
            "BEFORE INSERT OR UPDATE OF user_id, item_id, current_revision_key",
            "af_validate_collector_source_tenant()",
        ),
        (
            "af_items_collector_owner",
            "items",
            "BEFORE UPDATE OF user_id",
            "af_validate_item_collector_owner()",
        ),
        (
            "af_collector_document_revisions_tenant",
            "collector_document_revisions",
            "BEFORE INSERT",
            "af_validate_collector_revision_tenant()",
        ),
        (
            "af_collector_transform_receipts_tenant",
            "collector_transform_receipts",
            "BEFORE INSERT",
            "af_validate_collector_receipt_tenant()",
        ),
        (
            "af_collector_revision_pointer_cleanup",
            "collector_document_revisions",
            "AFTER DELETE",
            "af_cleanup_collector_revision_pointer()",
        ),
    )
    for trigger_name, table_name, timing, function_name in postgres_triggers:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"))
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger_name} {timing} ON {table_name} "
                f"FOR EACH ROW EXECUTE FUNCTION {function_name}"
            )
        )


def _audit_existing_evidence_lineage(bind) -> None:
    """Reject compatible pre-created tables whose rows violate 0041 invariants."""

    checks = (
        (
            "source ownership",
            """
            SELECT source.id
            FROM collector_source_items AS source
            LEFT JOIN users AS source_user ON source_user.id = source.user_id
            LEFT JOIN items AS item ON item.id = source.item_id
            WHERE source_user.id IS NULL
               OR (
                 source.item_id IS NOT NULL
                 AND (item.id IS NULL OR item.user_id <> source.user_id)
               )
            LIMIT 1
            """,
        ),
        (
            "raw asset ownership",
            """
            SELECT raw.id
            FROM collector_raw_assets AS raw
            LEFT JOIN users AS raw_user ON raw_user.id = raw.user_id
            WHERE raw_user.id IS NULL
            LIMIT 1
            """,
        ),
        (
            "revision lineage",
            """
            SELECT revision.id
            FROM collector_document_revisions AS revision
            LEFT JOIN collector_source_items AS source
              ON source.id = revision.source_item_id
            LEFT JOIN collector_raw_assets AS raw
              ON raw.id = revision.raw_asset_id
            LEFT JOIN items AS item ON item.id = revision.item_id
            WHERE source.id IS NULL
               OR raw.id IS NULL
               OR raw.user_id <> source.user_id
               OR (
                 revision.item_id IS NULL
                 AND source.item_id IS NOT NULL
               )
               OR (
                 revision.item_id IS NOT NULL
                 AND (
                   source.item_id IS NULL
                   OR source.item_id <> revision.item_id
                   OR item.id IS NULL
                   OR item.user_id <> source.user_id
                 )
               )
            LIMIT 1
            """,
        ),
        (
            "source span lineage",
            """
            SELECT span.id
            FROM collector_source_spans AS span
            LEFT JOIN collector_document_revisions AS revision
              ON revision.id = span.revision_id
            WHERE revision.id IS NULL
            LIMIT 1
            """,
        ),
        (
            "transform receipt lineage",
            """
            SELECT receipt.id
            FROM collector_transform_receipts AS receipt
            LEFT JOIN users AS receipt_user ON receipt_user.id = receipt.user_id
            LEFT JOIN collector_document_revisions AS revision
              ON revision.id = receipt.revision_id
            LEFT JOIN collector_source_items AS source
              ON source.id = revision.source_item_id
            LEFT JOIN items AS item ON item.id = receipt.item_id
            WHERE receipt_user.id IS NULL
               OR revision.id IS NULL
               OR source.id IS NULL
               OR item.id IS NULL
               OR revision.item_id IS NULL
               OR revision.item_id <> receipt.item_id
               OR source.item_id IS NULL
               OR source.item_id <> receipt.item_id
               OR source.user_id <> receipt.user_id
               OR item.user_id <> receipt.user_id
            LIMIT 1
            """,
        ),
        (
            "current revision pointer",
            """
            SELECT source.id
            FROM collector_source_items AS source
            WHERE source.current_revision_key IS NOT NULL
              AND NOT EXISTS (
                SELECT 1
                FROM collector_document_revisions AS revision
                WHERE revision.source_item_id = source.id
                  AND revision.revision_key = source.current_revision_key
              )
            LIMIT 1
            """,
        ),
    )
    for label, query in checks:
        invalid_id = bind.execute(sa.text(query)).scalar()
        if invalid_id is not None:
            raise RuntimeError(
                "Revision 0041 found incompatible collector evidence lineage "
                f"({label}, row {invalid_id}). Repair or remove the invalid rows before upgrading."
            )


def _prepare_preexisting_evidence_tables() -> None:
    """Adopt compatible 0041 tables or replace empty create_all placeholders.

    Revision 0041 is the first migration that owns these tables. A development
    startup may have precreated tables from ORM metadata, and an expand-only
    downgrade intentionally retains 0041 data. Compatible tables are adopted
    in place. An incompatible populated schema is refused so no identifier can
    be changed by an affinity cast.
    """

    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    evidence_tables = (
        "collector_transform_receipts",
        "collector_source_spans",
        "collector_document_revisions",
        "collector_raw_assets",
        "collector_source_items",
    )
    existing = [table_name for table_name in evidence_tables if table_name in tables]
    if not existing:
        return
    if bind.dialect.name == "postgresql":
        # The compatibility check and a possible empty-table rebuild must be
        # atomic with respect to first writers. These names are migration
        # constants, not user input.
        lock_tables = ["users", "items", *existing]
        op.execute(sa.text("LOCK TABLE " + ", ".join(lock_tables) + " IN ACCESS EXCLUSIVE MODE"))
    compatible = len(existing) == len(evidence_tables)
    inspector = sa.inspect(bind)
    if compatible:
        specs = _evidence_schema_specs(bind)
        compatible = all(
            _table_matches_spec(inspector, bind, table_name, specs[table_name])
            for table_name in evidence_tables
        )
    if compatible:
        _audit_existing_evidence_lineage(bind)
        return

    nonempty = [
        table_name
        for table_name in existing
        if int(bind.exec_driver_sql(f'SELECT count(*) FROM "{table_name}"').scalar_one()) > 0
    ]
    if nonempty:
        raise RuntimeError(
            "Revision 0041 found populated pre-migration collector evidence tables "
            f"({', '.join(nonempty)}). Export or back up those rows before upgrading; "
            "the migration will not replace or coerce an incompatible populated schema."
        )
    for table_name in evidence_tables:
        if table_name in tables:
            op.drop_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    _prepare_preexisting_evidence_tables()
    user_id_type = _parent_uuid_type("users")
    item_id_type = _parent_uuid_type("items")
    tables = set(sa.inspect(bind).get_table_names())

    if "items" in tables:
        existing_columns = _column_names("items")
        additions = (
            sa.Column("key_points", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("content_score_reasons", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("content_density", sa.String(20), nullable=True),
            sa.Column("novelty_level", sa.String(20), nullable=True),
            sa.Column("llm_receipts", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("processing_degraded", sa.Boolean(), server_default="0", nullable=False),
        )
        for column in additions:
            if column.name not in existing_columns:
                op.add_column("items", column)
        _scrub_legacy_wechat_metadata(bind)

    tables = set(sa.inspect(bind).get_table_names())
    if "collector_source_items" not in tables:
        op.create_table(
            "collector_source_items",
            sa.Column("id", _uuid_type(), nullable=False),
            sa.Column("user_id", user_id_type, nullable=False),
            sa.Column("item_id", item_id_type, nullable=True),
            sa.Column("connector", sa.String(80), nullable=False),
            sa.Column("account_scope", sa.String(160), server_default="local", nullable=False),
            sa.Column("native_item_id", sa.String(512), nullable=False),
            sa.Column("native_version", sa.String(255), nullable=True),
            sa.Column("canonical_url", sa.Text(), nullable=True),
            sa.Column("state", sa.String(30), server_default="active", nullable=False),
            sa.Column("current_revision_key", sa.String(64), nullable=True),
            sa.Column("metadata_payload", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "connector",
                "account_scope",
                "native_item_id",
                name="uq_collector_source_items_native_identity",
            ),
        )
    _create_index_if_missing("collector_source_items", "idx_collector_source_items_user_seen", ["user_id", "last_seen_at"])
    _create_index_if_missing("collector_source_items", "idx_collector_source_items_item", ["item_id"])
    _create_index_if_missing("collector_source_items", "idx_collector_source_items_state", ["state"])

    tables = set(sa.inspect(bind).get_table_names())
    if "collector_raw_assets" not in tables:
        op.create_table(
            "collector_raw_assets",
            sa.Column("id", _uuid_type(), nullable=False),
            sa.Column("user_id", user_id_type, nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("mime_type", sa.String(120), server_default="text/plain", nullable=False),
            sa.Column("byte_size", sa.Integer(), nullable=False),
            sa.Column("storage_uri", sa.Text(), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=True),
            sa.Column("metadata_payload", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "sha256", name="uq_collector_raw_assets_user_sha256"),
        )
    _create_index_if_missing("collector_raw_assets", "idx_collector_raw_assets_user_created", ["user_id", "created_at"])

    tables = set(sa.inspect(bind).get_table_names())
    if "collector_document_revisions" not in tables:
        op.create_table(
            "collector_document_revisions",
            sa.Column("id", _uuid_type(), nullable=False),
            sa.Column("source_item_id", _uuid_type(), nullable=False),
            sa.Column("raw_asset_id", _uuid_type(), nullable=False),
            sa.Column("item_id", item_id_type, nullable=True),
            sa.Column("revision_key", sa.String(64), nullable=False),
            sa.Column("native_version", sa.String(255), nullable=True),
            sa.Column("normalized_sha256", sa.String(64), nullable=False),
            sa.Column("parser_fingerprint", sa.String(64), nullable=False),
            sa.Column("parse_status", sa.String(30), server_default="captured", nullable=False),
            sa.Column("diagnostics_payload", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["source_item_id"], ["collector_source_items.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["raw_asset_id"], ["collector_raw_assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_item_id", "revision_key", name="uq_collector_document_revisions_key"),
        )
    _create_index_if_missing(
        "collector_document_revisions",
        "idx_collector_document_revisions_source_created",
        ["source_item_id", "created_at"],
    )
    _create_index_if_missing("collector_document_revisions", "idx_collector_document_revisions_item", ["item_id"])

    tables = set(sa.inspect(bind).get_table_names())
    if "collector_source_spans" not in tables:
        op.create_table(
            "collector_source_spans",
            sa.Column("id", _uuid_type(), nullable=False),
            sa.Column("revision_id", _uuid_type(), nullable=False),
            sa.Column("span_key", sa.String(160), nullable=False),
            sa.Column("kind", sa.String(40), server_default="text", nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("text_sha256", sa.String(64), nullable=False),
            sa.Column("page_no", sa.Integer(), nullable=True),
            sa.Column("bbox_payload", sa.JSON(), nullable=True),
            sa.Column("dom_selector", sa.Text(), nullable=True),
            sa.Column("char_start", sa.Integer(), nullable=True),
            sa.Column("char_end", sa.Integer(), nullable=True),
            sa.Column("metadata_payload", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["revision_id"], ["collector_document_revisions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("revision_id", "span_key", name="uq_collector_source_spans_key"),
        )
    _create_index_if_missing("collector_source_spans", "idx_collector_source_spans_revision", ["revision_id"])
    _create_index_if_missing("collector_source_spans", "idx_collector_source_spans_text_sha", ["text_sha256"])

    tables = set(sa.inspect(bind).get_table_names())
    if "collector_transform_receipts" not in tables:
        op.create_table(
            "collector_transform_receipts",
            sa.Column("id", _uuid_type(), nullable=False),
            sa.Column("user_id", user_id_type, nullable=False),
            sa.Column("revision_id", _uuid_type(), nullable=False),
            sa.Column("item_id", item_id_type, nullable=False),
            sa.Column("stage", sa.String(80), nullable=False),
            sa.Column("input_hash", sa.String(64), nullable=False),
            sa.Column("stage_fingerprint", sa.String(64), nullable=False),
            sa.Column("output_hash", sa.String(64), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("provider", sa.String(80), nullable=True),
            sa.Column("model", sa.String(160), nullable=True),
            sa.Column("prompt_name", sa.String(160), nullable=True),
            sa.Column("schema_fingerprint", sa.String(64), nullable=True),
            sa.Column("usage_payload", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("diagnostics_payload", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["revision_id"], ["collector_document_revisions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "revision_id",
                "stage",
                "input_hash",
                "stage_fingerprint",
                "output_hash",
                name="uq_collector_transform_receipts_run",
            ),
        )
    _create_index_if_missing("collector_transform_receipts", "idx_collector_transform_receipts_revision", ["revision_id"])
    _create_index_if_missing("collector_transform_receipts", "idx_collector_transform_receipts_item", ["item_id"])
    _create_index_if_missing(
        "collector_transform_receipts",
        "idx_collector_transform_receipts_stage_status",
        ["stage", "status"],
    )

    _install_integrity_guards(bind)

    immutable_tables = (
        ("collector_raw_assets", "af_collector_raw_assets"),
        ("collector_document_revisions", "af_collector_document_revisions"),
        ("collector_source_spans", "af_collector_source_spans"),
        ("collector_transform_receipts", "af_collector_transform_receipts"),
    )
    if bind.dialect.name == "sqlite":
        for table_name, prefix in immutable_tables:
            op.execute(
                sa.text(
                    f"CREATE TRIGGER IF NOT EXISTS {prefix}_no_update "
                    f"BEFORE UPDATE ON {table_name} BEGIN "
                    "SELECT RAISE(ABORT, 'Collector evidence is immutable while retained'); END"
                )
            )
    elif bind.dialect.name == "postgresql":
        op.execute(
                sa.text(
                    "CREATE OR REPLACE FUNCTION af_reject_collector_evidence_update() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN "
                    "RAISE EXCEPTION 'Collector evidence is immutable while retained'; END; $$"
                )
            )
        for table_name, prefix in immutable_tables:
            trigger_name = f"{prefix}_immutable"
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"))
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {trigger_name} BEFORE UPDATE ON {table_name} "
                    "FOR EACH ROW EXECUTE FUNCTION af_reject_collector_evidence_update()"
                )
            )


def downgrade() -> None:
    # Retain raw, revision, span and transform evidence after a writer rollback.
    pass
