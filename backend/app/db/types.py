from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Uuid as SQLAlchemyUuid


class CompatibleUuid(SQLAlchemyUuid):
    """Read both portable CHAR UUIDs and legacy SQLite UUID/NUMERIC values."""

    cache_ok = True

    def result_processor(self, dialect, coltype):
        default_processor = super().result_processor(dialect, coltype)
        if default_processor is None:
            return None

        def process(value):
            if dialect.name == "sqlite" and isinstance(value, int) and not isinstance(value, bool):
                # SQLite interpreted a 32-character digits-only UUID as a base-10
                # integer. Re-pad the original decimal text; UUID(int=value)
                # would incorrectly reinterpret it as hexadecimal.
                if value < 0 or value >= 10**32:
                    raise ValueError("Legacy SQLite integer UUID is outside the 32-digit UUID range")
                return UUID(f"{value:032d}")
            if dialect.name == "sqlite" and isinstance(value, Decimal):
                if (
                    not value.is_finite()
                    or value != value.to_integral_value()
                    or value < 0
                    or value >= Decimal(10**32)
                ):
                    raise ValueError("Legacy SQLite decimal UUID is not an exact 32-digit identifier")
                return UUID(f"{int(value):032d}")
            if dialect.name == "sqlite" and isinstance(value, float):
                raise ValueError(
                    "Legacy SQLite UUID was stored as an inexact floating-point value; "
                    "the original identifier cannot be recovered safely"
                )
            return default_processor(value)

        return process
