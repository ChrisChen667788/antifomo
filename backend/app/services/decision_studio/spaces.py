from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from collections.abc import Callable
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.decision_studio_entities import (
    DecisionNotebook,
    KnowledgeConnector,
    KnowledgeReviewThread,
    KnowledgeSpace,
    KnowledgeSpaceMembership,
)


ROLE_RANK = {"viewer": 10, "reviewer": 20, "editor": 30, "owner": 40}
CONNECTOR_TYPES = {
    "local_folder",
    "http",
    "mcp",
    "tencent_docs",
    "feishu",
    "notion",
    "microsoft365",
    "sharepoint",
}
FORBIDDEN_PERMISSION_PREFIXES = ("shell", "exec", "root", "credential:read", "filesystem:any")
MCP_ACTION_PERMISSIONS = {
    "list_resources": "mcp:list",
    "read_resource": "mcp:read",
    "search": "mcp:search",
}


class AccessDeniedError(PermissionError):
    pass


def create_space(
    db: Session,
    *,
    owner_user_id: UUID,
    name: str,
    description: str,
    visibility: str,
) -> KnowledgeSpace:
    if visibility not in {"private", "shared"}:
        raise ValueError("Space visibility must be private or shared.")
    space = KnowledgeSpace(
        owner_user_id=owner_user_id,
        name=name.strip()[:120],
        description=description.strip(),
        visibility=visibility,
    )
    db.add(space)
    db.flush()
    db.add(KnowledgeSpaceMembership(space_id=space.id, member_id=str(owner_user_id), role="owner"))
    db.commit()
    db.refresh(space)
    return space


def actor_role(db: Session, *, space: KnowledgeSpace, actor_id: str) -> str | None:
    if str(space.owner_user_id) == actor_id:
        return "owner"
    membership = db.scalar(
        select(KnowledgeSpaceMembership)
        .where(KnowledgeSpaceMembership.space_id == space.id)
        .where(KnowledgeSpaceMembership.member_id == actor_id)
    )
    return membership.role if membership else None


def require_space_access(
    db: Session,
    *,
    space_id: UUID,
    actor_id: str,
    minimum_role: str = "viewer",
) -> KnowledgeSpace:
    space = db.get(KnowledgeSpace, space_id)
    if space is None or space.status != "active":
        raise AccessDeniedError("Knowledge Space is unavailable.")
    role = actor_role(db, space=space, actor_id=actor_id)
    if role is None or ROLE_RANK.get(role, 0) < ROLE_RANK.get(minimum_role, 0):
        raise AccessDeniedError(f"{minimum_role} access is required.")
    return space


def require_notebook_access(
    db: Session,
    *,
    notebook_id: UUID,
    actor_id: str,
    minimum_role: str = "viewer",
) -> DecisionNotebook:
    notebook = db.get(DecisionNotebook, notebook_id)
    if notebook is None or notebook.status != "active":
        raise AccessDeniedError("Notebook is unavailable.")
    if notebook.space_id:
        require_space_access(db, space_id=notebook.space_id, actor_id=actor_id, minimum_role=minimum_role)
    elif str(notebook.user_id) != actor_id:
        raise AccessDeniedError("Private notebook access denied.")
    return notebook


def accessible_space_ids(db: Session, *, actor_id: str) -> list[UUID]:
    owned = list(db.scalars(select(KnowledgeSpace.id).where(KnowledgeSpace.owner_user_id == _actor_uuid(actor_id))).all())
    member = list(
        db.scalars(
            select(KnowledgeSpaceMembership.space_id).where(KnowledgeSpaceMembership.member_id == actor_id)
        ).all()
    )
    return list(dict.fromkeys([*owned, *member]))


def _actor_uuid(actor_id: str) -> UUID:
    try:
        return UUID(actor_id)
    except ValueError:
        return UUID(int=0)


def serialize_space(db: Session, space: KnowledgeSpace, *, actor_id: str) -> dict[str, object]:
    memberships = list(
        db.scalars(
            select(KnowledgeSpaceMembership)
            .where(KnowledgeSpaceMembership.space_id == space.id)
            .order_by(KnowledgeSpaceMembership.role.desc(), KnowledgeSpaceMembership.member_id)
        ).all()
    )
    return {
        "id": str(space.id),
        "owner_user_id": str(space.owner_user_id),
        "name": space.name,
        "description": space.description,
        "visibility": space.visibility,
        "status": space.status,
        "actor_role": actor_role(db, space=space, actor_id=actor_id),
        "members": [
            {"id": str(membership.id), "member_id": membership.member_id, "role": membership.role}
            for membership in memberships
        ],
    }


