from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import shutil
import subprocess
import time
from urllib import error, request
from urllib.parse import urlparse


@dataclass(slots=True)
class SignatureVerifyResult:
    ok: bool
    reason: str


@dataclass(slots=True)
class CallbackDispatchResult:
    ok: bool
    status_code: int | None
    detail: str | None


@dataclass(slots=True)
class OfficialGatewayProbeResult:
    cli_detected: bool
    cli_version: str | None
    cli_authenticated: bool
    cli_auth_detail: str | None
    gateway_configured: bool
    gateway_reachable: bool
    gateway_url: str | None
    gateway_status_code: int | None
    gateway_detail: str | None


@dataclass(slots=True)
class CodeBuddyExecutionResult:
    ok: bool
    authenticated: bool
    output: str | None
    detail: str | None
    exit_code: int | None


def detect_codebuddy_cli(command: str = "codebuddy") -> tuple[bool, str | None]:
    executable = shutil.which(str(command or "").strip())
    if not executable:
        return False, None
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
    except Exception:
        return True, None
    output = (completed.stdout or completed.stderr or "").strip()
    return True, output or None


def _resolve_codebuddy_executable(command: str = "codebuddy") -> str | None:
    return shutil.which(str(command or "").strip())


def _looks_like_auth_required(text: str) -> bool:
    lowered = text.lower()
    return (
        "authentication required" in lowered
        or "please use /login" in lowered
        or "sign in to your account" in lowered
        or "login required" in lowered
    )


