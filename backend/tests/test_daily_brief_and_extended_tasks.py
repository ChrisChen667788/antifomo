from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import FocusSession, Item, KnowledgeEntry, SessionItem, User
from app.models.research_entities import ResearchWatchlist, ResearchWatchlistChangeEvent
from app.schemas.research import ResearchReportDocument, ResearchReportSectionOut
from app.services import daily_brief_service, task_runtime
from app.services.knowledge_intelligence_service import build_research_report_metadata
from app.services.task_runtime import create_and_execute_task
from app.services.work_task_service import build_exec_brief, build_sales_brief


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_daily_brief_uses_current_user_items_and_watchlist_changes(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    another_user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    try:
        db.add_all(
            [
                User(id=settings.single_user_id, name="demo"),
                User(id=another_user_id, name="other"),
            ]
        )
        db.flush()

        db.add(
            Item(
                user_id=settings.single_user_id,
                source_type="url",
                source_url="https://example.com/a",
                source_domain="example.com",
                title="今日重点 A",
                short_summary="需要优先阅读的重点摘要",
                action_suggestion="deep_read",
                output_language="zh-CN",
                status="ready",
            )
        )
        db.add(
            Item(
                user_id=another_user_id,
                source_type="url",
                source_url="https://example.com/b",
                source_domain="example.com",
                title="其他用户内容",
                short_summary="不应出现在 demo 用户日报里",
                action_suggestion="later",
                output_language="zh-CN",
                status="ready",
            )
        )
        db.flush()

        demo_watchlist = ResearchWatchlist(
            user_id=settings.single_user_id,
            name="Demo Watchlist",
            query="AI 浏览器",
        )
        other_watchlist = ResearchWatchlist(
            user_id=another_user_id,
            name="Other Watchlist",
            query="无关主题",
        )
        db.add_all([demo_watchlist, other_watchlist])
        db.flush()

        db.add_all(
            [
                ResearchWatchlistChangeEvent(
                    watchlist_id=demo_watchlist.id,
                    change_type="added",
                    summary="新增上海甲方招采线索",
                    severity="high",
                    payload={},
                ),
                ResearchWatchlistChangeEvent(
                    watchlist_id=other_watchlist.id,
                    change_type="risk",
                    summary="其他用户的风险提示",
                    severity="medium",
                    payload={},
                ),
            ]
        )
        db.commit()

        monkeypatch.setattr(
            daily_brief_service,
            "_generate_audio",
            lambda snapshot, script: ("ready", f"/api/mobile/daily-brief/audio/{snapshot.id}"),
        )

        snapshot = daily_brief_service.build_daily_brief_snapshot(
            db,
            user_id=settings.single_user_id,
            force_refresh=True,
        )
        payload = daily_brief_service.serialize_daily_brief(snapshot)

        assert payload["headline"] == "今日重点 A"
        assert payload["top_items"][0]["title"] == "今日重点 A"
        assert len(payload["watchlist_changes"]) == 1
        assert payload["watchlist_changes"][0]["summary"] == "新增上海甲方招采线索"
        assert payload["audio_status"] == "ready"
    finally:
        db.close()


def test_extended_export_tasks_generate_expected_outputs() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.flush()

        session = FocusSession(
            user_id=settings.single_user_id,
            goal_text="跟进浏览器赛道客户",
            output_language="zh-CN",
            duration_minutes=30,
            start_time=datetime(2026, 3, 28, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 28, 9, 30, tzinfo=timezone.utc),
            status="finished",
            summary_text="优先整理拜访提纲和老板同步要点。",
        )
        db.add(session)
        db.flush()

        item = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://example.com/browser",
            source_domain="example.com",
            title="浏览器赛道项目更新",
            short_summary="甲方试点继续推进，适合输出销售和老板简报。",
            long_summary="甲方试点继续推进，适合输出销售和老板简报。",
            action_suggestion="deep_read",
            output_language="zh-CN",
            status="ready",
        )
        db.add(item)
        db.flush()
        db.add(SessionItem(session_id=session.id, item_id=item.id))

        report = ResearchReportDocument(
            keyword="浏览器赛道甲方推进",
            research_focus="补预算窗口、组织入口和公开联系人",
            followup_context={
                "followup_report_title": "浏览器赛道重点甲方推进研判",
                "followup_report_summary": "上一版建议优先跟进浏览器客户A。",
                "supplemental_context": "销售团队补充：客户已进入年度预算讨论。",
                "supplemental_evidence": "待核验线索：4 月底可能发起二期可研评审。",
                "supplemental_requirements": "请补立项窗口、建设单位和预算口径。",
            },
            output_language="zh-CN",
            research_mode="deep",
            report_title="浏览器赛道重点甲方推进研判",
            executive_summary="优先围绕浏览器客户A的预算窗口和商务入口推进。",
            consulting_angle="先确认业务 sponsor、预算归口和 close plan，再安排会前简报。",
            sections=[
                ResearchReportSectionOut(
                    title="竞争分析",
                    items=["竞品进入窗口存在冲突线索，仍需二次核验。"],
                    evidence_density="low",
                    source_quality="medium",
                    confidence_tone="conflict",
                    contradiction_detected=True,
                    contradiction_note="两类来源对进入节奏表述不一致。",
                    official_source_ratio=0.0,
                    evidence_count=1,
                    evidence_quota=2,
                    meets_evidence_quota=False,
                )
            ],
            target_accounts=["浏览器客户A"],
            top_target_accounts=[
                {
                    "name": "浏览器客户A",
                    "score": 83,
                    "reasoning": "预算和公开组织入口较清晰。",
                    "score_breakdown": [],
                    "evidence_links": [],
                }
            ],
            target_departments=["数字化部", "采购中心"],
            public_contact_channels=["官网商务合作入口"],
            budget_signals=["预算窗口集中在未来 1-2 个季度"],
            strategic_directions=["优先切入浏览器智能助手与会员运营"],
            tender_timeline=["本季度完成内部立项，下季度启动采购"],
            source_count=4,
        )
        db.add(
            KnowledgeEntry(
                user_id=settings.single_user_id,
                title=report.report_title,
                content="demo",
                source_domain="research.report",
                metadata_payload=build_research_report_metadata(report, action_cards=[]),
            )
        )

        watchlist = ResearchWatchlist(
            user_id=settings.single_user_id,
            name="AI Browser Watchlist",
            query="AI 浏览器",
        )
        db.add(watchlist)
        db.flush()
        db.add(
            ResearchWatchlistChangeEvent(
                watchlist_id=watchlist.id,
                change_type="added",
                summary="新增重点甲方和预算信号",
                severity="high",
                payload={},
            )
        )
        db.commit()

        exec_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_exec_brief",
            session_id=session.id,
            input_payload={"output_language": "zh-CN"},
        )
        sales_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_sales_brief",
            session_id=session.id,
            input_payload={"output_language": "zh-CN"},
        )
        outreach_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_outreach_draft",
            input_payload={"output_language": "zh-CN"},
        )
        digest_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_watchlist_digest",
            input_payload={"output_language": "zh-CN"},
        )
        feasibility_word_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_feasibility_study_word",
            input_payload={
                "output_language": "zh-CN",
                "report": report.model_dump(mode="json"),
                "delivery_supplement": {
                    "project_name": "浏览器智能助手建设项目",
                    "project_owner": "浏览器客户A",
                    "target_customer": "浏览器客户A集团总部",
                    "solution_scenario": "AI营销平台",
                    "vertical_scene": "会员运营 AI 助手",
                    "project_region": "华东区域",
                    "implementation_window": "2026 Q2-Q4",
                    "investment_estimate": "一期预算 500-800 万",
                    "construction_basis": "结合公开预算信号和内部会议补充整理。",
                    "scope_statement": "先做智能助手试点，再扩到会员运营和客服场景。",
                    "expected_benefits": "提升用户留存和运营自动化水平。",
                    "cross_validation_notes": "二期可研时间点仍需结合招采公告继续验证。",
                    "supplemental_context": "客户已开始准备年度预算材料。",
                    "supplemental_evidence": "4 月底可能发起二期可研评审。",
                    "supplemental_requirements": "重点补预算口径和实施窗口。",
                },
            },
        )
        proposal_pdf_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_project_proposal_pdf",
            input_payload={
                "output_language": "zh-CN",
                "report": report.model_dump(mode="json"),
                "delivery_supplement": {
                    "project_name": "浏览器智能助手建设项目",
                    "target_customer": "浏览器客户A集团总部",
                    "solution_scenario": "AI营销平台",
                    "vertical_scene": "会员运营 AI 助手",
                    "scope_statement": "以浏览器智能助手作为一期建设主线。",
                    "cross_validation_notes": "项目建议书中保留二期时间点待核验说明。",
                },
            },
        )

        assert exec_task.status == "done"
        assert "老板" in str(exec_task.output_payload.get("content") or "")
        assert "账户推进上下文" in str(exec_task.output_payload.get("content") or "")
        assert isinstance(exec_task.output_payload.get("briefing_context"), dict)
        assert sales_task.status == "done"
        assert "销售" in str(sales_task.output_payload.get("content") or "")
        assert "Stakeholder Map" in str(sales_task.output_payload.get("content") or "")
        assert outreach_task.status == "done"
        assert "外联" in str(outreach_task.output_payload.get("content") or "")
        assert "浏览器客户A" in str(outreach_task.output_payload.get("content") or "")
        assert digest_task.status == "done"
        assert digest_task.output_payload["change_count"] == 1
        assert "新增重点甲方和预算信号" in str(digest_task.output_payload.get("content") or "")
        assert isinstance(digest_task.output_payload.get("watchlist_context"), dict)
        assert feasibility_word_task.status == "done"
        assert feasibility_word_task.output_payload["document_kind"] == "feasibility_study"
        assert "浏览器智能助手建设项目可行性研究报告" in str(feasibility_word_task.output_payload.get("content") or "")
        assert "二、研究依据与交叉验证输入" in str(feasibility_word_task.output_payload.get("content") or "")
        assert "4 月底可能发起二期可研评审" in str(feasibility_word_task.output_payload.get("content") or "")
        assert "目标客户：浏览器客户A集团总部" in str(feasibility_word_task.output_payload.get("content") or "")
        assert "项目/方案场景：AI营销平台" in str(feasibility_word_task.output_payload.get("content") or "")
        assert "垂直场景：会员运营 AI 助手" in str(feasibility_word_task.output_payload.get("content") or "")
        assert proposal_pdf_task.status == "done"
        assert proposal_pdf_task.output_payload["document_kind"] == "project_proposal"
        assert proposal_pdf_task.output_payload["format"] == "pdf"
        assert proposal_pdf_task.output_payload.get("content_base64")
        assert "项目建议书" in str(proposal_pdf_task.output_payload.get("content") or "")
        assert "交叉验证附注" in str(proposal_pdf_task.output_payload.get("content") or "")
        assert "目标客户：浏览器客户A集团总部" in str(proposal_pdf_task.output_payload.get("content") or "")
        assert "项目/方案场景：AI营销平台" in str(proposal_pdf_task.output_payload.get("content") or "")
        assert "垂直场景：会员运营 AI 助手" in str(proposal_pdf_task.output_payload.get("content") or "")
    finally:
        db.close()


