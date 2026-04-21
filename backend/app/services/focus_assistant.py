from __future__ import annotations

from typing import Iterable
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import FocusSession, KnowledgeEntry
from app.schemas.focus_assistant import (
    FocusAssistantActionOut,
    FocusAssistantExecuteRequest,
    FocusAssistantPlanOut,
    FocusAssistantPlanRequest,
)
from app.services.language import normalize_output_language
from app.services.task_runtime import create_and_execute_task
from app.services.workbuddy_adapter import run_codebuddy_prompt


settings = get_settings()


def _load_latest_session(db: Session) -> FocusSession | None:
    return db.scalar(
        select(FocusSession)
        .where(FocusSession.user_id == settings.single_user_id)
        .order_by(desc(FocusSession.start_time))
        .limit(1)
    )


def _load_focus_references(db: Session, limit: int = 8) -> list[KnowledgeEntry]:
    return list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.is_focus_reference.is_(True))
            .order_by(desc(KnowledgeEntry.is_pinned), desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
            .limit(limit)
        )
    )


def _resolve_session(plan: FocusAssistantPlanRequest | FocusAssistantExecuteRequest, latest: FocusSession | None) -> FocusSession | None:
    if plan.session_id and latest and latest.id == plan.session_id:
        return latest
    return latest


def _summary_text(goal_text: str | None, duration_minutes: int | None, focus_reference_count: int) -> str:
    goal = (goal_text or "").strip() or "当前主任务"
    duration = duration_minutes or 25
    if focus_reference_count > 0:
      return f"围绕“{goal}”安排一轮 {duration} 分钟的专注支持，优先整理回读清单、会后总结和 Focus 参考材料。"
    return f"围绕“{goal}”安排一轮 {duration} 分钟的专注支持，优先产出回读清单与会后总结。"


def _build_guardrails() -> list[str]:
    return [
        "仅提供导出、整理、摘要和参考材料打包，不自动代发个人微信私聊消息。",
        "所有执行动作默认生成结果草稿或文件，由用户自行确认后继续使用。",
        "Focus Assistant 默认优先走腾讯官方 CodeBuddy CLI / Gateway；若官方通道不可用，再回退到本地兼容层。",
    ]


def _maybe_delegate_to_official_codebuddy(
    db: Session,
    *,
    action: FocusAssistantActionOut,
    task,
    output_language: str,
) -> None:
    requested_mode = str(settings.workbuddy_mode or "auto").strip().lower()
    if requested_mode == "local":
        return
    output_payload = dict(task.output_payload) if isinstance(task.output_payload, dict) else {}
    content_preview = ""
    if isinstance(output_payload, dict):
        content_preview = str(
            output_payload.get("content")
            or output_payload.get("markdown")
            or output_payload.get("text")
            or ""
        ).strip()
    prompt = "\n".join(
        [
            "你是腾讯官方 CodeBuddy/WorkBuddy 执行桥的结果整理助手。",
            "请基于以下 Focus Assistant 动作和已生成结果，输出一段不超过 180 字的执行确认摘要，并给出 2 条后续建议。",
            f"动作标题：{action.title}",
            f"动作描述：{action.description}",
            f"交接提示：{action.handoff_prompt or ''}",
            f"输出语言：{output_language}",
            "已生成结果摘要：",
            content_preview[:2000],
        ]
    ).strip()
    cli_result = run_codebuddy_prompt(
        prompt,
        command=settings.workbuddy_official_cli_command,
        timeout_seconds=settings.workbuddy_official_cli_timeout_seconds,
        output_format="text",
    )
    output_payload["workbuddy_bridge"] = {
        "provider": "tencent_codebuddy_cli" if cli_result.ok else "local_adapter",
        "requested_mode": requested_mode,
        "official_cli_used": cli_result.ok,
        "official_cli_authenticated": cli_result.authenticated,
        "detail": cli_result.detail,
        "summary": cli_result.output if cli_result.ok else None,
    }
    task.output_payload = dict(output_payload)
    db.add(task)
    db.commit()
    db.refresh(task)


