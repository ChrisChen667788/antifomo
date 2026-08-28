from __future__ import annotations

from typing import Any


def requires_account_truth(contract: Any) -> bool:
    """Return whether a report is making customer-specific delivery claims.

    Generic solution research remains useful as a market scan. It becomes a
    customer-facing architecture only when an explicit customer is in scope.
    """

    task_type = str(getattr(contract, "task_type", "") or "")
    if task_type == "account_intelligence":
        return True
    if task_type != "solution_research":
        return False
    return bool(getattr(contract, "clients", None))
