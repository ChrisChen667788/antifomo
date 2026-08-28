from __future__ import annotations

import json

from app.services.workbuddy_adapter import (
    compute_workbuddy_signature,
    run_codebuddy_prompt,
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


def test_codebuddy_execution_pins_and_reports_model(monkeypatch) -> None:
    captured: list[str] = []

    class _Completed:
        returncode = 0
        stdout = json.dumps(
            [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "done"}],
                    "providerData": {"model": "glm-5.2"},
                },
                {"type": "result", "subtype": "success", "result": "done"},
            ]
        )
        stderr = ""

    monkeypatch.setattr("app.services.workbuddy_adapter._resolve_codebuddy_executable", lambda _command: "/bin/codebuddy")

    def fake_run(command, **_kwargs):
        captured.extend(command)
        return _Completed()

    monkeypatch.setattr("app.services.workbuddy_adapter.subprocess.run", fake_run)
    result = run_codebuddy_prompt("summarize", model="glm-5.2")

    assert captured[captured.index("--model") + 1] == "glm-5.2"
    assert captured[captured.index("--output-format") + 1] == "json"
    assert result.requested_model == "glm-5.2"
    assert result.effective_model == "glm-5.2"
    assert result.output == "done"


def test_codebuddy_execution_does_not_invent_effective_model(monkeypatch) -> None:
    class _Completed:
        returncode = 0
        stdout = "not-json"
        stderr = ""

    monkeypatch.setattr("app.services.workbuddy_adapter._resolve_codebuddy_executable", lambda _command: "/bin/codebuddy")
    monkeypatch.setattr("app.services.workbuddy_adapter.subprocess.run", lambda *_args, **_kwargs: _Completed())

    result = run_codebuddy_prompt("summarize", model="glm-5.2")

    assert result.requested_model == "glm-5.2"
    assert result.effective_model is None
