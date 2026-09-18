#!/usr/bin/env python3
"""Run a loopback-only diagnostic API with a separate DB and no background work.

Uses real product routes and catalog initialization, not mocked HTTP responses.
The catalog and all later samples remain local diagnostics, never customer proof.
"""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="output/iteration-runtime-20260909")
    parser.add_argument("--port", type=int, default=8018)
    args = parser.parse_args()
    directory = Path(args.output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / ".local-diagnostics-only"
    database = directory / "diagnostics.sqlite"
    if database.exists() and not marker.exists():
        parser.error("Refusing to reuse a database not created by this diagnostic runner.")
    marker.write_text("local_catalog_diagnostics; customer_acceptance=false; paid_model_calls=false\n")
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{database}", "LLM_PROVIDER": "mock", "STRATEGY_LLM_PROVIDER": "mock",
        "WECHAT_AGENT_AUTO_START": "false", "RESEARCH_JOB_WORKER_ENABLED": "false",
        "PENDING_ITEM_RECOVERY_ENABLED": "false", "GATEWAY_USAGE_METER_ENABLED": "false",
    })
    sys.path.insert(0, str(ROOT / "backend"))
    from app.main import app
    from app.db.base import Base
    from app.db.session import engine, SessionLocal
    from app.services.product_strategy import office_evidence_service, visual_evidence_service
    from app.services.product_strategy.context_packet_service import initialize_decision_context_packets
    from app.services.product_strategy.artifact_acceptance_service import initialize_artifact_acceptance
    from app.services.product_strategy.iteration_program_service import initialize_iteration_program
    import uvicorn

    storage = directory / "storage" / "product-strategy"
    office_evidence_service.OFFICE_EVIDENCE_STORAGE_ROOT = storage / "office-evidence"
    visual_evidence_service.VISUAL_EVIDENCE_STORAGE_ROOT = storage / "visual-evidence"
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        initialize_decision_context_packets(db)
        initialize_artifact_acceptance(db)
        initialize_iteration_program(db)
    print("Local diagnostic API: separate SQLite, catalog data, no paid models or background workers.", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
