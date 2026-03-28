from __future__ import annotations

from app.services.workbuddy_adapter import (
    compute_workbuddy_signature,
    verify_workbuddy_signature,
)


def test_verify_workbuddy_signature_plain_ok() -> None:
    secret = "test_secret"
    raw_body = b'{"event_type":"ping"}'
    signature = compute_workbuddy_signature(secret, raw_body)

    result = verify_workbuddy_signature(
        secret=secret,
        raw_body=raw_body,
        signature=f"sha256={signature}",
        timestamp=None,
    )
    assert result.ok is True
    assert result.reason in {"ok_plain", "ok_timestamped"}


def test_verify_workbuddy_signature_timestamped_ok() -> None:
    secret = "test_secret"
    raw_body = b'{"event_type":"create_task"}'
    timestamp = "2000000000"
    signature = compute_workbuddy_signature(secret, raw_body, timestamp=timestamp)

    result = verify_workbuddy_signature(
        secret=secret,
        raw_body=raw_body,
        signature=signature,
        timestamp=timestamp,
        max_age_seconds=10**10,
    )
    assert result.ok is True


def test_verify_workbuddy_signature_mismatch() -> None:
    result = verify_workbuddy_signature(
        secret="test_secret",
        raw_body=b'{"k":"v"}',
        signature="deadbeef",
        timestamp=None,
    )
    assert result.ok is False
    assert result.reason == "signature_mismatch"


def test_verify_workbuddy_signature_bypass_when_no_secret() -> None:
    result = verify_workbuddy_signature(
        secret=None,
        raw_body=b"{}",
        signature=None,
        timestamp=None,
    )
    assert result.ok is True
    assert result.reason == "signature_bypassed_no_secret"

