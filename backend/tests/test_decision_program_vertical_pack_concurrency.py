from __future__ import annotations

import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.decision_program.verticals import VERTICAL_PACKS, seed_vertical_packs


def test_concurrent_vertical_pack_seed_reloads_winning_transaction(tmp_path, monkeypatch) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'vertical-pack-race.db'}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)

    with session_factory() as losing_session:
        original_commit = losing_session.commit
        injected = False

        def commit_after_competing_seed() -> None:
            nonlocal injected
            if injected:
                original_commit()
                return
            injected = True
            with session_factory() as winning_session:
                seed_vertical_packs(winning_session)
            raise IntegrityError(
                "INSERT INTO decision_vertical_packs",
                {},
                sqlite3.IntegrityError(
                    "UNIQUE constraint failed: decision_vertical_packs.pack_key, decision_vertical_packs.version"
                ),
            )

        monkeypatch.setattr(losing_session, "commit", commit_after_competing_seed)
        rows = seed_vertical_packs(losing_session)

    assert [row.pack_key for row in rows] == [definition["pack_key"] for definition in VERTICAL_PACKS]
    assert all(row.version == "1.0.0" for row in rows)
    assert all(row.status == "validation_pending" for row in rows)
    engine.dispose()
