from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import create_engine

from app.db.types import CompatibleUuid


def test_compatible_uuid_restores_exact_legacy_sqlite_numeric_values() -> None:
    dialect = create_engine("sqlite+pysqlite:///:memory:").dialect
    processor = CompatibleUuid(as_uuid=True).result_processor(dialect, None)
    assert processor is not None

    assert processor(1) == UUID("00000000-0000-0000-0000-000000000001")
    assert processor(Decimal("12345678901234567890123456789012")) == UUID(
        "12345678-9012-3456-7890-123456789012"
    )


@pytest.mark.parametrize(
    "value",
    [Decimal("1.5"), Decimal("NaN"), Decimal("1E+32"), -1, 1.0],
)
def test_compatible_uuid_rejects_inexact_or_out_of_range_numeric_values(value) -> None:
    dialect = create_engine("sqlite+pysqlite:///:memory:").dialect
    processor = CompatibleUuid(as_uuid=True).result_processor(dialect, None)
    assert processor is not None

    with pytest.raises(ValueError, match="Legacy SQLite"):
        processor(value)
