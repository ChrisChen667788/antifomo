from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_program_entities import DecisionConnectorSyncRun, EnterpriseIdentityProfile
from app.models.decision_studio_entities import KnowledgeConnector
from app.services.decision_program.common import canonical_digest, iso, utc_now


ALLOWED_IDENTITY_PROVIDERS = {"oidc", "saml", "microsoft_entra", "wecom"}
ALLOWED_ROLES = {"viewer", "reviewer", "editor", "owner"}
SENSITIVE_KEYS = {"token", "password", "secret", "api_key", "authorization", "cookie", "client_secret"}


def _contains_secret(payload: Any) -> bool:
    if isinstance(payload, dict):
        return any(str(key).lower() in SENSITIVE_KEYS or _contains_secret(value) for key, value in payload.items())
    if isinstance(payload, list):
        return any(_contains_secret(value) for value in payload)
    return False


def create_identity_profile(
    db: Session,
    *,
    space_id: UUID,
    provider_type: str,
    name: str,
    issuer_uri: str,
    client_id: str,
    tenant_key: str,
    role_mapping: dict[str, str],
    allowed_domains: list[str],
    retention_days: int,
) -> EnterpriseIdentityProfile:
    if provider_type not in ALLOWED_IDENTITY_PROVIDERS:
        raise ValueError("Unsupported enterprise identity provider.")
    parsed = urlparse(issuer_uri.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Identity issuer must be an HTTPS URI without embedded credentials.")
    invalid_roles = sorted(set(role_mapping.values()) - ALLOWED_ROLES)
    if invalid_roles:
        raise ValueError(f"Unsupported mapped roles: {', '.join(invalid_roles)}")
    normalized_domains = sorted({value.strip().lower() for value in allowed_domains if value.strip()})
    fingerprint = hashlib.sha256(client_id.strip().encode("utf-8")).hexdigest()
    existing = db.scalar(
        select(EnterpriseIdentityProfile)
        .where(EnterpriseIdentityProfile.space_id == space_id)
        .where(EnterpriseIdentityProfile.provider_type == provider_type)
        .where(EnterpriseIdentityProfile.tenant_key == tenant_key.strip())
    )
    if existing is not None:
        if existing.client_id_fingerprint != fingerprint or existing.issuer_uri != issuer_uri.strip():
            raise ValueError("Identity profile already exists; rotate it through an audited replacement workflow.")
        return existing
    now = utc_now()
    row = EnterpriseIdentityProfile(
        space_id=space_id,
        provider_type=provider_type,
        name=name.strip(),
        issuer_uri=issuer_uri.strip(),
        client_id_fingerprint=fingerprint,
        tenant_key=tenant_key.strip(),
        status="ready",
        role_mapping_payload=role_mapping,
        allowed_domains_payload=normalized_domains,
        retention_days=retention_days,
        validation_payload={
            "status": "pass",
            "https_issuer": True,
            "credentials_persisted": False,
            "role_mapping_valid": True,
        },
        last_validated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def serialize_identity_profile(row: EnterpriseIdentityProfile) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "space_id": str(row.space_id),
        "provider_type": row.provider_type,
        "name": row.name,
        "issuer_uri": row.issuer_uri,
        "client_id_fingerprint": row.client_id_fingerprint,
        "tenant_key": row.tenant_key,
        "status": row.status,
        "role_mapping": dict(row.role_mapping_payload or {}),
        "allowed_domains": list(row.allowed_domains_payload or []),
        "retention_days": row.retention_days,
        "validation": dict(row.validation_payload or {}),
        "last_validated_at": iso(row.last_validated_at),
    }


def record_connector_sync(
    db: Session,
    *,
    connector: KnowledgeConnector,
    actor_id: str,
    idempotency_key: str,
    mode: str,
    cursor_before: str,
    resources: list[dict[str, Any]],
    acl_snapshot: list[dict[str, Any]],
) -> DecisionConnectorSyncRun:
    existing = db.scalar(
        select(DecisionConnectorSyncRun)
        .where(DecisionConnectorSyncRun.connector_id == connector.id)
        .where(DecisionConnectorSyncRun.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing
    if connector.connector_type not in {"microsoft365", "sharepoint", "tencent_docs", "feishu", "notion"}:
        raise ValueError("Connector sync snapshots are available for governed knowledge connectors only.")
    if _contains_secret(resources) or _contains_secret(acl_snapshot):
        raise ValueError("Connector sync payload must not contain credentials or tokens.")
    resource_ids = [str(value.get("id") or "").strip() for value in resources]
    findings: list[str] = []
    if any(not value for value in resource_ids):
        findings.append("Every resource requires a stable id.")
    if len(resource_ids) != len(set(resource_ids)):
        findings.append("Resource ids must be unique within a sync snapshot.")
    active_resource_ids = {
        str(value.get("id") or "").strip()
        for value in resources
        if value.get("deleted") is not True
    }
    deleted_resource_ids = {
        str(value.get("id") or "").strip()
        for value in resources
        if value.get("deleted") is True
    }
    acl_resource_ids = {str(value.get("resource_id") or "").strip() for value in acl_snapshot}
    missing_acl = sorted(active_resource_ids - acl_resource_ids)
    if missing_acl:
        findings.append(f"ACL snapshot missing for {len(missing_acl)} resources.")
    if mode == "apply" and connector.status != "ready":
        findings.append("Apply mode requires a connector that passed governed dry-run.")
    cursor_after = canonical_digest({"cursor_before": cursor_before, "resource_ids": sorted(resource_ids)})
    snapshot_digest = canonical_digest(
        {
            "connector_id": str(connector.id),
            "config_fingerprint": connector.config_fingerprint,
            "resource_ids": sorted(resource_ids),
            "acl_snapshot": acl_snapshot,
            "cursor_before": cursor_before,
            "cursor_after": cursor_after,
        }
    )
    now = utc_now()
    row = DecisionConnectorSyncRun(
        connector_id=connector.id,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        mode=mode,
        status="blocked" if findings else ("previewed" if mode == "dry_run" else "applied"),
        cursor_before=cursor_before,
        cursor_after=cursor_after,
        resource_count=len(resources),
        applied_count=len(active_resource_ids) if mode == "apply" and not findings else 0,
        deleted_count=len(deleted_resource_ids) if mode == "apply" and not findings else 0,
        acl_snapshot_payload=acl_snapshot,
        findings_payload=findings,
        snapshot_digest=snapshot_digest,
        started_at=now,
        completed_at=now,
    )
    db.add(row)
    if mode == "apply" and not findings:
        connector.last_sync_at = now
    db.commit()
    db.refresh(row)
    return row


def serialize_connector_sync(row: DecisionConnectorSyncRun) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "connector_id": str(row.connector_id),
        "actor_id": row.actor_id,
        "idempotency_key": row.idempotency_key,
        "mode": row.mode,
        "status": row.status,
        "cursor_before": row.cursor_before,
        "cursor_after": row.cursor_after,
        "resource_count": row.resource_count,
        "applied_count": row.applied_count,
        "deleted_count": row.deleted_count,
        "acl_snapshot": list(row.acl_snapshot_payload or []),
        "findings": list(row.findings_payload or []),
        "snapshot_digest": row.snapshot_digest,
        "started_at": iso(row.started_at),
        "completed_at": iso(row.completed_at),
    }
