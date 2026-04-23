from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import KnowledgeEntry, User
from app.schemas.research import ResearchReportResponse
from app.services.research_evaluation_service import build_offline_research_evaluation


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


def _build_report(
    *,
    title: str,
    keyword: str,
    strict_topic_source_count: int,
    strict_match_ratio: float,
    retrieval_quality: str,
    supported_targets: list[str],
    unsupported_targets: list[str],
    official_source_ratio: float,
    section_passed: bool,
) -> ResearchReportResponse:
    now = datetime.now(timezone.utc)
    return ResearchReportResponse(
        keyword=keyword,
        research_focus="梳理预算窗口、组织入口和推进策略",
        output_language="zh-CN",
        research_mode="deep",
        report_title=title,
        executive_summary=f"{title} 执行摘要",
        consulting_angle="围绕预算、组织入口和推进路径做判断。",
        target_accounts=[*(supported_targets or []), *(unsupported_targets or [])],
        target_departments=["采购中心"],
        budget_signals=["7 月预算复核"],
        source_count=max(strict_topic_source_count, 2),
        evidence_density="high" if section_passed else "medium",
        source_quality="high" if retrieval_quality == "high" else "low",
        sources=[
            {
                "title": "公开公告",
                "url": f"https://example.com/{uuid.uuid4()}",
                "domain": "example.com",
                "snippet": "预算与采购线索",
                "search_query": keyword,
                "source_type": "policy",
                "content_status": "extracted",
                "source_label": "官网",
                "source_tier": "official",
            }
        ],
        source_diagnostics={
            "scope_regions": ["上海"],
            "scope_industries": ["政务云"],
            "scope_clients": [*(supported_targets or []), *(unsupported_targets or [])],
            "supported_target_accounts": supported_targets,
            "unsupported_target_accounts": unsupported_targets,
            "official_source_ratio": official_source_ratio,
            "strict_topic_source_count": strict_topic_source_count,
            "strict_match_ratio": strict_match_ratio,
            "retrieval_quality": retrieval_quality,
            "evidence_mode": "strong" if retrieval_quality != "low" else "fallback",
        },
        sections=[
            {
                "title": "项目与商机判断",
                "items": ["预算窗口已出现。"],
                "evidence_count": 2 if section_passed else 1,
                "evidence_quota": 2,
                "meets_evidence_quota": section_passed,
                "quota_gap": 0 if section_passed else 1,
            }
        ],
        generated_at=now,
    )


def test_build_offline_research_evaluation_summarizes_core_metrics_and_weak_reports() -> None:
    db = _new_session()
    try:
        user = _seed_demo_user(db)
        strong_report = _build_report(
            title="上海数据集团预算窗口研判",
            keyword="上海数据集团预算窗口",
            strict_topic_source_count=6,
            strict_match_ratio=0.82,
            retrieval_quality="high",
            supported_targets=["上海数据集团"],
            unsupported_targets=[],
            official_source_ratio=0.72,
            section_passed=True,
        )
        weak_report = _build_report(
            title="南京政务云候选推进",
            keyword="南京政务云预算窗口",
            strict_topic_source_count=0,
            strict_match_ratio=0.12,
            retrieval_quality="low",
            supported_targets=[],
            unsupported_targets=["南京市数据局"],
            official_source_ratio=0.12,
            section_passed=False,
        )
        db.add_all(
            [
                KnowledgeEntry(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title=strong_report.report_title,
                    content="强样本",
                    source_domain="research.report",
                    metadata_payload={"report": strong_report.model_dump(mode="json")},
                ),
                KnowledgeEntry(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title=weak_report.report_title,
                    content="弱样本",
                    source_domain="research.report",
                    metadata_payload={"report": weak_report.model_dump(mode="json")},
                ),
                KnowledgeEntry(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title="损坏 payload",
                    content="无效",
                    source_domain="research.report",
                    metadata_payload={"report": {"keyword": "bad"}},
                ),
            ]
        )
        db.commit()

        evaluation = build_offline_research_evaluation(db, weakest_limit=4)

        assert evaluation.total_reports == 3
        assert evaluation.evaluated_reports == 2
        assert evaluation.invalid_payloads == 1
        metric_map = {metric.key: metric for metric in evaluation.metrics}
        assert metric_map["retrieval_hit_rate"].numerator == 1
        assert metric_map["retrieval_hit_rate"].denominator == 2
        assert metric_map["retrieval_hit_rate"].percent == 50
        assert metric_map["target_support_rate"].numerator == 1
        assert metric_map["target_support_rate"].denominator == 2
        assert metric_map["section_quota_pass_rate"].numerator == 1
        assert metric_map["section_quota_pass_rate"].denominator == 2
        assert evaluation.weakest_reports
        assert evaluation.weakest_reports[0].report_title == "南京政务云候选推进"
        assert evaluation.weakest_reports[0].unsupported_targets == ["南京市数据局"]
        assert evaluation.summary_lines
    finally:
        db.close()
