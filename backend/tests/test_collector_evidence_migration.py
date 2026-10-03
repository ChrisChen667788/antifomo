from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.core import config as app_config
from app.db.base import Base
from app.models.collector_evidence_entities import (
    CollectorDocumentRevision,
    CollectorRawAsset,
    CollectorSourceItem,
    CollectorTransformReceipt,
)
from app.models.entities import Item, User
from app.services.collector_evidence_service import record_source_capture


def _migration_config(backend: Path) -> Config:
    alembic = Config(str(backend / "alembic.ini"))
    alembic.set_main_option("script_location", str(backend / "alembic"))
    return alembic


@pytest.mark.parametrize("precreate_metadata", [False, True])
def test_0041_creates_or_adopts_schema_and_makes_evidence_append_only(
    tmp_path: Path,
    monkeypatch,
    precreate_metadata: bool,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "collector-evidence.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    alembic = _migration_config(backend)

    command.upgrade(alembic, "20261001_0040")
    engine = create_engine(url)
    if precreate_metadata:
        Base.metadata.create_all(engine)
    command.upgrade(alembic, "head")

    inspector = inspect(engine)
    expected_tables = {
        "collector_source_items",
        "collector_raw_assets",
        "collector_document_revisions",
        "collector_source_spans",
        "collector_transform_receipts",
    }
    assert expected_tables <= set(inspector.get_table_names())
    expected_foreign_key_counts = {
        "collector_source_items": 2,
        "collector_raw_assets": 1,
        "collector_document_revisions": 3,
        "collector_source_spans": 1,
        "collector_transform_receipts": 3,
    }
    expected_unique_columns = {
        "collector_source_items": {("user_id", "connector", "account_scope", "native_item_id")},
        "collector_raw_assets": {("user_id", "sha256")},
        "collector_document_revisions": {("source_item_id", "revision_key")},
        "collector_source_spans": {("revision_id", "span_key")},
        "collector_transform_receipts": {
            ("user_id", "revision_id", "stage", "input_hash", "stage_fingerprint", "output_hash")
        },
    }
    for table_name, count in expected_foreign_key_counts.items():
        foreign_keys = inspector.get_foreign_keys(table_name)
        assert len(foreign_keys) == count
        assert all((foreign_key.get("options") or {}).get("ondelete") == "CASCADE" for foreign_key in foreign_keys)
        assert {
            tuple(unique.get("column_names") or [])
            for unique in inspector.get_unique_constraints(table_name)
        } == expected_unique_columns[table_name]
    item_columns = {column["name"] for column in inspector.get_columns("items")}
    assert {
        "key_points",
        "content_score_reasons",
        "content_density",
        "novelty_level",
        "llm_receipts",
        "processing_degraded",
    } <= item_columns

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        user_id = "00000000000000000000000000000001"
        asset_id = "00000000000000000000000000000002"
        connection.execute(
            text(
                "INSERT INTO users (id, name, created_at) "
                "VALUES (:id, 'migration-user', CURRENT_TIMESTAMP)"
            ),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO collector_raw_assets "
                "(id, user_id, sha256, mime_type, byte_size, raw_text, metadata_payload) "
                "VALUES (:id, :user_id, :sha, 'text/plain', 3, 'raw', '{}')"
            ),
            {"id": asset_id, "user_id": user_id, "sha": "a" * 64},
        )

    with pytest.raises(DatabaseError):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE collector_raw_assets SET raw_text = 'changed' WHERE id = :id"),
                {"id": asset_id},
            )

    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20261003_0041"
        assert connection.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        trigger_names = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                    "AND name LIKE 'af_collector_%_no_update'"
                )
            )
        }
    assert len(trigger_names) == 4

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        assert connection.execute(
            text("SELECT count(*) FROM collector_raw_assets WHERE user_id = :id"),
            {"id": user_id},
        ).scalar_one() == 0
    engine.dispose()

