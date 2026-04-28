from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import User
from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.task_runtime import create_and_execute_task


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def _report() -> ResearchReportResponse:
    return ResearchReportResponse(
        keyword="政务AI解决方案",
        research_focus="面向政务热线和政务服务大厅的 AI 助手、知识库和工单协同平台。",
        output_language="zh-CN",
        research_mode="deep",
        report_title="政务AI解决方案机会研判",
        executive_summary="政务服务和热线场景近三年持续出现数字化、智能问答和工单协同建设需求。",
        consulting_angle="先锁定目标数据局/政务服务中心，再用近三年招采和产品参数反推方案边界。",
        target_accounts=["某市数据局"],
        target_departments=["政务服务中心", "热线管理处"],
        budget_signals=["一期预算 300 万-500 万"],
        tender_timeline=["2026 Q3 招采窗口"],
        strategic_directions=["先做政务AI助手试点，再扩到热线和大厅联动。"],
        flagship_products=["政务AI助手平台"],
        source_count=1,
        evidence_density="medium",
        source_quality="medium",
        sources=[
            ResearchSourceOut(
                title="某市政务服务AI助手公开招标公告",
                url="https://ggzy.example.gov.cn/tender/gov-ai",
                domain="ggzy.example.gov.cn",
                snippet="2025年公开招标，包含知识库、智能问答、工单协同，要求支持 API 接口、私有化部署、等保三级。",
                search_query="政务AI 助手 招标 技术参数",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            )
        ],
        generated_at=datetime.now(timezone.utc),
    )


def test_solution_intelligence_export_tasks_generate_markdown_artifacts() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        report = _report()
        delivery_supplement = {
            "solution_scenario": "政务AI解决方案",
            "target_customer": "某市数据局",
            "vertical_scene": "政务热线 AI 助手",
            "supplemental_context": "客户希望先做试点。",
        }
        intelligence_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_research_market_intelligence_markdown",
            input_payload={
                "output_language": "zh-CN",
                "report": report.model_dump(mode="json"),
                "delivery_supplement": delivery_supplement,
            },
        )
        solution_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_research_solution_delivery_markdown",
            input_payload={
                "output_language": "zh-CN",
                "report": report.model_dump(mode="json"),
                "delivery_supplement": delivery_supplement,
            },
        )

        assert intelligence_task.status == "done"
        assert intelligence_task.output_payload["document_kind"] == "market_intelligence"
        assert "近三年招投标与产品技术参数情报包" in str(intelligence_task.output_payload.get("content") or "")
        assert solution_task.status == "done"
        assert solution_task.output_payload["document_kind"] == "solution_delivery"
        assert "对客汇报 PPT 大纲" in str(solution_task.output_payload.get("content") or "")
        assert "政务AI解决方案" in str(solution_task.output_payload.get("content") or "")
    finally:
        db.close()