def list_accessible_spaces(db: Session, *, actor_id: str) -> list[KnowledgeSpace]:
    ids = accessible_space_ids(db, actor_id=actor_id)
    if not ids:
        return []
    return list(
        db.scalars(
            select(KnowledgeSpace)
            .where(KnowledgeSpace.id.in_(ids))
            .where(KnowledgeSpace.status == "active")
            .order_by(KnowledgeSpace.updated_at.desc())
        ).all()
    )


def upsert_membership(
    db: Session,
    *,
    space: KnowledgeSpace,
    member_id: str,
    role: str,
) -> KnowledgeSpaceMembership:
    if role not in ROLE_RANK or role == "owner":
        raise ValueError("Membership role must be viewer, reviewer, or editor.")
    if member_id == str(space.owner_user_id):
        raise ValueError("The owner role cannot be replaced through membership updates.")
    membership = db.scalar(
        select(KnowledgeSpaceMembership)
        .where(KnowledgeSpaceMembership.space_id == space.id)
        .where(KnowledgeSpaceMembership.member_id == member_id)
    )
    if membership is None:
        membership = KnowledgeSpaceMembership(space_id=space.id, member_id=member_id, role=role)
        db.add(membership)
    else:
        membership.role = role
    db.commit()
    db.refresh(membership)
    return membership


