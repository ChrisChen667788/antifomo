#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.schemas.decision_studio import ValidationRunRequest  # noqa: E402
from app.services.decision_studio.validation import (  # noqa: E402
    build_release_program_snapshot,
    build_validation_audit_export,
    preview_validation_run,
    record_validation_run,
    run_local_reliability_probe,
    serialize_validation_run,
    validation_specs_payload,
)
from app.services.user_context import ensure_demo_user  # noqa: E402


def _write_or_print(payload: dict[str, Any], output: Path | None) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
    if output is None:
        print(encoded, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8")
    print(output)


def _load_request(path: Path) -> ValidationRunRequest:
    return ValidationRunRequest.model_validate_json(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Operate the immutable Decision Studio 2.0.1-2.0.6 validation program.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    specs_parser = subparsers.add_parser("specs", help="Print milestone and suite contracts.")
    specs_parser.add_argument("--output", type=Path)
    for command in ("preview", "record"):
        command_parser = subparsers.add_parser(command, help=f"{command.title()} a validation input JSON.")
        command_parser.add_argument("--input", type=Path, required=True)
        command_parser.add_argument("--output", type=Path)
    release_parser = subparsers.add_parser("release", help="Aggregate latest immutable runs.")
    release_parser.add_argument("--output", type=Path)
    audit_parser = subparsers.add_parser("audit", help="Export the tamper-evident validation chain.")
    audit_parser.add_argument("--limit", type=int, default=1000)
    audit_parser.add_argument("--output", type=Path)
    probe_parser = subparsers.add_parser("probe", help="Run non-destructive local 2.0.6 reliability checks.")
    probe_parser.add_argument("--audit-limit", type=int, default=1000)
    probe_parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.command == "specs":
        _write_or_print(validation_specs_payload(), args.output)
        return 0

    settings = get_settings()
    with SessionLocal() as db:
        user = ensure_demo_user(db)
        if user.id != settings.single_user_id:
            raise RuntimeError("Demo user identity does not match SINGLE_USER_ID.")
        if args.command in {"preview", "record"}:
            request = _load_request(args.input)
            values = request.model_dump()
            if args.command == "preview":
                payload = preview_validation_run(user_id=user.id, **values)
            else:
                payload = serialize_validation_run(record_validation_run(db, user_id=user.id, **values))
            _write_or_print(payload, args.output)
            return 0 if payload["status"] == "pass" else 1
        if args.command == "release":
            payload = build_release_program_snapshot(db, user_id=user.id)
            _write_or_print(payload, args.output)
            return 0 if payload["overall_status"] == "pass" else 1
        if args.command == "audit":
            payload = build_validation_audit_export(db, user_id=user.id, limit=args.limit)
            _write_or_print(payload, args.output)
            return 0 if payload["chain_valid"] else 1
        payload = run_local_reliability_probe(db, user_id=user.id, audit_sample_limit=args.audit_limit)
        _write_or_print(payload, args.output)
        return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
