from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import KnowledgeEntry, User
from app.schemas.research import (
    ResearchExperimentPlanCreateRequest,
    ResearchExperimentRolloutActionRequest,
    ResearchReportResponse,
)
from app.services.research_experiment_orchestration_service import (
    build_research_experiment_orchestration,
    create_research_experiment_plan,
    evaluate_research_experiment_rollout_gate,
    freeze_research_experiment_cohort,
    lock_research_experiment_baseline,
    promote_research_experiment_rollout,
    revoke_research_experiment_rollout,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def _seed_demo_user(db: Session) -> User:
    settings = get_settings()
    user = User(
        id=settings.single_user_id,
        name="Demo User",
        email="demo@anti-fomo.local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_report(title: str, keyword: str) -> ResearchReportResponse:
    now = datetime.now(timezone.utc)
    return ResearchReportResponse(
        keyword=keyword,
        research_focus="核验项目预算窗口、组织入口和采购推进链路",
        output_language="zh-CN",
        research_mode="deep",
        report_title=title,
        executive_summary=f"{title} 执行摘要",
        consulting_angle="围绕预算、组织入口和推进路径做判断。",
        target_accounts=["上海数据集团"],
        target_departments=["采购中心"],
        budget_signals=["7 月预算复核"],
        source_count=2,
        evidence_density="high",
        source_quality="high",
        sources=[
            {
                "title": "行业观察",
                "url": f"https://media.example.com/{uuid.uuid4()}",
                "domain": "media.example.com",
                "snippet": "泛行业趋势观察",
                "search_query": keyword,
                "source_type": "web",
                "content_status": "snippet",
                "source_label": "行业媒体",
                "source_tier": "media",
            },
            {
                "title": "公开公告",
                "url": f"https://example.gov.cn/{uuid.uuid4()}",
                "domain": "example.gov.cn",
                "snippet": "预算与采购线索",
                "search_query": keyword,
                "source_type": "policy",
                "content_status": "extracted",
                "source_label": "官网",
                "source_tier": "official",
            },
        ],
        source_diagnostics={
            "scope_regions": ["上海"],
            "scope_industries": ["政务云"],
            "scope_clients": ["上海数据集团"],
            "supported_target_accounts": ["上海数据集团"],
            "unsupported_target_accounts": [],
            "official_source_ratio": 0.5,
            "strict_topic_source_count": 4,
            "strict_match_ratio": 0.72,
            "retrieval_quality": "high",
            "evidence_mode": "strong",
        },
        sections=[
            {
                "title": "项目与商机判断",
                "items": ["预算窗口已出现。"],
                "evidence_count": 2,
                "evidence_quota": 2,
                "meets_evidence_quota": True,
                "quota_gap": 0,
            }
        ],
        generated_at=now,
    )


def test_experiment_plan_audits_gate_history_and_rollout_manifest() -> None:
    db = _new_session()
    try:
        user = _seed_demo_user(db)
        reports = [
            _build_report("上海数据集团预算窗口研判", "上海数据集团预算窗口"),
            _build_report("上海数据集团采购链路研判", "上海数据集团采购链路"),
        ]
        db.add_all(
            [
                KnowledgeEntry(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title=report.report_title,
                    content=report.executive_summary,
                    source_domain="research.report",
                    metadata_payload={"report": report.model_dump(mode="json")},
                )
                for report in reports
            ]
        )
        db.commit()

        created = create_research_experiment_plan(
            db,
            ResearchExperimentPlanCreateRequest(
                name="CrossEncoder rollout",
                lane_key="reranker_official_recall",
                strategy_family="reranker",
                candidate_label="cross-encoder-v1",
                gate_config={"minimum_sample_size": 1, "minimum_uplift_points": 1},
            ),
        )

        frozen = freeze_research_experiment_cohort(db, created["id"])
        assert frozen["status"] == "cohort_frozen"
        assert frozen["cohort_size"] == 2
        assert len(frozen["cohort_entry_ids"]) == 2

        locked = lock_research_experiment_baseline(db, created["id"])
        assert locked["status"] == "baseline_locked"
        assert locked["baseline_version_label"]
        assert locked["baseline_lane"]["baseline"]["denominator"] == 2

        with pytest.raises(ValueError, match="Baseline already locked"):
            freeze_research_experiment_cohort(db, created["id"])

        gated = evaluate_research_experiment_rollout_gate(db, created["id"])
        assert gated["status"] == "gate_blocked"
        assert gated["latest_gate"]["decision"] == "block"
        assert gated["latest_gate"]["sample_size"] == 2
        assert gated["latest_gate"]["required_uplift_points"] == 1
        assert gated["latest_gate"]["observed_uplift_points"] == 0
        assert gated["gate_history_count"] == 1

        with pytest.raises(ValueError, match="Only allowed rollout gates"):
            promote_research_experiment_rollout(
                db,
                created["id"],
                ResearchExperimentRolloutActionRequest(note="blocked strategy must not promote"),
            )

        allowed_created = create_research_experiment_plan(
            db,
            ResearchExperimentPlanCreateRequest(
                name="CrossEncoder rollout allowed",
                lane_key="reranker_official_recall",
                strategy_family="reranker",
                candidate_label="cross-encoder-v1",
                gate_config={"minimum_sample_size": 1, "minimum_uplift_points": 0},
            ),
        )
        freeze_research_experiment_cohort(db, allowed_created["id"])
        lock_research_experiment_baseline(db, allowed_created["id"])
        allowed = evaluate_research_experiment_rollout_gate(db, allowed_created["id"])
        assert allowed["status"] == "gate_allowed"
        assert allowed["latest_gate"]["decision"] == "allow"
        assert allowed["gate_history_count"] == 1

        promoted = promote_research_experiment_rollout(
            db,
            allowed_created["id"],
            ResearchExperimentRolloutActionRequest(note="promote after gate allow"),
        )
        assert promoted["status"] == "rollout_promoted"
        assert promoted["rollout_manifest"]["decision"] == "promoted"
        assert promoted["rollout_manifest"]["activation_payload"]["rollout_gate"]["decision"] == "allow"
        assert promoted["promoted_at"] is not None

        revoked = revoke_research_experiment_rollout(
            db,
            allowed_created["id"],
            ResearchExperimentRolloutActionRequest(note="revoke after validation"),
        )
        assert revoked["status"] == "rollout_revoked"
        assert revoked["rollout_manifest"]["decision"] == "revoked"
        assert revoked["rollout_revoked_at"] is not None

        orchestration = build_research_experiment_orchestration(db)
        assert orchestration.total_plans == 2
        assert orchestration.frozen_plan_count == 2
        assert orchestration.locked_plan_count == 2
        assert orchestration.allowed_plan_count == 1
        assert orchestration.blocked_plan_count == 1
        assert orchestration.promoted_plan_count == 0
        assert orchestration.revoked_plan_count == 1
    finally:
        db.close()
