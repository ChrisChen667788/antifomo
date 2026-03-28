from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.entities import Item, User
from app.services.session_service import gather_items_in_window


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_gather_items_in_window_includes_same_second_items() -> None:
    db = _new_session()
    try:
        user = User(id=uuid.uuid4(), name="demo")
        db.add(user)
        db.flush()

        # start_time has microseconds; item created at the same second boundary.
        start_time = datetime(2026, 3, 16, 10, 15, 49, 921010, tzinfo=timezone.utc)
        item = Item(
            user_id=user.id,
            source_type="text",
            title="same-second",
            raw_content="demo",
            status="ready",
            created_at=datetime(2026, 3, 16, 10, 15, 49, tzinfo=timezone.utc),
        )
        db.add(item)
        db.commit()

        items = gather_items_in_window(
            db,
            user_id=user.id,
            start_time=start_time,
            end_time=datetime(2026, 3, 16, 10, 16, 22, 156262, tzinfo=timezone.utc),
        )
        assert len(items) == 1
        assert items[0].id == item.id
    finally:
        db.close()
