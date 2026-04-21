from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import User


settings = get_settings()


def ensure_demo_user(db: Session) -> User:
    user = db.get(User, settings.single_user_id)
    if user:
        return user

    user = User(
        id=settings.single_user_id,
        name="Demo User",
        email="demo@anti-fomo.local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

