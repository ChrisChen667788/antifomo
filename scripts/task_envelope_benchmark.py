#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, event, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.models.entities import User, WorkTask  # noqa: E402
from app.models.task_envelope_entities import TaskEnvelope, TaskReceipt  # noqa: E402
from app.schemas.task_envelopes import TaskBudget, TaskEnvelopeCreateRequest  # noqa: E402
from app.services.task_envelope_service import create_envelope  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synthetic local SQLite Task Envelope acceptance benchmark.")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--max-p95-ms", type=float, default=2000)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.max_p95_ms <= 0:
        parser.error("requests, concurrency and max-p95-ms must be positive")
    return args


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def percentile_95(values: list[float]) -> float:
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[94]


def main() -> int:
    args = parse_args()
    user_id = uuid4()
    with tempfile.TemporaryDirectory(prefix="anti-fomo-task-envelope-benchmark-") as temp_dir:
        database_path = Path(temp_dir) / "benchmark.sqlite"
        engine = create_engine(
            f"sqlite+pysqlite:///{database_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection, _record):  # type: ignore[no-untyped-def]
            dbapi_connection.execute("PRAGMA journal_mode=WAL")
            dbapi_connection.execute("PRAGMA busy_timeout=30000")

        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(User(id=user_id, name="Synthetic benchmark user"))
            db.commit()

        def submit(index: int) -> tuple[float, str]:
            request = TaskEnvelopeCreateRequest(
                request_id=f"benchmark-request-{index}",
                mode="plan",
                capability_key="benchmark.read-only",
                context_digest=digest(f"context:{index}"),
                plan_digest=digest(f"plan:{index}"),
                content_digest=digest(f"content:{index}"),
                effects_digest=digest(f"effects:{index}"),
                budget=TaskBudget(max_tokens=1024, max_runtime_seconds=30),
                required_scopes=["task:read"],
                deadline=datetime.now(UTC) + timedelta(hours=1),
                idempotency_key=f"benchmark:{index}",
                request_payload={"case": index, "synthetic": True},
            )
            started = time.perf_counter()
            with Session(engine) as db:
                outcome = create_envelope(db, user_id=user_id, request=request)["outcome"]
            return (time.perf_counter() - started) * 1000, outcome

        started = time.perf_counter()
        durations: list[float] = []
        outcomes: list[str] = []
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [pool.submit(submit, index) for index in range(args.requests)]
            for future in as_completed(futures):
                try:
                    duration, outcome = future.result()
                    durations.append(duration)
                    outcomes.append(outcome)
                except Exception as error:  # pragma: no cover - benchmark reporting path
                    errors.append(f"{type(error).__name__}: {error}")
        elapsed = time.perf_counter() - started

        with Session(engine) as db:
            envelope_count = db.scalar(select(func.count()).select_from(TaskEnvelope)) or 0
            receipt_count = db.scalar(select(func.count()).select_from(TaskReceipt)) or 0
            work_task_count = db.scalar(select(func.count()).select_from(WorkTask)) or 0
        engine.dispose()

    p95_ms = percentile_95(durations) if durations else float("inf")
    passed = (
        not errors
        and len(durations) == args.requests
        and outcomes.count("created") == args.requests
        and envelope_count == args.requests
        and receipt_count == args.requests
        and work_task_count == 0
        and p95_ms <= args.max_p95_ms
    )
    report = {
        "schema_version": "anti-fomo-task-envelope-benchmark/v1",
        "evidence_tier": "synthetic_benchmark",
        "database": "temporary_local_sqlite",
        "requests": args.requests,
        "concurrency": args.concurrency,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_requests_per_second": round(args.requests / elapsed, 2),
        "latency_ms": {
            "min": round(min(durations), 3) if durations else None,
            "median": round(statistics.median(durations), 3) if durations else None,
            "p95": round(p95_ms, 3) if durations else None,
            "max": round(max(durations), 3) if durations else None,
            "budget_p95": args.max_p95_ms,
        },
        "counts": {
            "created": outcomes.count("created"),
            "envelopes": envelope_count,
            "receipts": receipt_count,
            "legacy_work_tasks": work_task_count,
            "errors": len(errors),
        },
        "error_samples": errors[:5],
        "status": "passed" if passed else "failed",
        "claim_boundary": "Local synthetic acceptance only; not production throughput or SLA evidence.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