def create_review_thread(
    db: Session,
    *,
    space_id: UUID,
    target_type: str,
    target_id: str,
    actor_id: str,
    comment: str,
) -> KnowledgeReviewThread:
    thread = KnowledgeReviewThread(
        space_id=space_id,
        target_type=target_type.strip()[:40],
        target_id=target_id.strip()[:80],
        comments_payload=[
            {
                "actor_id": actor_id,
                "comment": comment.strip(),
                "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        ] if comment.strip() else [],
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def add_review_comment(db: Session, *, thread: KnowledgeReviewThread, actor_id: str, comment: str) -> KnowledgeReviewThread:
    comments = list(thread.comments_payload or [])
    comments.append(
        {
            "actor_id": actor_id,
            "comment": comment.strip(),
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
    )
    thread.comments_payload = comments
    db.commit()
    db.refresh(thread)
    return thread


def decide_review(
    db: Session,
    *,
    thread: KnowledgeReviewThread,
    actor_id: str,
    decision: str,
) -> KnowledgeReviewThread:
    if decision not in {"approved", "changes_requested", "rejected"}:
        raise ValueError("Unsupported review decision.")
    thread.decision = decision
    thread.status = "closed"
    thread.reviewer_id = actor_id
    db.commit()
    db.refresh(thread)
    return thread


def serialize_review(thread: KnowledgeReviewThread) -> dict[str, object]:
    return {
        "id": str(thread.id),
        "space_id": str(thread.space_id),
        "target_type": thread.target_type,
        "target_id": thread.target_id,
        "status": thread.status,
        "comments": list(thread.comments_payload or []),
        "decision": thread.decision,
        "reviewer_id": thread.reviewer_id,
    }


def _connector_fingerprint(connector_type: str, endpoint: str, permissions: list[str]) -> str:
    raw = json.dumps(
        {"connector_type": connector_type, "endpoint": endpoint, "permissions": sorted(permissions)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_connector(
    db: Session,
    *,
    space_id: UUID,
    name: str,
    connector_type: str,
    endpoint: str,
    permissions: list[str],
) -> KnowledgeConnector:
    if connector_type not in CONNECTOR_TYPES:
        raise ValueError("Unsupported connector type.")
    normalized_permissions = list(dict.fromkeys(value.strip() for value in permissions if value.strip()))
    connector = KnowledgeConnector(
        space_id=space_id,
        name=name.strip()[:160],
        connector_type=connector_type,
        endpoint=endpoint.strip(),
        permissions_payload=normalized_permissions,
        config_fingerprint=_connector_fingerprint(connector_type, endpoint.strip(), normalized_permissions),
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


def dry_run_connector(db: Session, *, connector: KnowledgeConnector) -> KnowledgeConnector:
    violations: list[str] = []
    endpoint = connector.endpoint.strip()
    permissions = [str(value) for value in connector.permissions_payload or []]
    if any(permission.startswith(FORBIDDEN_PERMISSION_PREFIXES) for permission in permissions):
        violations.append("Connector requests a forbidden high-risk permission.")
    if connector.connector_type == "local_folder":
        path = Path(endpoint).expanduser()
        if not path.is_absolute():
            violations.append("Local folder connector requires an absolute path.")
        if any(part == ".." for part in path.parts):
            violations.append("Local folder traversal is not allowed.")
    else:
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            violations.append("Remote connector requires an HTTP(S) endpoint.")
        if parsed.username or parsed.password:
            violations.append("Credentials must not be embedded in the connector endpoint.")
        allowed_domains = {
            value.strip().lower()
            for value in get_settings().decision_connector_allowed_domains.split(",")
            if value.strip()
        }
        if not allowed_domains:
            violations.append("Remote connector domain allowlist is empty.")
        elif parsed.hostname and parsed.hostname.lower() not in allowed_domains:
            violations.append(f"Remote connector host {parsed.hostname} is not allowlisted.")
    connector.last_dry_run_payload = {
        "status": "blocked" if violations else "ready",
        "violations": violations,
        "network_executed": False,
        "secrets_persisted": False,
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    connector.status = "blocked" if violations else "ready"
    db.commit()
    db.refresh(connector)
    return connector


def serialize_connector(connector: KnowledgeConnector) -> dict[str, object]:
    return {
        "id": str(connector.id),
        "space_id": str(connector.space_id),
        "name": connector.name,
        "connector_type": connector.connector_type,
        "status": connector.status,
        "endpoint": connector.endpoint,
        "permissions": list(connector.permissions_payload or []),
        "config_fingerprint": connector.config_fingerprint,
        "last_dry_run": connector.last_dry_run_payload or {},
        "last_sync_at": connector.last_sync_at,
    }


def invoke_controlled_mcp(
    db: Session,
    *,
    connector: KnowledgeConnector,
    action: str,
    arguments: dict[str, object],
    granted_permissions: list[str],
    dry_run: bool = True,
    runner: Callable[[str, str, dict[str, object]], dict[str, object]] | None = None,
) -> dict[str, object]:
    violations: list[str] = []
    required_permission = MCP_ACTION_PERMISSIONS.get(action)
    if connector.connector_type != "mcp":
        violations.append("Controlled MCP invocation requires an MCP connector.")
    if connector.status != "ready":
        violations.append("Connector must pass allowlist and permission dry-run before invocation.")
    if required_permission is None:
        violations.append("Unsupported controlled MCP action.")
    else:
        declared = {str(value) for value in connector.permissions_payload or []}
        if required_permission not in declared:
            violations.append(f"Connector did not declare {required_permission}.")
        if required_permission not in set(granted_permissions):
            violations.append(f"Runtime did not grant {required_permission}.")
    sensitive_keys = {"token", "password", "secret", "api_key", "authorization", "cookie"}
    if any(str(key).lower() in sensitive_keys for key in arguments):
        violations.append("Secrets and credentials are not accepted in MCP arguments.")
    serialized_size = len(json.dumps(arguments, ensure_ascii=False, default=str))
    if serialized_size > 100_000:
        violations.append("MCP arguments exceed the 100 KB sandbox limit.")
    plan = {
        "connector_id": str(connector.id),
        "endpoint": connector.endpoint,
        "action": action,
        "required_permission": required_permission,
        "arguments": arguments if not violations else {},
        "network_executed": False,
        "dry_run": dry_run,
    }
    if violations:
        return {"status": "blocked", "plan": plan, "violations": violations, "result": {}}
    if dry_run:
        return {"status": "ready", "plan": plan, "violations": [], "result": {}}
    if runner is None:
        return {
            "status": "blocked",
            "plan": plan,
            "violations": ["No governed MCP transport runner is installed; network execution remains disabled."],
            "result": {},
        }
    result = runner(connector.endpoint, action, arguments)
    connector.last_sync_at = datetime.now(UTC)
    connector.last_dry_run_payload = {
        **dict(connector.last_dry_run_payload or {}),
        "last_controlled_action": action,
        "last_controlled_status": "succeeded",
        "network_executed": True,
    }
    db.commit()
    return {"status": "succeeded", "plan": {**plan, "network_executed": True}, "violations": [], "result": result}
