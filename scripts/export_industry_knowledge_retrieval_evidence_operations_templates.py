#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.industry_knowledge_retrieval_evidence_operations import (  # noqa: E402
    DEFAULT_HANDOFF_PATH,
    DEFAULT_INCIDENT_PATH,
    DEFAULT_REVOCATION_PATH,
    export_industry_knowledge_retrieval_evidence_operations_templates,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create only missing retrieval-evidence-operations templates; existing human records are never overwritten."
    )
    parser.add_argument("--incidents", type=Path, default=DEFAULT_INCIDENT_PATH)
    parser.add_argument("--revocation", type=Path, default=DEFAULT_REVOCATION_PATH)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF_PATH)
    args = parser.parse_args()
    try:
        output = export_industry_knowledge_retrieval_evidence_operations_templates(
            incident_path=args.incidents,
            revocation_path=args.revocation,
            handoff_path=args.handoff,
        )
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