def test_0041_fresh_alembic_database_supports_default_user_orm_roundtrip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "fresh-orm.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    command.upgrade(_migration_config(backend), "head")

    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    now = datetime.now(timezone.utc)
    default_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    with Session(engine) as db:
        user = User(id=default_user_id, name="migration-orm-user", created_at=now)
        item = Item(
            user_id=default_user_id,
            source_type="url",
            source_url="https://mp.weixin.qq.com/s/orm-roundtrip",
            raw_content="正文",
            ingest_route="wechat_favorites",
            status="pending",
            created_at=now,
        )
        db.add_all([user, item])
        db.flush()
        capture = record_source_capture(
            db,
            item=item,
            connector="wechat_favorites_history",
            raw_content="raw evidence",
            clean_content="clean evidence",
        )
        item_id = item.id
        raw_asset_id = capture.raw_asset.id
        db.commit()

    with Session(engine) as db:
        reloaded_user = db.get(User, default_user_id)
        reloaded_item = db.get(Item, item_id)
        reloaded_asset = db.scalar(select(CollectorRawAsset).where(CollectorRawAsset.id == raw_asset_id))
        assert reloaded_user is not None
        assert reloaded_item is not None
        assert reloaded_item.user_id == default_user_id
        assert reloaded_asset is not None
        assert reloaded_asset.user_id == default_user_id

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []
    engine.dispose()