def test_exec_and_sales_brief_filter_wechat_auto_noise_items() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.flush()

        db.add_all(
            [
                Item(
                    user_id=settings.single_user_id,
                    source_type="plugin",
                    source_domain="mp.weixin.qq.com",
                    title="WeChat Auto 04-17 09:27 B1R1：主体账号 行业账号 区域账号 省级账号 地市级账号",
                    short_summary="主体账号 行业账号 区域账号 省级账号 地市级账号",
                    raw_content="主体账号 行业账号 区域账号 省级账号 地市级账号",
                    action_suggestion="deep_read",
                    output_language="zh-CN",
                    status="ready",
                ),
                Item(
                    user_id=settings.single_user_id,
                    source_type="plugin",
                    source_domain="mp.weixin.qq.com",
                    title="WeChat Auto 04-18 06:25 B1R1：华泰证券华为云昇腾算力服务项目中标结果公示",
                    short_summary="项目已进入结果公示阶段，建议优先核验建设单位、预算口径和二期扩容窗口。",
                    raw_content="标题：华泰证券华为云昇腾算力服务项目中标结果公示。正文：项目已进入结果公示阶段。",
                    action_suggestion="deep_read",
                    output_language="zh-CN",
                    status="ready",
                ),
            ]
        )
        db.commit()

        exec_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_exec_brief",
            input_payload={"output_language": "zh-CN"},
        )
        sales_task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_sales_brief",
            input_payload={"output_language": "zh-CN"},
        )

        exec_content = str(exec_task.output_payload.get("content") or "")
        sales_content = str(sales_task.output_payload.get("content") or "")

        assert exec_task.status == "done"
        assert sales_task.status == "done"
        assert "WeChat Auto" not in exec_content
        assert "WeChat Auto" not in sales_content
        assert "主体账号 行业账号" not in exec_content
        assert "主体账号 行业账号" not in sales_content
        assert "华泰证券华为云昇腾算力服务项目中标结果公示" in exec_content
        assert "华泰证券华为云昇腾算力服务项目中标结果公示" in sales_content
    finally:
        db.close()


