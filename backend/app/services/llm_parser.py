from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, Field, ValidationError

from app.services.language import localized_text


class SummarizeResult(BaseModel):
    display_title: str = ""
    short_summary: str = "暂无摘要。"
    long_summary: str = "暂无长摘要。"
    key_points: list[str] = Field(default_factory=list)


class TagsResult(BaseModel):
    tags: list[str] = Field(default_factory=lambda: ["待分类"])


class ScoreResult(BaseModel):
    score_value: float = 2.5
    action_suggestion: str = "later"
    recommendation_reason: list[str] = Field(default_factory=lambda: ["解析失败，使用默认推荐。"])
    content_density: str = "medium"
    novelty_level: str = "medium"


class SessionSummaryResult(BaseModel):
    summary_text: str = "本次专注已完成，建议先处理高相关内容，再处理次要内容。"


class InsightResult(BaseModel):
    insight_title: str = "专业解读"
    expert_take: str = "当前暂无可用解读，建议稍后重试。"
    key_signals: list[str] = Field(default_factory=list)
    knowledge_note: str = "当前暂无可写入知识库的内容摘要。"


class ResearchReportResult(BaseModel):
    report_title: str = "研究主题待确认"
    executive_summary: str = "当前证据不足，建议补充更多来源后再形成正式判断。"
    consulting_angle: str = "可用于初步行业判断、方案方向梳理和销售跟进准备。"
    industry_brief: list[str] = Field(default_factory=list)
    key_signals: list[str] = Field(default_factory=list)
    policy_and_leadership: list[str] = Field(default_factory=list)
    commercial_opportunities: list[str] = Field(default_factory=list)
    solution_design: list[str] = Field(default_factory=list)
    sales_strategy: list[str] = Field(default_factory=list)
    bidding_strategy: list[str] = Field(default_factory=list)
    outreach_strategy: list[str] = Field(default_factory=list)
    ecosystem_strategy: list[str] = Field(default_factory=list)
    target_accounts: list[str] = Field(default_factory=list)
    target_departments: list[str] = Field(default_factory=list)
    public_contact_channels: list[str] = Field(default_factory=list)
    account_team_signals: list[str] = Field(default_factory=list)
    budget_signals: list[str] = Field(default_factory=list)
    project_distribution: list[str] = Field(default_factory=list)
    strategic_directions: list[str] = Field(default_factory=list)
    tender_timeline: list[str] = Field(default_factory=list)
    leadership_focus: list[str] = Field(default_factory=list)
    ecosystem_partners: list[str] = Field(default_factory=list)
    competitor_profiles: list[str] = Field(default_factory=list)
    benchmark_cases: list[str] = Field(default_factory=list)
    flagship_products: list[str] = Field(default_factory=list)
    key_people: list[str] = Field(default_factory=list)
    five_year_outlook: list[str] = Field(default_factory=list)
    client_peer_moves: list[str] = Field(default_factory=list)
    winner_peer_moves: list[str] = Field(default_factory=list)
    competition_analysis: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ResearchStrategyRefinementResult(BaseModel):
    report_title: str = ""
    executive_summary: str = ""
    consulting_angle: str = ""


class ResearchStrategyScopePlanResult(BaseModel):
    locked_regions: list[str] = Field(default_factory=list)
    locked_industries: list[str] = Field(default_factory=list)
    locked_clients: list[str] = Field(default_factory=list)
    company_anchors: list[str] = Field(default_factory=list)
    must_include_terms: list[str] = Field(default_factory=list)
    must_exclude_terms: list[str] = Field(default_factory=list)
    query_expansions: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _extract_json_block(raw_text: str) -> str | None:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return raw_text[start : end + 1]


def safe_parse_json(raw_text: str, schema: type[SchemaT], fallback: SchemaT) -> SchemaT:
    payload: object

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        candidate = _extract_json_block(raw_text)
        if not candidate:
            return fallback
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            return fallback

    if not isinstance(payload, dict):
        return fallback

    try:
        return schema.model_validate(payload)
    except ValidationError:
        return fallback


