from __future__ import annotations

from base64 import b64decode
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import User
from app.schemas.research import (
    ResearchFollowupContextOut,
    ResearchFollowupDiagnosticsOut,
    ResearchFollowupSectionImpactOut,
    ResearchReportResponse,
    ResearchSourceOut,
)
from app.services.work_task_service import build_research_plaintext
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
        pptx_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_research_solution_delivery_pptx",
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
        assert "Advisory-grade 交付产物" in str(solution_task.output_payload.get("content") or "")
        assert "客户 brief" in str(solution_task.output_payload.get("content") or "")
        assert "政务AI解决方案" in str(solution_task.output_payload.get("content") or "")
        assert "交付质量自审" in str(solution_task.output_payload.get("content") or "")
        assert "解决方案架构就绪度" in str(solution_task.output_payload.get("content") or "")
        assert "架构蓝图" in str(solution_task.output_payload.get("content") or "")
        assert "解决方案架构师工作台" in str(solution_task.output_payload.get("content") or "")
        assert "干系人问题地图" in str(solution_task.output_payload.get("content") or "")
        assert "能力到架构矩阵" in str(solution_task.output_payload.get("content") or "")
        assert "ADR 架构决策记录" in str(solution_task.output_payload.get("content") or "")
        assert "集成依赖诊断" in str(solution_task.output_payload.get("content") or "")
        assert "量化决策模型" in str(solution_task.output_payload.get("content") or "")
        assert "可研财务三情景" in str(solution_task.output_payload.get("content") or "")
        assert pptx_task.status == "done"
        assert pptx_task.output_payload["document_kind"] == "solution_delivery_pptx"
        assert pptx_task.output_payload["filename"].endswith(".pptx")
        assert pptx_task.output_payload["mime_type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        assert pptx_task.output_payload["formal_rendering"]["editable_text_boxes"] is True
        assert pptx_task.output_payload["formal_rendering"]["office_roundtrip"]["status"] == "pass"
        with ZipFile(BytesIO(b64decode(str(pptx_task.output_payload.get("content_base64") or "")))) as archive:
            assert "ppt/presentation.xml" in archive.namelist()
            slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "<p:txBody>" in slide_xml
        assert "Anti-FOMO P2.3 editable PPTX" in slide_xml
        assert "图表占位" in slide_xml
    finally:
        db.close()


def test_research_plaintext_export_includes_followup_resolution_and_impacted_sections() -> None:
    report = _report().model_copy(
        update={
            "followup_context": ResearchFollowupContextOut(
                followup_report_title="政务AI解决方案机会研判",
                followup_report_summary="上一版摘要",
                supplemental_context="补充了政务热线试点背景。",
                supplemental_evidence="新增公开招标要求支持工单协同。",
                supplemental_requirements="优先重写解决方案设计建议。",
            ),
            "followup_diagnostics": ResearchFollowupDiagnosticsOut(
                enabled=True,
                title_resolution="corrected",
                summary_resolution="corrected",
                impacted_sections=[
                    ResearchFollowupSectionImpactOut(
                        section_title="解决方案设计建议",
                        impact_score=78,
                        impact_label="high",
                        reason="新增试点约束已直接命中方案章节。",
                        next_action="优先补试点范围、接口约束和部署边界。",
                    )
                ],
            ),
        }
    )

    _filename, content = build_research_plaintext(report, output_language="zh-CN")

    assert "标题处理：已按追问纠偏" in content
    assert "摘要处理：已按追问纠偏" in content
    assert "重点影响章节：解决方案设计建议" in content