def test_exec_and_sales_brief_omit_low_quality_ocr_items_and_fallback_to_context() -> None:
    noise_item = Item(
        user_id=uuid.uuid4(),
        source_type="plugin",
        source_domain="wechat.local",
        ingest_route="ocr",
        title="WeChat Auto 04-18 06:25 B1R1",
        short_summary="原创 行业号 2026年4月18日 06:25 微信扫一扫 听全文",
        raw_content="原创 行业号 2026年4月18日 06:25 微信扫一扫 听全文",
        action_suggestion="deep_read",
        output_language="zh-CN",
        status="ready",
    )
    knowledge_context = {
        "top_accounts": [
            {
                "name": "华东银行",
                "budget_probability": 82,
                "next_best_action": "优先确认预算归口和二期评审窗口。",
            }
        ],
        "top_opportunities": [
            {
                "title": "算力扩容二期项目",
                "account_name": "华东银行",
                "budget_probability": 76,
                "next_step": "安排下周会前简报并确认 sponsor。",
            }
        ],
        "review_queue": [
            {
                "title": "预算口径仍待核验",
                "severity": "high",
                "summary": "公开招采和内部口径暂未完全对齐。",
                "recommended_action": "继续补证。",
            }
        ],
    }

    exec_content = build_exec_brief(output_language="zh-CN", items=[noise_item], knowledge_context=knowledge_context)
    sales_content = build_sales_brief(output_language="zh-CN", items=[noise_item], knowledge_context=knowledge_context)

    assert "今日重点: 0" in exec_content or "今日重点：0" in exec_content
    assert "低可信 OCR 预览" in exec_content
    assert "建议优先推进账户" in exec_content
    assert "华东银行" in exec_content
    assert "当前重点商机" in exec_content
    assert "算力扩容二期项目" in exec_content
    assert "WeChat Auto" not in exec_content

    assert "低可信 OCR 预览" in sales_content
    assert "建议优先推进账户" in sales_content
    assert "当前重点商机" in sales_content
    assert "算力扩容二期项目" in sales_content
    assert "WeChat Auto" not in sales_content


