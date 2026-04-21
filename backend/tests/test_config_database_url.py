from pathlib import Path

from app.core.config import _normalize_sqlite_database_url


def test_relative_sqlite_database_url_resolves_to_backend_dir() -> None:
    normalized = _normalize_sqlite_database_url("sqlite:///./anti_fomo_demo.db")

    expected = Path(__file__).resolve().parents[1] / "anti_fomo_demo.db"
    assert normalized == f"sqlite:///{expected}"


def test_absolute_sqlite_database_url_stays_unchanged() -> None:
    value = "sqlite:////tmp/demo.db"
    assert _normalize_sqlite_database_url(value) == value