def _fallback_summarize(output_language: str) -> SummarizeResult:
    return SummarizeResult(
        display_title=localized_text(
            output_language,
            {
                "zh-CN": "内容摘要待生成",
                "zh-TW": "內容摘要待生成",
                "en": "Summary Pending",
                "ja": "要約生成待ち",
                "ko": "요약 생성 대기",
            },
            "内容摘要待生成",
        ),
        short_summary=localized_text(
            output_language,
            {
                "zh-CN": "暂无摘要。",
                "zh-TW": "暫無摘要。",
                "en": "Summary is not available yet.",
                "ja": "要約はまだ利用できません。",
                "ko": "요약을 아직 사용할 수 없습니다.",
            },
            "暂无摘要。",
        ),
        long_summary=localized_text(
            output_language,
            {
                "zh-CN": "暂无长摘要。",
                "zh-TW": "暫無長摘要。",
                "en": "Detailed summary is not available yet.",
                "ja": "詳細要約はまだ利用できません。",
                "ko": "상세 요약을 아직 사용할 수 없습니다.",
            },
            "暂无长摘要。",
        ),
        key_points=[],
    )


def _fallback_tags(output_language: str) -> TagsResult:
    return TagsResult(
        tags=[
            localized_text(
                output_language,
                {
                    "zh-CN": "待分类",
                    "zh-TW": "待分類",
                    "en": "Uncategorized",
                    "ja": "未分類",
                    "ko": "미분류",
                },
                "待分类",
            )
        ]
    )


def _fallback_score(output_language: str) -> ScoreResult:
    return ScoreResult(
        score_value=2.5,
        action_suggestion="later",
        recommendation_reason=[
            localized_text(
                output_language,
                {
                    "zh-CN": "解析失败，使用默认推荐。",
                    "zh-TW": "解析失敗，使用預設推薦。",
                    "en": "Parsing failed, using default recommendation.",
                    "ja": "解析に失敗したため、既定の推薦を使用しました。",
                    "ko": "파싱에 실패하여 기본 추천을 사용했습니다.",
                },
                "解析失败，使用默认推荐。",
            )
        ],
        content_density="medium",
        novelty_level="medium",
    )


def _fallback_session_summary(output_language: str) -> SessionSummaryResult:
    return SessionSummaryResult(
        summary_text=localized_text(
            output_language,
            {
                "zh-CN": "本次专注已完成，建议先处理高相关内容，再处理次要内容。",
                "zh-TW": "本次專注已完成，建議先處理高相關內容，再處理次要內容。",
                "en": "The focus session is complete. Review high-priority items first, then secondary items.",
                "ja": "本セッションは完了しました。まず優先度の高い項目から確認し、その後に次点項目を処理してください。",
                "ko": "이번 집중 세션이 완료되었습니다. 우선순위가 높은 항목부터 확인한 뒤 나머지를 처리하세요.",
            },
            "本次专注已完成，建议先处理高相关内容，再处理次要内容。",
        )
    )


def _fallback_insight(output_language: str) -> InsightResult:
    return InsightResult(
        insight_title=localized_text(
            output_language,
            {
                "zh-CN": "专业解读待生成",
                "zh-TW": "專業解讀待生成",
                "en": "Insight Pending",
                "ja": "解説生成待ち",
                "ko": "전문 해석 대기",
            },
            "专业解读待生成",
        ),
        expert_take=localized_text(
            output_language,
            {
                "zh-CN": "当前暂无可用解读，建议稍后重试或先查看详情页。",
                "zh-TW": "目前暫無可用解讀，建議稍後重試或先查看詳情頁。",
                "en": "Insight is not available yet. Try again later or open the detail page first.",
                "ja": "現時点では解説を利用できません。後でもう一度試すか、詳細ページを先に確認してください。",
                "ko": "현재 해석을 불러올 수 없습니다. 잠시 후 다시 시도하거나 상세 페이지를 먼저 확인하세요.",
            },
            "当前暂无可用解读，建议稍后重试或先查看详情页。",
        ),
        key_signals=[],
        knowledge_note=localized_text(
            output_language,
            {
                "zh-CN": "暂无知识库笔记。",
                "zh-TW": "暫無知識庫筆記。",
                "en": "No knowledge note available yet.",
                "ja": "まだナレッジノートはありません。",
                "ko": "아직 지식 노트가 없습니다.",
            },
            "暂无知识库笔记。",
        ),
    )