def test_briefing_account_context_sanitizes_markdown_image_and_meta_noise() -> None:
    knowledge_context = {
        "account": {
            "name": "上海市市场监督管理局",
            "objective": "确认预算归口和推进窗口。",
            "value_hypothesis": "[Image 1](http://example.com/a.png)](http://example.com/b)",
            "next_meeting_goal": "确认项目 owner 和下一次会前简报范围。",
            "why_now": [
                "[Image 1](http://example.com/c.png)",
                "推出首批12个人工智能：长三角opc创新创业姑苏挑战赛项目报名通道开启 - 苏州市人民政府",
                "微信扫一扫 听全文 2026年4月18日 09:00",
            ],
            "stakeholders": [
                {
                    "name": "公开入口",
                    "role": "medium",
                    "priority": "medium",
                    "next_move": "[Image 1](http://example.com/d.png)",
                }
            ],
        },
        "top_accounts": [
            {"name": "上海市市场监督管理局", "budget_probability": 92, "next_best_action": "优先确认预算归口。"}
        ],
        "top_opportunities": [
            {"title": "OPC 社区项目", "account_name": "上海市市场监督管理局", "budget_probability": 88, "next_step": "确认立项口径。"}
        ],
    }

    exec_content = build_exec_brief(output_language="zh-CN", items=[], knowledge_context=knowledge_context)
    sales_content = build_sales_brief(output_language="zh-CN", items=[], knowledge_context=knowledge_context)

    assert "[Image 1]" not in exec_content
    assert "http://example.com" not in exec_content
    assert "微信扫一扫" not in exec_content
    assert "推出首批12个人工智能" in exec_content
    assert "价值假设" not in exec_content

    assert "[Image 1]" not in sales_content
    assert "http://example.com" not in sales_content
    assert "微信扫一扫" not in sales_content
    assert "继续确认其真实影响力。" in sales_content


def test_task_runtime_stores_sanitized_briefing_context(monkeypatch) -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        monkeypatch.setattr(
            task_runtime,
            "_build_task_knowledge_context",
            lambda db, report_payload=None: {
                "account": {
                    "name": "上海市市场监督管理局",
                    "value_hypothesis": "[Image 1](http://example.com/a.png)](http://example.com/b)",
                    "why_now": [
                        "[Image 1](http://example.com/c.png)",
                        "推出首批12个人工智能：长三角opc创新创业姑苏挑战赛项目报名通道开启 - 苏州市人民政府",
                    ],
                }
            },
        )

        task = create_and_execute_task(
            db,
            user_id=settings.single_user_id,
            task_type="export_exec_brief",
            input_payload={"output_language": "zh-CN"},
        )

        context = task.output_payload.get("briefing_context") or {}
        account = context.get("account") or {}
        assert task.status == "done"
        assert "value_hypothesis" not in account
        assert account.get("why_now") == ["推出首批12个人工智能：长三角opc创新创业姑苏挑战赛项目报名通道开启 - 苏州市人民政府"]
    finally:
        db.close()
