from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app import models  # noqa: F401
from app.core import config as app_config
from app.db.base import Base


def test_upgrade_from_0035_handles_precreated_tables_and_preserves_integrity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "upgrade.sqlite"
    url = f"sqlite:///{database_path}"
    monkeypatch.setattr(app_config, "get_settings", lambda: type("Settings", (), {"database_url": url})())
    alembic = Config(str(backend / "alembic.ini"))
    alembic.set_main_option("script_location", str(backend / "alembic"))

    command.upgrade(alembic, "20260906_0035")
    engine = create_engine(url)
    # Reproduce the real checkout's stamp/schema drift: application startup can
    # create new metadata before Alembic records its revision.
    Base.metadata.create_all(engine)
    command.upgrade(alembic, "head")

    inspector = inspect(engine)
    assert {"model_profiles", "task_envelopes", "task_approvals", "task_receipts"} <= set(
        inspector.get_table_names()
    )
    assert "uq_task_envelopes_idempotency" in {
        item["name"] for item in inspector.get_unique_constraints("task_envelopes")
    }
    assert "uq_task_receipts_envelope_sequence" in {
        item["name"] for item in inspector.get_unique_constraints("task_receipts")
    }
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20261003_0041"
        assert connection.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        assert connection.execute(text("SELECT count(*) FROM pragma_foreign_key_check")).scalar_one() == 0
        trigger_names = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                    "AND name LIKE 'af_task_%'"
                )
            )
        }
    assert {
        "af_task_envelopes_frozen_fields",
        "af_task_approvals_no_update",
        "af_task_approvals_no_delete",
        "af_task_receipts_no_update",
        "af_task_receipts_no_delete",
    } <= trigger_names
    engine.dispose()