def probe_codebuddy_cli_auth(
    command: str = "codebuddy",
    *,
    timeout_seconds: int = 8,
) -> tuple[bool, str | None]:
    executable = _resolve_codebuddy_executable(command)
    if not executable:
        return False, "cli_not_found"
    try:
        completed = subprocess.run(
            [executable, "-p", "--output-format", "text", "Reply with OK only."],
            capture_output=True,
            text=True,
            timeout=max(5, min(int(timeout_seconds or 8), 30)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "probe_timeout"
    except Exception as exc:  # pragma: no cover - runtime path
        return False, str(exc)
    output = (completed.stdout or completed.stderr or "").strip()
    if _looks_like_auth_required(output):
        return False, output[:300] or "authentication_required"
    if completed.returncode == 0:
        return True, output[:300] or "ok"
    return False, output[:300] or f"exit_{completed.returncode}"


def _normalize_probe_candidates(base_url: str | None, health_url: str | None) -> list[str]:
    candidates: list[str] = []
    explicit_health = str(health_url or "").strip()
    if explicit_health:
        candidates.append(explicit_health.rstrip("/"))
    normalized_base = str(base_url or "").strip().rstrip("/")
    if normalized_base:
        parsed = urlparse(normalized_base)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            path = parsed.path.rstrip("/")
            if path:
                candidates.append(normalized_base)
                if not path.endswith("/health") and not path.endswith("/healthz"):
                    candidates.append(f"{normalized_base}/health")
                    candidates.append(f"{normalized_base}/healthz")
            else:
                candidates.append(f"{normalized_base}/gateway/health")
                candidates.append(f"{normalized_base}/healthz")
                candidates.append(f"{normalized_base}/health")
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = candidate.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def probe_official_gateway(
    *,
    cli_command: str = "codebuddy",
    gateway_url: str | None = None,
    gateway_health_url: str | None = None,
    bearer_token: str | None = None,
    timeout_seconds: int = 6,
) -> OfficialGatewayProbeResult:
    cli_detected, cli_version = detect_codebuddy_cli(cli_command)
    cli_authenticated = False
    cli_auth_detail: str | None = None
    if cli_detected:
        cli_authenticated, cli_auth_detail = probe_codebuddy_cli_auth(
            cli_command,
            timeout_seconds=timeout_seconds,
        )
    candidates = _normalize_probe_candidates(gateway_url, gateway_health_url)
    if not candidates:
        return OfficialGatewayProbeResult(
            cli_detected=cli_detected,
            cli_version=cli_version,
            cli_authenticated=cli_authenticated,
            cli_auth_detail=cli_auth_detail,
            gateway_configured=False,
            gateway_reachable=False,
            gateway_url=None,
            gateway_status_code=None,
            gateway_detail="gateway_url_not_configured",
        )

    last_status: int | None = None
    last_detail: str | None = None
    for candidate in candidates:
        headers = {"Accept": "application/json"}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        req = request.Request(candidate, method="GET", headers=headers)
        try:
            with request.urlopen(req, timeout=max(3, min(int(timeout_seconds or 6), 30))) as resp:
                status_code = int(getattr(resp, "status", 200))
                detail = resp.read().decode("utf-8", errors="ignore")[:300]
                if 200 <= status_code < 400:
                    return OfficialGatewayProbeResult(
                        cli_detected=cli_detected,
                        cli_version=cli_version,
                        cli_authenticated=cli_authenticated,
                        cli_auth_detail=cli_auth_detail,
                        gateway_configured=True,
                        gateway_reachable=True,
                        gateway_url=candidate,
                        gateway_status_code=status_code,
                        gateway_detail=detail or "ok",
                    )
                last_status = status_code
                last_detail = detail or "unexpected_status"
        except error.HTTPError as exc:
            last_status = exc.code
            last_detail = exc.read().decode("utf-8", errors="ignore")[:300] or str(exc)
        except Exception as exc:  # pragma: no cover - runtime/network path
            last_detail = str(exc)

    return OfficialGatewayProbeResult(
        cli_detected=cli_detected,
        cli_version=cli_version,
        cli_authenticated=cli_authenticated,
        cli_auth_detail=cli_auth_detail,
        gateway_configured=True,
        gateway_reachable=False,
        gateway_url=candidates[0],
        gateway_status_code=last_status,
        gateway_detail=last_detail or "gateway_unreachable",
    )


def run_codebuddy_prompt(
    prompt: str,
    *,
    command: str = "codebuddy",
    timeout_seconds: int = 90,
    output_format: str = "text",
) -> CodeBuddyExecutionResult:
    executable = _resolve_codebuddy_executable(command)
    if not executable:
        return CodeBuddyExecutionResult(
            ok=False,
            authenticated=False,
            output=None,
            detail="cli_not_found",
            exit_code=None,
        )
    try:
        completed = subprocess.run(
            [executable, "-p", "--output-format", output_format, str(prompt)],
            capture_output=True,
            text=True,
            timeout=max(10, min(int(timeout_seconds or 90), 600)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CodeBuddyExecutionResult(
            ok=False,
            authenticated=True,
            output=None,
            detail="execution_timeout",
            exit_code=None,
        )
    except Exception as exc:  # pragma: no cover - runtime path
        return CodeBuddyExecutionResult(
            ok=False,
            authenticated=False,
            output=None,
            detail=str(exc),
            exit_code=None,
        )
    output = (completed.stdout or completed.stderr or "").strip()
    if _looks_like_auth_required(output):
        return CodeBuddyExecutionResult(
            ok=False,
            authenticated=False,
            output=None,
            detail=output[:300] or "authentication_required",
            exit_code=completed.returncode,
        )
    if completed.returncode == 0:
        return CodeBuddyExecutionResult(
            ok=True,
            authenticated=True,
            output=output[:12000] or "",
            detail="ok",
            exit_code=0,
        )
    return CodeBuddyExecutionResult(
        ok=False,
        authenticated=True,
        output=output[:4000] or None,
        detail=output[:300] or f"exit_{completed.returncode}",
        exit_code=completed.returncode,
    )


def compute_workbuddy_signature(
    secret: str,
    raw_body: bytes,
    *,
    timestamp: str | None = None,
) -> str:
    key = secret.encode("utf-8")
    if timestamp:
        payload = timestamp.encode("utf-8") + b"." + raw_body
    else:
        payload = raw_body
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def _normalize_signature(value: str | None) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("sha256="):
        text = text.split("=", 1)[1].strip()
    return text.lower()


def verify_workbuddy_signature(
    *,
    secret: str | None,
    raw_body: bytes,
    signature: str | None,
    timestamp: str | None = None,
    max_age_seconds: int = 300,
) -> SignatureVerifyResult:
    secret_value = str(secret or "").strip()
    if not secret_value:
        return SignatureVerifyResult(ok=True, reason="signature_bypassed_no_secret")

    signature_value = _normalize_signature(signature)
    if not signature_value:
        return SignatureVerifyResult(ok=False, reason="missing_signature")

    ts = str(timestamp or "").strip()
    if ts:
        if not ts.isdigit():
            return SignatureVerifyResult(ok=False, reason="invalid_timestamp")
        now_ts = int(time.time())
        drift = abs(now_ts - int(ts))
        if drift > max(1, int(max_age_seconds)):
            return SignatureVerifyResult(ok=False, reason="stale_timestamp")

    expected_plain = compute_workbuddy_signature(secret_value, raw_body)
    if hmac.compare_digest(signature_value, expected_plain):
        return SignatureVerifyResult(ok=True, reason="ok_plain")

    if ts:
        expected_ts = compute_workbuddy_signature(secret_value, raw_body, timestamp=ts)
        if hmac.compare_digest(signature_value, expected_ts):
            return SignatureVerifyResult(ok=True, reason="ok_timestamped")

    return SignatureVerifyResult(ok=False, reason="signature_mismatch")


def dispatch_workbuddy_callback(
    *,
    callback_url: str,
    payload: dict,
    headers: dict[str, str] | None = None,
    bearer_token: str | None = None,
    timeout_seconds: int = 12,
) -> CallbackDispatchResult:
    target = str(callback_url or "").strip()
    if not target:
        return CallbackDispatchResult(ok=False, status_code=None, detail="empty_callback_url")

    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return CallbackDispatchResult(ok=False, status_code=None, detail="invalid_callback_url")

    final_headers: dict[str, str] = {"Content-Type": "application/json"}
    for key, value in (headers or {}).items():
        key_text = str(key or "").strip()
        value_text = str(value or "").strip()
        if key_text and value_text:
            final_headers[key_text] = value_text

    has_auth = any(str(key).lower() == "authorization" for key in final_headers)
    if bearer_token and not has_auth:
        final_headers["Authorization"] = f"Bearer {bearer_token}"

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=target,
        method="POST",
        headers=final_headers,
        data=body,
    )
    try:
        with request.urlopen(req, timeout=max(3, min(timeout_seconds, 120))) as resp:
            status_code = int(getattr(resp, "status", 200))
            response_body = resp.read().decode("utf-8", errors="ignore")
            return CallbackDispatchResult(ok=True, status_code=status_code, detail=response_body[:300])
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return CallbackDispatchResult(ok=False, status_code=exc.code, detail=detail[:300])
    except Exception as exc:  # pragma: no cover - network/runtime path
        return CallbackDispatchResult(ok=False, status_code=None, detail=str(exc))