def test_0041_scrubs_fetch_only_values_from_legacy_wechat_item_urls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "legacy-wechat-url.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    alembic = _migration_config(backend)
    command.upgrade(alembic, "20261001_0040")

    engine = create_engine(url)
    user_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    item_id = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    attempt_id = "cccccccccccccccccccccccccccccccc"
    legacy_url = (
        "HTTPS://reader:password@MP.WEIXIN.QQ.COM.:443/s/?sn=stable&idx=1&mid=7&"
        "__biz=MzLegacy&scene=21&pass_ticket=migration-secret&key=temporary"
        "#wechat_redirect"
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, name, created_at) "
                "VALUES (:id, 'legacy-url-user', CURRENT_TIMESTAMP)"
            ),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO items "
                "(id, user_id, source_type, source_url, resolved_from_url, raw_content, "
                "clean_content, status, "
                "processing_error, content_acquisition_note, created_at) "
                "VALUES (:id, :user_id, 'url', :source_url, :resolved_from_url, "
                ":raw_content, :clean_content, 'ready', :error_detail, :error_detail, "
                "CURRENT_TIMESTAMP)"
            ),
            {
                "id": item_id,
                "user_id": user_id,
                "source_url": legacy_url,
                "resolved_from_url": legacy_url,
                "raw_content": f"legacy link: {legacy_url}",
                "clean_content": f"clean link: {legacy_url}",
                "error_detail": f"fetch failed for {legacy_url}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO collector_ingest_attempts "
                "(id, user_id, item_id, source_url, source_type, route_type, resolver, "
                "attempt_status, error_detail, created_at) VALUES "
                "(:id, :user_id, :item_id, :source_url, 'url', 'direct_url', 'legacy', "
                "'failed', :error_detail, CURRENT_TIMESTAMP)"
            ),
            {
                "id": attempt_id,
                "user_id": user_id,
                "item_id": item_id,
                "source_url": legacy_url,
                "error_detail": f"attempt failed for {legacy_url}",
            },
        )
    engine.dispose()

    command.upgrade(alembic, "head")
    # A repeated upgrade is a no-op and must leave the scrubbed identity stable.
    command.upgrade(alembic, "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        source_url, resolved_from_url = connection.execute(
            text(
                "SELECT source_url, resolved_from_url FROM items WHERE id = :id"
            ),
            {"id": item_id},
        ).one()
        assert source_url == (
            "https://mp.weixin.qq.com/s?__biz=MzLegacy&mid=7&idx=1&sn=stable"
        )
        assert resolved_from_url == source_url
        assert "pass_ticket" not in source_url
        assert "migration-secret" not in resolved_from_url
        assert "key=temporary" not in source_url
        processing_error, content_note = connection.execute(
            text(
                "SELECT processing_error, content_acquisition_note FROM items WHERE id = :id"
            ),
            {"id": item_id},
        ).one()
        raw_content, clean_content = connection.execute(
            text("SELECT raw_content, clean_content FROM items WHERE id = :id"),
            {"id": item_id},
        ).one()
        attempt_url, attempt_error = connection.execute(
            text(
                "SELECT source_url, error_detail FROM collector_ingest_attempts WHERE id = :id"
            ),
            {"id": attempt_id},
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
            assert "migration-secret" not in persisted_value
            assert "key=temporary" not in persisted_value
        assert connection.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []
    engine.dispose()


def test_0041_matches_char_parent_affinity_for_base_created_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "base-created.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    default_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    with Session(engine) as db:
        user = User(id=default_user_id, name="base-user", created_at=now)
        item = Item(
            user_id=default_user_id,
            source_type="text",
            raw_content="base body",
            status="pending",
            created_at=now,
        )
        db.add_all([user, item])
        db.commit()
        item_id = item.id
    engine.dispose()

    command.stamp(_migration_config(backend), "20261001_0040")
    command.upgrade(_migration_config(backend), "head")

    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    with Session(engine) as db:
        item = db.get(Item, item_id)
        assert item is not None
        capture = record_source_capture(
            db,
            item=item,
            connector="manual",
            raw_content="base raw evidence",
            clean_content="base clean evidence",
        )
        db.commit()
        db.expire_all()
        assert db.get(CollectorRawAsset, capture.raw_asset.id).user_id == default_user_id

    with engine.connect() as connection:
        raw_user_type = next(
            row[2]
            for row in connection.exec_driver_sql("PRAGMA table_info('collector_raw_assets')")
            if row[1] == "user_id"
        )
        assert str(raw_user_type).upper() == "CHAR(32)"
        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []
    engine.dispose()


def test_0041_refuses_to_cast_populated_precreated_evidence_tables(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "populated-precreated.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    alembic = _migration_config(backend)
    command.upgrade(alembic, "20261001_0040")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    user_id = "a0000000000000000000000000000001"
    asset_id = "b0000000000000000000000000000002"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, name, created_at) VALUES (:id, 'existing', CURRENT_TIMESTAMP)"),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO collector_raw_assets "
                "(id, user_id, sha256, mime_type, byte_size, raw_text, metadata_payload) "
                "VALUES (:id, :user_id, :sha, 'text/plain', 8, 'evidence', '{}')"
            ),
            {"id": asset_id, "user_id": user_id, "sha": "f" * 64},
        )
    engine.dispose()

    with pytest.raises(RuntimeError, match="will not replace or coerce"):
        command.upgrade(_migration_config(backend), "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20261001_0040"
        row = connection.execute(
            text("SELECT id, user_id, raw_text FROM collector_raw_assets")
        ).one()
        assert tuple(row) == (asset_id, user_id, "evidence")
        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []
    engine.dispose()


def test_0041_rebuilds_empty_precreated_schema_with_missing_column(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "missing-empty-column.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE collector_transform_receipts DROP COLUMN usage_payload")
    engine.dispose()

    command.stamp(_migration_config(backend), "20261001_0040")
    command.upgrade(_migration_config(backend), "head")

    engine = create_engine(url)
    inspector = inspect(engine)
    assert "usage_payload" in {
        column["name"] for column in inspector.get_columns("collector_transform_receipts")
    }
    assert len(inspector.get_foreign_keys("collector_transform_receipts")) == 3
    engine.dispose()


def test_0041_refuses_populated_schema_with_missing_column(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "missing-populated-column.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    user_id = "a0000000000000000000000000000001"
    asset_id = "b0000000000000000000000000000002"
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE collector_transform_receipts DROP COLUMN usage_payload")
        connection.execute(
            text("INSERT INTO users (id, name, created_at) VALUES (:id, 'existing', CURRENT_TIMESTAMP)"),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO collector_raw_assets "
                "(id, user_id, sha256, mime_type, byte_size, raw_text, metadata_payload) "
                "VALUES (:id, :user_id, :sha, 'text/plain', 8, 'evidence', '{}')"
            ),
            {"id": asset_id, "user_id": user_id, "sha": "e" * 64},
        )
    engine.dispose()
    command.stamp(_migration_config(backend), "20261001_0040")

    with pytest.raises(RuntimeError, match="populated pre-migration collector evidence tables"):
        command.upgrade(_migration_config(backend), "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT raw_text FROM collector_raw_assets")).scalar_one() == "evidence"
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20261001_0040"
    engine.dispose()