def _fallback_research_report(output_language: str) -> ResearchReportResult:
    return ResearchReportResult(
        report_title=localized_text(
            output_language,
            {
                "zh-CN": "研究主题待确认",
                "zh-TW": "研究主題待確認",
                "en": "Research Topic Pending",
                "ja": "調査テーマ確認待ち",
                "ko": "리서치 주제 확인 대기",
            },
            "研究主题待确认",
        ),
        executive_summary=localized_text(
            output_language,
            {
                "zh-CN": "当前检索证据不足，系统已生成一份保守版分析框架。建议补充更明确的关键词、行业范围或项目方向后再次生成。",
                "zh-TW": "目前檢索證據不足，系統已生成一份保守版分析框架。建議補充更明確的關鍵詞、產業範圍或專案方向後再次生成。",
                "en": "Evidence is currently limited. A conservative research scaffold has been generated. Add clearer keywords, sector scope, or project direction and run again.",
                "ja": "現時点では根拠が不足しています。保守的な調査フレームのみ生成しました。キーワードや業界範囲、案件方向を具体化して再実行してください。",
                "ko": "현재 근거가 부족해 보수적인 리서치 프레임만 생성했습니다. 키워드, 산업 범위, 프로젝트 방향을 더 구체화해 다시 실행하세요.",
            },
            "当前检索证据不足，系统已生成一份保守版分析框架。",
        ),
        consulting_angle=localized_text(
            output_language,
            {
                "zh-CN": "可先作为线索盘点底稿，用于行业判断、销售切入与投标准备。",
                "zh-TW": "可先作為線索盤點底稿，用於產業判斷、銷售切入與投標準備。",
                "en": "Use this as a first-pass working memo for market reading, sales entry points, and bidding prep.",
                "ja": "業界判断、営業の切り口、入札準備のための一次メモとして利用できます。",
                "ko": "시장 판단, 영업 진입, 입찰 준비를 위한 1차 작업 메모로 사용할 수 있습니다.",
            },
            "可先作为线索盘点底稿，用于行业判断、销售切入与投标准备。",
        ),
        industry_brief=[],
        key_signals=[],
        policy_and_leadership=[],
        commercial_opportunities=[],
        solution_design=[],
        sales_strategy=[],
        bidding_strategy=[],
        outreach_strategy=[],
        ecosystem_strategy=[],
        target_accounts=[],
        target_departments=[],
        public_contact_channels=[],
        budget_signals=[],
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=[],
        leadership_focus=[],
        ecosystem_partners=[],
        competitor_profiles=[],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        risks=[
            localized_text(
                output_language,
                {
                    "zh-CN": "当前来源数量不足，判断可能偏保守。",
                    "zh-TW": "目前來源數量不足，判斷可能偏保守。",
                    "en": "Source coverage is limited, so the analysis is intentionally conservative.",
                    "ja": "ソース数が不足しているため、分析は保守的です。",
                    "ko": "소스 수가 부족해 분석이 보수적으로 작성되었습니다.",
                },
                "当前来源数量不足，判断可能偏保守。",
            )
        ],
        next_actions=[
            localized_text(
                output_language,
                {
                    "zh-CN": "补充更具体的行业、地区、项目名称或客户类型后重试。",
                    "zh-TW": "補充更具體的產業、地區、專案名稱或客戶類型後重試。",
                    "en": "Retry with more specific sector, region, project name, or buyer profile.",
                    "ja": "業界、地域、案件名、顧客タイプを具体化して再実行してください。",
                    "ko": "산업, 지역, 프로젝트명, 고객 유형을 더 구체화해 다시 시도하세요.",
                },
                "补充更具体的行业、地区、项目名称或客户类型后重试。",
            )
        ],
    )


def parse_summarize_response(raw_text: str, *, output_language: str = "zh-CN") -> SummarizeResult:
    return safe_parse_json(raw_text, SummarizeResult, _fallback_summarize(output_language))


def parse_tags_response(raw_text: str, *, output_language: str = "zh-CN") -> TagsResult:
    return safe_parse_json(raw_text, TagsResult, _fallback_tags(output_language))


def parse_score_response(raw_text: str, *, output_language: str = "zh-CN") -> ScoreResult:
    return safe_parse_json(raw_text, ScoreResult, _fallback_score(output_language))


def parse_session_summary_response(
    raw_text: str, *, output_language: str = "zh-CN"
) -> SessionSummaryResult:
    return safe_parse_json(raw_text, SessionSummaryResult, _fallback_session_summary(output_language))


def parse_insight_response(raw_text: str, *, output_language: str = "zh-CN") -> InsightResult:
    return safe_parse_json(raw_text, InsightResult, _fallback_insight(output_language))


def parse_research_report_response(
    raw_text: str, *, output_language: str = "zh-CN"
) -> ResearchReportResult:
    return safe_parse_json(raw_text, ResearchReportResult, _fallback_research_report(output_language))


def parse_research_strategy_refine_response(raw_text: str) -> ResearchStrategyRefinementResult:
    return safe_parse_json(raw_text, ResearchStrategyRefinementResult, ResearchStrategyRefinementResult())


def parse_research_strategy_scope_response(raw_text: str) -> ResearchStrategyScopePlanResult:
    return safe_parse_json(raw_text, ResearchStrategyScopePlanResult, ResearchStrategyScopePlanResult())