def build_focus_assistant_plan(db: Session, payload: FocusAssistantPlanRequest) -> FocusAssistantPlanOut:
    latest_session = _load_latest_session(db)
    session = _resolve_session(payload, latest_session)
    output_language = normalize_output_language(
        payload.output_language or (session.output_language if session else None)
    )
    goal_text = (payload.goal_text or (session.goal_text if session else "") or "").strip() or None
    duration_minutes = payload.duration_minutes or (session.duration_minutes if session else None)
    focus_references = _load_focus_references(db)

    actions: list[FocusAssistantActionOut] = [
        FocusAssistantActionOut(
            key="reading_digest",
            title="整理稍后读清单",
            description="把最近内容压成一份便于回看的阅读清单。",
            task_type="export_reading_list",
            steps=["汇总最近内容", "按当前输出语言整理清单", "返回 Markdown 结果"],
            handoff_prompt="请把最近内容整理成一份可快速扫读的阅读清单。",
        ),
        FocusAssistantActionOut(
            key="session_markdown_summary",
            title="生成专注总结",
            description="基于最近一次 Focus Session 输出 Markdown 总结。",
            task_type="export_markdown_summary",
            session_required=True,
            available=bool(session),
            reason=None if session else "需要先完成至少一轮 Focus Session。",
            steps=["读取最近一次专注会话", "汇总新增内容与建议深读项", "生成 Markdown 总结"],
            handoff_prompt="请基于最近一次专注会话生成一份结构清楚的 Markdown 总结。",
        ),
        FocusAssistantActionOut(
            key="todo_draft",
            title="生成待办草稿",
            description="把最近一次 Focus Session 输出成后续行动草稿。",
            task_type="export_todo_draft",
            session_required=True,
            available=bool(session),
            reason=None if session else "需要先完成至少一轮 Focus Session。",
            steps=["读取最近一次专注会话", "提炼后续行动项", "生成待办草稿"],
            handoff_prompt="请基于最近一次专注会话生成后续待办草稿。",
        ),
        FocusAssistantActionOut(
            key="focus_reference_bundle",
            title="导出 Focus 参考材料",
            description="把当前 Focus 参考卡片打包成一份 Markdown，便于边工作边查阅。",
            task_type="export_knowledge_bundle_markdown",
            available=bool(focus_references),
            reason=None if focus_references else "当前还没有 Focus 参考卡片。",
            steps=["读取已标记的 Focus 参考卡片", "按当前输出语言打包导出", "返回单份 Markdown 文件"],
            handoff_prompt="请把本次 Focus 参考卡片合并成一份结构化材料，方便工作时查阅。",
        ),
    ]
    blocked_actions = [
        FocusAssistantActionOut(
            key="personal_wechat_auto_send",
            title="个人微信自动代发",
            description="自动读取并回复个人微信好友消息。",
            available=False,
            reason="当前版本不支持个人微信私聊自动代发，这属于高风险能力。",
            session_required=False,
        )
    ]

    return FocusAssistantPlanOut(
        goal_text=goal_text,
        duration_minutes=duration_minutes,
        output_language=output_language,
        latest_session_id=session.id if session else None,
        latest_session_status=session.status if session else None,
        focus_reference_count=len(focus_references),
        focus_reference_ids=[entry.id for entry in focus_references],
        focus_reference_titles=[entry.title for entry in focus_references],
        summary=_summary_text(goal_text, duration_minutes, len(focus_references)),
        actions=actions,
        blocked_actions=blocked_actions,
        guardrails=_build_guardrails(),
    )


def _find_action(actions: Iterable[FocusAssistantActionOut], key: str) -> FocusAssistantActionOut | None:
    for action in actions:
        if action.key == key:
            return action
    return None


def execute_focus_assistant_action(db: Session, payload: FocusAssistantExecuteRequest):
    plan = build_focus_assistant_plan(
        db,
        FocusAssistantPlanRequest(
            goal_text=payload.goal_text,
            duration_minutes=payload.duration_minutes,
            session_id=payload.session_id,
            output_language=payload.output_language,
        ),
    )
    action = _find_action(plan.actions + plan.blocked_actions, payload.action_key)
    if not action:
        raise ValueError("Unsupported action")
    if not action.available or not action.task_type:
        raise ValueError(action.reason or "This action is not available")

    session_id = payload.session_id or plan.latest_session_id
    input_payload: dict[str, object] = {"output_language": plan.output_language}
    if action.key == "focus_reference_bundle":
        input_payload["entry_ids"] = [str(entry_id) for entry_id in plan.focus_reference_ids]
        input_payload["title"] = "Focus 参考材料"

    task = create_and_execute_task(
        db,
        user_id=settings.single_user_id,
        task_type=action.task_type,
        session_id=session_id if action.session_required else None,
        input_payload=input_payload,
    )
    if payload.channel == "workbuddy":
        _maybe_delegate_to_official_codebuddy(
            db,
            action=action,
            task=task,
            output_language=plan.output_language,
        )
    return action, task