def test_0041_downgrade_and_reupgrade_retains_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "retain-on-downgrade.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    alembic = _migration_config(backend)
    command.upgrade(alembic, "head")
    engine = create_engine(url)
    user_id = "00000000000000000000000000000001"
    asset_id = "00000000000000000000000000000002"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, name, created_at) VALUES (:id, 'retained', CURRENT_TIMESTAMP)"),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO collector_raw_assets "
                "(id, user_id, sha256, mime_type, byte_size, raw_text, metadata_payload) "
                "VALUES (:id, :user_id, :sha, 'text/plain', 9, 'keep this', '{}')"
            ),
            {"id": asset_id, "user_id": user_id, "sha": "d" * 64},
        )
    engine.dispose()

    command.downgrade(alembic, "20261001_0040")
    command.upgrade(alembic, "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, user_id, raw_text FROM collector_raw_assets WHERE id = :id"),
            {"id": asset_id},
        ).one()
        assert row.id == asset_id
        assert row.raw_text == "keep this"
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20261003_0041"
        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []
    with Session(engine) as db:
        retained = db.get(CollectorRawAsset, uuid.UUID(asset_id))
        assert retained is not None
        assert retained.user_id == uuid.UUID(user_id)
    engine.dispose()


def test_0041_enforces_evidence_tenant_lineage_and_repairs_deleted_revision_pointer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "tenant-lineage.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    command.upgrade(_migration_config(backend), "head")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    now = datetime.now(timezone.utc)
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    with Session(engine) as db:
        user_a = User(id=user_a_id, name="tenant-a", created_at=now)
        user_b = User(id=user_b_id, name="tenant-b", created_at=now)
        item_a = Item(user_id=user_a_id, source_type="text", raw_content="a", status="pending", created_at=now)
        item_a_sibling = Item(
            user_id=user_a_id,
            source_type="text",
            raw_content="a-sibling",
            status="pending",
            created_at=now,
        )
        item_b = Item(user_id=user_b_id, source_type="text", raw_content="b", status="pending", created_at=now)
        db.add_all([user_a, user_b, item_a, item_a_sibling, item_b])
        db.flush()
        capture_a = record_source_capture(
            db,
            item=item_a,
            connector="manual",
            raw_content="tenant a raw",
            clean_content="tenant a clean",
        )
        capture_b = record_source_capture(
            db,
            item=item_b,
            connector="manual",
            raw_content="tenant b raw",
            clean_content="tenant b clean",
        )
        item_a_id = item_a.id
        item_a_sibling_id = item_a_sibling.id
        item_b_id = item_b.id
        source_a_id = capture_a.source_item.id
        raw_a_id = capture_a.raw_asset.id
        raw_b_id = capture_b.raw_asset.id
        revision_a_id = capture_a.revision.id
        revision_b_key = capture_b.revision.revision_key
        db.commit()

    with Session(engine) as db, pytest.raises(DatabaseError, match="crosses user ownership"):
        db.add(
            CollectorSourceItem(
                user_id=user_a_id,
                item_id=item_b_id,
                connector="manual",
                account_scope="cross-tenant",
                native_item_id="bad-source",
            )
        )
        db.flush()

    with engine.begin() as connection, pytest.raises(DatabaseError, match="cannot be rebound"):
        connection.execute(
            text("UPDATE collector_source_items SET item_id = :item_id WHERE id = :source_id"),
            {"item_id": item_a_sibling_id.hex, "source_id": source_a_id.hex},
        )

    with engine.begin() as connection, pytest.raises(DatabaseError, match="does not belong"):
        connection.execute(
            text(
                "UPDATE collector_source_items SET current_revision_key = :revision_key "
                "WHERE id = :source_id"
            ),
            {"revision_key": revision_b_key, "source_id": source_a_id.hex},
        )

    with engine.begin() as connection, pytest.raises(DatabaseError, match="cannot change ownership"):
        connection.execute(
            text("UPDATE items SET user_id = :user_id WHERE id = :item_id"),
            {"user_id": user_b_id.hex, "item_id": item_a_id.hex},
        )

    with Session(engine) as db, pytest.raises(DatabaseError, match="crosses user ownership"):
        db.add(
            CollectorDocumentRevision(
                source_item_id=source_a_id,
                raw_asset_id=raw_b_id,
                item_id=item_a_id,
                revision_key="c" * 64,
                normalized_sha256="d" * 64,
                parser_fingerprint="e" * 64,
                parse_status="captured",
            )
        )
        db.flush()

    with Session(engine) as db, pytest.raises(DatabaseError, match="crosses user ownership"):
        db.add(
            CollectorTransformReceipt(
                user_id=user_b_id,
                revision_id=revision_a_id,
                item_id=item_a_id,
                stage="summary",
                input_hash="1" * 64,
                stage_fingerprint="2" * 64,
                output_hash="3" * 64,
                status="success",
            )
        )
        db.flush()

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.execute(
            text("DELETE FROM collector_raw_assets WHERE id = :id"),
            {"id": raw_a_id.hex},
        )
        assert connection.execute(
            text("SELECT count(*) FROM collector_document_revisions WHERE id = :id"),
            {"id": revision_a_id.hex},
        ).scalar_one() == 0
        assert connection.execute(
            text("SELECT current_revision_key FROM collector_source_items WHERE id = :id"),
            {"id": source_a_id.hex},
        ).scalar_one() is None
        assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []
    engine.dispose()


@pytest.mark.parametrize(
    ("violation", "error_label"),
    [
        ("revision_lineage", "revision lineage"),
        ("current_pointer", "current revision pointer"),
    ],
)
def test_0041_refuses_to_adopt_compatible_tables_with_invalid_existing_lineage(
    tmp_path: Path,
    monkeypatch,
    violation: str,
    error_label: str,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / f"invalid-existing-{violation}.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    alembic = _migration_config(backend)
    # Create the exact 0041 schema, downgrade the writer version while
    # retaining evidence, then emulate a legacy writer that had no guards.
    command.upgrade(alembic, "head")
    command.downgrade(alembic, "20261001_0040")
    engine = create_engine(url)

    user_a_id = "a0000000000000000000000000000001"
    user_b_id = "b0000000000000000000000000000002"
    item_a_id = "c0000000000000000000000000000003"
    source_id = "d0000000000000000000000000000004"
    raw_id = "e0000000000000000000000000000005"
    revision_id = "f0000000000000000000000000000006"
    revision_key = "9" * 64
    with engine.begin() as connection:
        trigger_names = [
            row[0]
            for row in connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                    "AND (name LIKE 'af_collector_%' OR name = 'af_items_collector_owner_update')"
                )
            )
        ]
        for trigger_name in trigger_names:
            connection.exec_driver_sql(f'DROP TRIGGER "{trigger_name}"')
        connection.execute(
            text(
                "INSERT INTO users (id, name, created_at) VALUES "
                "(:user_a, 'tenant-a', CURRENT_TIMESTAMP), "
                "(:user_b, 'tenant-b', CURRENT_TIMESTAMP)"
            ),
            {"user_a": user_a_id, "user_b": user_b_id},
        )
        connection.execute(
            text(
                "INSERT INTO items "
                "(id, user_id, source_type, raw_content, status, created_at) "
                "VALUES (:id, :user_id, 'text', 'body', 'pending', CURRENT_TIMESTAMP)"
            ),
            {"id": item_a_id, "user_id": user_a_id},
        )
        connection.execute(
            text(
                "INSERT INTO collector_source_items "
                "(id, user_id, item_id, connector, native_item_id, current_revision_key, metadata_payload) "
                "VALUES (:id, :user_id, :item_id, 'manual', 'existing-source', :pointer, '{}')"
            ),
            {
                "id": source_id,
                "user_id": user_a_id,
                "item_id": item_a_id,
                "pointer": revision_key if violation == "current_pointer" else None,
            },
        )
        if violation == "revision_lineage":
            connection.execute(
                text(
                    "INSERT INTO collector_raw_assets "
                    "(id, user_id, sha256, mime_type, byte_size, raw_text, metadata_payload) "
                    "VALUES (:id, :user_id, :sha, 'text/plain', 3, 'raw', '{}')"
                ),
                {"id": raw_id, "user_id": user_b_id, "sha": "8" * 64},
            )
            connection.execute(
                text(
                    "INSERT INTO collector_document_revisions "
                    "(id, source_item_id, raw_asset_id, item_id, revision_key, normalized_sha256, "
                    "parser_fingerprint, diagnostics_payload) "
                    "VALUES (:id, :source_id, :raw_id, :item_id, :revision_key, :normalized, :parser, '{}')"
                ),
                {
                    "id": revision_id,
                    "source_id": source_id,
                    "raw_id": raw_id,
                    "item_id": item_a_id,
                    "revision_key": revision_key,
                    "normalized": "7" * 64,
                    "parser": "6" * 64,
                },
            )
    engine.dispose()

    with pytest.raises(RuntimeError, match=error_label):
        command.upgrade(_migration_config(backend), "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20261001_0040"
        assert connection.execute(text("SELECT count(*) FROM collector_source_items")).scalar_one() == 1
    engine.dispose()
