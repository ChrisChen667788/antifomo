from __future__ import annotations

from datetime import datetime, timezone
import html
import math
from base64 import b64encode

from app.models.entities import FocusSession, Item, KnowledgeEntry, WorkTask
from app.models.research_entities import ResearchWatchlistChangeEvent
from app.services.session_service import SessionMetrics
from app.services.language import localized_text, normalize_output_language
from app.schemas.research import ResearchReportDocument
from app.services.research_service import build_research_report_markdown


def _assistant_label(value: str, output_language: str) -> str:
    mapping = {
        "workbuddy": localized_text(
            output_language,
            {"zh-CN": "通过 WorkBuddy", "zh-TW": "透過 WorkBuddy", "en": "via WorkBuddy", "ja": "WorkBuddy 経由", "ko": "WorkBuddy 경유"},
            "通过 WorkBuddy",
        ),
        "direct": localized_text(
            output_language,
            {"zh-CN": "直连执行", "zh-TW": "直連執行", "en": "via direct channel", "ja": "直接実行", "ko": "직접 실행"},
            "直连执行",
        ),
    }
    return mapping.get(value, value)


def _append_assistant_section(
    lines: list[str],
    *,
    output_language: str,
    assistant_context: dict | None,
) -> None:
    if not isinstance(assistant_context, dict):
        return
    action_title = str(assistant_context.get("action_title") or "").strip()
    content = str(assistant_context.get("content") or "").strip()
    message = str(assistant_context.get("message") or "").strip()
    channel_used = str(assistant_context.get("channel_used") or "").strip()
    created_at = str(assistant_context.get("created_at") or "").strip()
    if not action_title and not content:
        return

    lines.extend(
        [
            "",
            f"## {localized_text(output_language, {'zh-CN': 'Focus Assistant 回流', 'zh-TW': 'Focus Assistant 回流', 'en': 'Focus Assistant Return', 'ja': 'Focus Assistant の結果', 'ko': 'Focus Assistant 회류'}, 'Focus Assistant 回流')}",
            f"- {localized_text(output_language, {'zh-CN': '动作', 'zh-TW': '動作', 'en': 'Action', 'ja': 'アクション', 'ko': '동작'}, '动作')}: {action_title or localized_text(output_language, {'zh-CN': '未命名动作', 'zh-TW': '未命名動作', 'en': 'Untitled action', 'ja': '無題アクション', 'ko': '이름 없는 동작'}, '未命名动作')}",
        ]
    )
    if channel_used:
        lines.append(
            f"- {localized_text(output_language, {'zh-CN': '执行通道', 'zh-TW': '執行通道', 'en': 'Channel', 'ja': '実行チャネル', 'ko': '실행 채널'}, '执行通道')}: {_assistant_label(channel_used, output_language)}"
        )
    if created_at:
        lines.append(
            f"- {localized_text(output_language, {'zh-CN': '执行时间', 'zh-TW': '執行時間', 'en': 'Run At', 'ja': '実行時刻', 'ko': '실행 시각'}, '执行时间')}: {created_at}"
        )
    if message:
        lines.append(
            f"- {localized_text(output_language, {'zh-CN': '说明', 'zh-TW': '說明', 'en': 'Note', 'ja': '補足', 'ko': '설명'}, '说明')}: {message}"
        )
    if content:
        lines.extend(["", content])


def _action_label(action: str | None, output_language: str) -> str:
    if action == "deep_read":
        return localized_text(
            output_language,
            {"zh-CN": "深读", "zh-TW": "深讀", "en": "deep read", "ja": "深読み", "ko": "정독"},
            "深读",
        )
    if action == "skip":
        return localized_text(
            output_language,
            {"zh-CN": "忽略", "zh-TW": "忽略", "en": "skip", "ja": "スキップ", "ko": "건너뛰기"},
            "忽略",
        )
    return localized_text(
        output_language,
        {"zh-CN": "稍后读", "zh-TW": "稍後讀", "en": "later", "ja": "後で読む", "ko": "나중에 읽기"},
        "稍后读",
    )


def select_summary_items(items: list[Item]) -> list[Item]:
    return [item for item in items if item.action_suggestion == "deep_read"][:10]


def select_reading_list_items(items: list[Item]) -> list[Item]:
    return [item for item in items if item.action_suggestion in {"deep_read", "later"}][:20]


def select_todo_items(items: list[Item]) -> list[Item]:
    return [item for item in items if item.action_suggestion == "deep_read"][:8]


def build_artifact_item_snapshots(items: list[Item], *, included_reason: str) -> list[dict]:
    return [
        {
            "item_id": str(item.id),
            "included_reason": included_reason,
            "title_snapshot": item.title or "未命名内容",
            "source_url_snapshot": item.source_url,
        }
        for item in items
    ]


def build_markdown_summary(
    session: FocusSession,
    metrics: SessionMetrics,
    items: list[Item],
    *,
    output_language: str | None = None,
    summary_text_override: str | None = None,
    assistant_context: dict | None = None,
) -> str:
    resolved_language = normalize_output_language(output_language or session.output_language)
    title = localized_text(
        resolved_language,
        {
            "zh-CN": "# Anti-fomo 专注总结",
            "zh-TW": "# Anti-fomo 專注總結",
            "en": "# Anti-fomo Session Summary",
            "ja": "# Anti-fomo セッション要約",
            "ko": "# Anti-fomo 세션 요약",
        },
        "# Anti-fomo Session Summary",
    )
    lines = [
        title,
        "",
        f"- {localized_text(resolved_language, {'zh-CN': '会话 ID', 'zh-TW': '工作階段 ID', 'en': 'Session ID', 'ja': 'セッション ID', 'ko': '세션 ID'}, 'Session ID')}: {session.id}",
        f"- {localized_text(resolved_language, {'zh-CN': '目标', 'zh-TW': '目標', 'en': 'Goal', 'ja': '目標', 'ko': '목표'}, '目标')}: "
        f"{session.goal_text or localized_text(resolved_language, {'zh-CN': '未设置', 'zh-TW': '未設定', 'en': 'Not set', 'ja': '未設定', 'ko': '미설정'}, '未设置')}",
        f"- {localized_text(resolved_language, {'zh-CN': '时长', 'zh-TW': '時長', 'en': 'Duration', 'ja': '時間', 'ko': '시간'}, '时长')}: "
        f"{session.duration_minutes} {localized_text(resolved_language, {'zh-CN': '分钟', 'zh-TW': '分鐘', 'en': 'minutes', 'ja': '分', 'ko': '분'}, '分钟')}",
        f"- {localized_text(resolved_language, {'zh-CN': '新增内容', 'zh-TW': '新增內容', 'en': 'New items', 'ja': '新規項目', 'ko': '신규 항목'}, '新增内容')}: {metrics.new_content_count}",
        f"- {localized_text(resolved_language, {'zh-CN': '深读', 'zh-TW': '深讀', 'en': 'Deep read', 'ja': '深読み', 'ko': '정독'}, '深读')}: {metrics.deep_read_count}",
        f"- {localized_text(resolved_language, {'zh-CN': '稍后读', 'zh-TW': '稍後讀', 'en': 'Later', 'ja': '後で読む', 'ko': '나중에 읽기'}, '稍后读')}: {metrics.later_count}",
        f"- {localized_text(resolved_language, {'zh-CN': '可忽略', 'zh-TW': '可忽略', 'en': 'Skip', 'ja': 'スキップ', 'ko': '건너뛰기'}, '可忽略')}: {metrics.skip_count}",
        "",
        f"## {localized_text(resolved_language, {'zh-CN': '深读建议', 'zh-TW': '深讀建議', 'en': 'Deep Read Recommendations', 'ja': '深読み推奨', 'ko': '정독 추천'}, '深读建议')}",
    ]

    deep_items = select_summary_items(items)
    if deep_items:
        for idx, item in enumerate(deep_items, start=1):
            title = item.title or localized_text(
                resolved_language,
                {'zh-CN': '未命名内容', 'zh-TW': '未命名內容', 'en': 'Untitled item', 'ja': '無題コンテンツ', 'ko': '제목 없음'},
                '未命名内容',
            )
            if item.source_url:
                lines.append(f"{idx}. [{title}]({item.source_url})")
            else:
                lines.append(f"{idx}. {title}")
    else:
        lines.append(
            f"1. {localized_text(resolved_language, {'zh-CN': '本轮无深读项', 'zh-TW': '本輪無深讀項', 'en': 'No deep-read items this round', 'ja': '今回の深読み項目はありません', 'ko': '이번 라운드 정독 항목 없음'}, '本轮无深读项')}"
        )

    lines.extend(
        [
            "",
            f"## {localized_text(resolved_language, {'zh-CN': '系统总结', 'zh-TW': '系統總結', 'en': 'System Summary', 'ja': 'システム要約', 'ko': '시스템 요약'}, '系统总结')}",
            summary_text_override
            or session.summary_text
            or localized_text(
                resolved_language,
                {
                    "zh-CN": "本轮专注已完成，建议先处理深读项。",
                    "zh-TW": "本輪專注已完成，建議先處理深讀項。",
                    "en": "Focus block completed. Start with deep-read items first.",
                    "ja": "集中セッションは完了しました。まず深読み項目から処理してください。",
                    "ko": "집중 세션이 완료되었습니다. 먼저 정독 항목부터 처리하세요.",
                },
                "本轮专注已完成，建议先处理深读项。",
            ),
        ]
    )
    _append_assistant_section(lines, output_language=resolved_language, assistant_context=assistant_context)
    return "\n".join(lines)


def build_reading_list(
    items: list[Item],
    *,
    output_language: str = "zh-CN",
    assistant_context: dict | None = None,
) -> str:
    resolved_language = normalize_output_language(output_language)
    candidate = select_reading_list_items(items)
    lines = [
        f"# {localized_text(resolved_language, {'zh-CN': '稍后读清单', 'zh-TW': '稍後讀清單', 'en': 'Reading List', 'ja': '後で読むリスト', 'ko': '읽기 목록'}, '稍后读清单')}",
        "",
    ]
    if not candidate:
        lines.append(
            f"- {localized_text(resolved_language, {'zh-CN': '暂无推荐阅读内容', 'zh-TW': '暫無推薦閱讀內容', 'en': 'No recommended items yet', 'ja': '推奨読書項目はありません', 'ko': '추천 읽기 항목이 없습니다'}, '暂无推荐阅读内容')}"
        )
        return "\n".join(lines)

    for idx, item in enumerate(candidate[:20], start=1):
        action = _action_label(item.action_suggestion, resolved_language)
        title = item.title or localized_text(
            resolved_language,
            {'zh-CN': '未命名内容', 'zh-TW': '未命名內容', 'en': 'Untitled item', 'ja': '無題コンテンツ', 'ko': '제목 없음'},
            '未命名内容',
        )
        if item.source_url:
            lines.append(f"{idx}. [{action}] [{title}]({item.source_url})")
        else:
            lines.append(f"{idx}. [{action}] {title}")
    _append_assistant_section(lines, output_language=resolved_language, assistant_context=assistant_context)
    return "\n".join(lines)


def build_todo_draft(
    session: FocusSession,
    items: list[Item],
    *,
    output_language: str | None = None,
    assistant_context: dict | None = None,
) -> str:
    resolved_language = normalize_output_language(output_language or session.output_language)
    lines = [
        f"# {localized_text(resolved_language, {'zh-CN': '待办草稿', 'zh-TW': '待辦草稿', 'en': 'Todo Draft', 'ja': 'TODO 下書き', 'ko': '할 일 초안'}, '待办草稿')}",
        "",
        f"- {localized_text(resolved_language, {'zh-CN': '本轮目标', 'zh-TW': '本輪目標', 'en': 'Current goal', 'ja': '今回の目標', 'ko': '이번 목표'}, '本轮目标')}："
        f"{session.goal_text or localized_text(resolved_language, {'zh-CN': '未设置', 'zh-TW': '未設定', 'en': 'Not set', 'ja': '未設定', 'ko': '미설정'}, '未设置')}",
        f"- {localized_text(resolved_language, {'zh-CN': '建议优先顺序：先深读，后整理，最后归档', 'zh-TW': '建議優先順序：先深讀，後整理，最後歸檔', 'en': 'Suggested order: deep read -> organize -> archive', 'ja': '推奨順序: 深読み -> 整理 -> アーカイブ', 'ko': '권장 순서: 정독 -> 정리 -> 보관'}, '建议优先顺序：先深读，后整理，最后归档')}",
        "",
        f"## {localized_text(resolved_language, {'zh-CN': '待办项', 'zh-TW': '待辦項', 'en': 'Todo Items', 'ja': 'TODO 項目', 'ko': '할 일 항목'}, '待办项')}",
    ]

    deep_items = select_todo_items(items)
    if not deep_items:
        lines.append(
            f"- [ ] {localized_text(resolved_language, {'zh-CN': '复盘本轮输入内容，确认下一轮关注主题', 'zh-TW': '回顧本輪輸入內容，確認下一輪關注主題', 'en': 'Review this round of items and define next focus topics', 'ja': '今回の入力内容を振り返り、次回の注目テーマを決める', 'ko': '이번 입력 내용을 복기하고 다음 집중 주제를 정하기'}, '复盘本轮输入内容，确认下一轮关注主题')}"
        )
        return "\n".join(lines)

    for item in deep_items:
        source_suffix = f"（{item.source_url.strip()}）" if item.source_url and item.source_url.strip() else ""
        lines.append(
            f"- [ ] {localized_text(resolved_language, {'zh-CN': '阅读', 'zh-TW': '閱讀', 'en': 'Read', 'ja': '読む', 'ko': '읽기'}, '阅读')} "
            f"《{item.title or localized_text(resolved_language, {'zh-CN': '未命名内容', 'zh-TW': '未命名內容', 'en': 'Untitled item', 'ja': '無題コンテンツ', 'ko': '제목 없음'}, '未命名内容')}》"
            f"{localized_text(resolved_language, {'zh-CN': '并记录 3 条要点', 'zh-TW': '並記錄 3 條要點', 'en': 'and capture 3 key points', 'ja': 'の要点を3つ記録する', 'ko': '후 핵심 포인트 3개 기록'}, '并记录 3 条要点')}"
            f"{source_suffix}"
        )
    lines.append(
        f"- [ ] {localized_text(resolved_language, {'zh-CN': '汇总关键结论并同步到知识库', 'zh-TW': '彙總關鍵結論並同步到知識庫', 'en': 'Consolidate key conclusions into your knowledge base', 'ja': '重要な結論をまとめてナレッジベースへ反映する', 'ko': '핵심 결론을 정리해 지식베이스에 반영'}, '汇总关键结论并同步到知识库')}"
    )
    _append_assistant_section(lines, output_language=resolved_language, assistant_context=assistant_context)
    return "\n".join(lines)


def build_knowledge_markdown(
    entry: KnowledgeEntry,
    *,
    output_language: str = "zh-CN",
) -> tuple[str, str]:
    resolved_language = normalize_output_language(output_language)
    title = (entry.title or "Knowledge Card").strip()
    filename_seed = "".join(ch for ch in title if ch.isalnum() or ch in {" ", "-", "_"}).strip().replace(" ", "_")
    if not filename_seed:
        filename_seed = "knowledge-card"
    filename = f"{filename_seed[:48]}.md"
    lines = [
        f"# {title}",
        "",
        f"- {localized_text(resolved_language, {'zh-CN': '来源', 'zh-TW': '來源', 'en': 'Source', 'ja': 'ソース', 'ko': '출처'}, '来源')}: "
        f"{entry.source_domain or localized_text(resolved_language, {'zh-CN': '未知来源', 'zh-TW': '未知來源', 'en': 'Unknown source', 'ja': '不明なソース', 'ko': '알 수 없는 출처'}, '未知来源')}",
        f"- {localized_text(resolved_language, {'zh-CN': '创建时间', 'zh-TW': '建立時間', 'en': 'Created At', 'ja': '作成日時', 'ko': '생성 시각'}, '创建时间')}: {entry.created_at.isoformat()}",
    ]
    if entry.updated_at:
        lines.append(
            f"- {localized_text(resolved_language, {'zh-CN': '最近更新', 'zh-TW': '最近更新', 'en': 'Updated At', 'ja': '更新日時', 'ko': '최근 업데이트'}, '最近更新')}: {entry.updated_at.isoformat()}"
        )
    if entry.collection_name:
        lines.append(
            f"- {localized_text(resolved_language, {'zh-CN': '分组', 'zh-TW': '分組', 'en': 'Collection', 'ja': 'グループ', 'ko': '그룹'}, '分组')}: {entry.collection_name}"
        )
    if entry.is_focus_reference:
        lines.append(
            f"- {localized_text(resolved_language, {'zh-CN': 'Focus 参考', 'zh-TW': 'Focus 參考', 'en': 'Focus Reference', 'ja': 'Focus 参照', 'ko': 'Focus 참조'}, 'Focus 参考')}: "
            f"{localized_text(resolved_language, {'zh-CN': '是', 'zh-TW': '是', 'en': 'Yes', 'ja': 'はい', 'ko': '예'}, '是')}"
        )
    lines.append(
        f"- {localized_text(resolved_language, {'zh-CN': '置顶', 'zh-TW': '置頂', 'en': 'Pinned', 'ja': 'ピン留め', 'ko': '고정'}, '置顶')}: "
        f"{localized_text(resolved_language, {'zh-CN': '是', 'zh-TW': '是', 'en': 'Yes', 'ja': 'はい', 'ko': '예'}, '是') if entry.is_pinned else localized_text(resolved_language, {'zh-CN': '否', 'zh-TW': '否', 'en': 'No', 'ja': 'いいえ', 'ko': '아니오'}, '否')}"
    )
    lines.extend(
        [
            "",
            f"## {localized_text(resolved_language, {'zh-CN': '卡片内容', 'zh-TW': '卡片內容', 'en': 'Card Content', 'ja': 'カード内容', 'ko': '카드 내용'}, '卡片内容')}",
            "",
            entry.content.strip(),
        ]
    )
    return filename, "\n".join(lines)


def build_knowledge_bundle_markdown(
    entries: list[KnowledgeEntry],
    *,
    output_language: str = "zh-CN",
    title: str | None = None,
) -> tuple[str, str]:
    resolved_language = normalize_output_language(output_language)
    resolved_title = (title or "").strip() or localized_text(
        resolved_language,
        {
            "zh-CN": "知识库批量导出",
            "zh-TW": "知識庫批量匯出",
            "en": "Knowledge Batch Export",
            "ja": "ナレッジ一括エクスポート",
            "ko": "지식 일괄 내보내기",
        },
        "知识库批量导出",
    )
    filename_seed = "".join(ch for ch in resolved_title if ch.isalnum() or ch in {" ", "-", "_"}).strip().replace(" ", "_")
    if not filename_seed:
        filename_seed = "knowledge-batch-export"
    filename = f"{filename_seed[:48]}.md"

    lines = [
        f"# {resolved_title}",
        "",
        f"- {localized_text(resolved_language, {'zh-CN': '卡片数量', 'zh-TW': '卡片數量', 'en': 'Card Count', 'ja': 'カード数', 'ko': '카드 수'}, '卡片数量')}: {len(entries)}",
        f"- {localized_text(resolved_language, {'zh-CN': '导出时间', 'zh-TW': '匯出時間', 'en': 'Exported At', 'ja': 'エクスポート時刻', 'ko': '내보낸 시각'}, '导出时间')}: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    for index, entry in enumerate(entries, start=1):
        entry_title = (entry.title or localized_text(
            resolved_language,
            {"zh-CN": "未命名知识卡片", "zh-TW": "未命名知識卡片", "en": "Untitled knowledge card", "ja": "無題ナレッジカード", "ko": "제목 없는 지식 카드"},
            "未命名知识卡片",
        )).strip()
        lines.extend(
            [
                f"## {index}. {entry_title}",
                "",
                f"- {localized_text(resolved_language, {'zh-CN': '来源', 'zh-TW': '來源', 'en': 'Source', 'ja': 'ソース', 'ko': '출처'}, '来源')}: "
                f"{entry.source_domain or localized_text(resolved_language, {'zh-CN': '未知来源', 'zh-TW': '未知來源', 'en': 'Unknown source', 'ja': '不明なソース', 'ko': '알 수 없는 출처'}, '未知来源')}",
                f"- {localized_text(resolved_language, {'zh-CN': '创建时间', 'zh-TW': '建立時間', 'en': 'Created At', 'ja': '作成日時', 'ko': '생성 시각'}, '创建时间')}: {entry.created_at.isoformat()}",
                f"- {localized_text(resolved_language, {'zh-CN': '置顶', 'zh-TW': '置頂', 'en': 'Pinned', 'ja': 'ピン留め', 'ko': '고정'}, '置顶')}: "
                f"{localized_text(resolved_language, {'zh-CN': '是', 'zh-TW': '是', 'en': 'Yes', 'ja': 'はい', 'ko': '예'}, '是') if entry.is_pinned else localized_text(resolved_language, {'zh-CN': '否', 'zh-TW': '否', 'en': 'No', 'ja': 'いいえ', 'ko': '아니오'}, '否')}",
                f"- {localized_text(resolved_language, {'zh-CN': 'Focus 参考', 'zh-TW': 'Focus 參考', 'en': 'Focus Reference', 'ja': 'Focus 参照', 'ko': 'Focus 참조'}, 'Focus 参考')}: "
                f"{localized_text(resolved_language, {'zh-CN': '是', 'zh-TW': '是', 'en': 'Yes', 'ja': 'はい', 'ko': '예'}, '是') if entry.is_focus_reference else localized_text(resolved_language, {'zh-CN': '否', 'zh-TW': '否', 'en': 'No', 'ja': 'いいえ', 'ko': '아니오'}, '否')}",
            ]
        )
        if entry.collection_name:
            lines.append(
                f"- {localized_text(resolved_language, {'zh-CN': '分组', 'zh-TW': '分組', 'en': 'Collection', 'ja': 'グループ', 'ko': '그룹'}, '分组')}: {entry.collection_name}"
            )
        lines.extend(
            [
                "",
                entry.content.strip(),
                "",
            ]
        )
    return filename, "\n".join(lines)


def build_research_markdown(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
) -> tuple[str, str]:
    report = ResearchReportDocument.model_validate(report_payload)
    return build_research_report_markdown(report, output_language=output_language)


def build_research_plaintext(
    report: ResearchReportDocument,
    *,
    output_language: str = "zh-CN",
) -> tuple[str, str]:
    resolved_language = normalize_output_language(output_language)
    title_seed = "".join(
        ch for ch in (report.report_title or report.keyword or "research-report") if ch.isalnum() or ch in {" ", "-", "_"}
    ).strip().replace(" ", "_")
    if not title_seed:
        title_seed = "research-report"
    filename = f"{title_seed[:48]}.txt"
    lines = [
        report.report_title,
        "",
        f"{localized_text(resolved_language, {'zh-CN': '关键词', 'zh-TW': '關鍵詞', 'en': 'Keyword'}, '关键词')}: {report.keyword}",
        f"{localized_text(resolved_language, {'zh-CN': '来源数', 'zh-TW': '來源數', 'en': 'Source Count'}, '来源数')}: {report.source_count}",
    ]
    if report.research_focus:
        lines.append(
            f"{localized_text(resolved_language, {'zh-CN': '补充关注点', 'zh-TW': '補充關注點', 'en': 'Research Focus'}, '补充关注点')}: {report.research_focus}"
        )
    if getattr(report, "generated_at", None):
        lines.append(
            f"{localized_text(resolved_language, {'zh-CN': '生成时间', 'zh-TW': '生成時間', 'en': 'Generated At'}, '生成时间')}: {getattr(report, 'generated_at')}"
        )
    lines.extend(
        [
            "",
            localized_text(resolved_language, {'zh-CN': '执行摘要', 'zh-TW': '執行摘要', 'en': 'Executive Summary'}, '执行摘要'),
            report.executive_summary,
            "",
            localized_text(resolved_language, {'zh-CN': '咨询价值', 'zh-TW': '顧問價值', 'en': 'Consulting Angle'}, '咨询价值'),
            report.consulting_angle,
        ]
    )
    for section in report.sections:
        lines.extend(["", section.title])
        lines.extend([f"- {item}" for item in section.items])
    if report.sources:
        lines.extend(
            [
                "",
                localized_text(resolved_language, {'zh-CN': '来源样本', 'zh-TW': '來源樣本', 'en': 'Source Samples'}, '来源样本'),
            ]
        )
        for index, source in enumerate(report.sources, start=1):
            lines.extend(
                [
                    "",
                    f"{index}. {source.title}",
                    f"URL: {source.url}",
                    f"Domain: {source.domain or 'web'}",
                    f"Query: {source.search_query}",
                    f"Type: {source.source_type}",
                    f"Status: {source.content_status}",
                    source.snippet,
                ]
            )
    return filename, "\n".join(lines).strip()


def build_research_word_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
) -> tuple[str, str, str]:
    report = ResearchReportDocument.model_validate(report_payload)
    resolved_language = normalize_output_language(output_language or report.output_language)
    filename_seed = "".join(
        ch for ch in (report.report_title or report.keyword or "research-report") if ch.isalnum() or ch in {" ", "-", "_"}
    ).strip().replace(" ", "_")
    if not filename_seed:
        filename_seed = "research-report"
    filename = f"{filename_seed[:48]}.doc"
    blocks: list[str] = [
        "<html><head><meta charset='utf-8' />",
        "<style>",
        "body{font-family:'PingFang SC','Microsoft YaHei',sans-serif;padding:36px;color:#0f172a;line-height:1.7;}",
        "h1{font-size:24px;margin:0 0 14px;}h2{font-size:18px;margin:22px 0 10px;}h3{font-size:15px;margin:14px 0 8px;}",
        ".meta{margin:0 0 18px;padding:14px 16px;border:1px solid #dbeafe;background:#f8fbff;border-radius:14px;}",
        ".meta p{margin:4px 0;}.section{margin-top:18px;}.section ul{margin:8px 0 0 18px;padding:0;}",
        ".source{margin-top:14px;padding:12px 14px;border:1px solid #e2e8f0;background:#fff;border-radius:12px;}",
        "</style></head><body>",
        f"<h1>{html.escape(report.report_title)}</h1>",
        "<div class='meta'>",
        f"<p><strong>{html.escape(localized_text(resolved_language, {'zh-CN': '关键词', 'zh-TW': '關鍵詞', 'en': 'Keyword'}, '关键词'))}：</strong>{html.escape(report.keyword)}</p>",
        f"<p><strong>{html.escape(localized_text(resolved_language, {'zh-CN': '来源数', 'zh-TW': '來源數', 'en': 'Source Count'}, '来源数'))}：</strong>{report.source_count}</p>",
    ]
    if report.research_focus:
        blocks.append(
            f"<p><strong>{html.escape(localized_text(resolved_language, {'zh-CN': '补充关注点', 'zh-TW': '補充關注點', 'en': 'Research Focus'}, '补充关注点'))}：</strong>{html.escape(report.research_focus)}</p>"
        )
    if getattr(report, "generated_at", None):
        blocks.append(
            f"<p><strong>{html.escape(localized_text(resolved_language, {'zh-CN': '生成时间', 'zh-TW': '生成時間', 'en': 'Generated At'}, '生成时间'))}：</strong>{html.escape(str(getattr(report, 'generated_at')))}</p>"
        )
    blocks.extend(
        [
            "</div>",
            f"<h2>{html.escape(localized_text(resolved_language, {'zh-CN': '执行摘要', 'zh-TW': '執行摘要', 'en': 'Executive Summary'}, '执行摘要'))}</h2>",
            f"<p>{html.escape(report.executive_summary)}</p>",
            f"<h2>{html.escape(localized_text(resolved_language, {'zh-CN': '咨询价值', 'zh-TW': '顧問價值', 'en': 'Consulting Angle'}, '咨询价值'))}</h2>",
            f"<p>{html.escape(report.consulting_angle)}</p>",
        ]
    )
    if report.query_plan:
        blocks.append(
            f"<h2>{html.escape(localized_text(resolved_language, {'zh-CN': '检索路径', 'zh-TW': '檢索路徑', 'en': 'Search Plan'}, '检索路径'))}</h2><ul>"
        )
        blocks.extend([f"<li>{html.escape(query)}</li>" for query in report.query_plan])
        blocks.append("</ul>")
    for section in report.sections:
        blocks.append(f"<div class='section'><h2>{html.escape(section.title)}</h2><ul>")
        blocks.extend([f"<li>{html.escape(item)}</li>" for item in section.items])
        blocks.append("</ul></div>")
    if report.sources:
        blocks.append(
            f"<h2>{html.escape(localized_text(resolved_language, {'zh-CN': '来源样本', 'zh-TW': '來源樣本', 'en': 'Source Samples'}, '来源样本'))}</h2>"
        )
        for index, source in enumerate(report.sources, start=1):
            blocks.extend(
                [
                    "<div class='source'>",
                    f"<h3>{index}. {html.escape(source.title)}</h3>",
                    f"<p><strong>URL:</strong> {html.escape(source.url)}</p>",
                    f"<p><strong>Domain:</strong> {html.escape(source.domain or 'web')}</p>",
                    f"<p><strong>Query:</strong> {html.escape(source.search_query)}</p>",
                    f"<p><strong>Type:</strong> {html.escape(source.source_type)}</p>",
                    f"<p><strong>Status:</strong> {html.escape(source.content_status)}</p>",
                    f"<p>{html.escape(source.snippet)}</p>",
                    "</div>",
                ]
            )
    blocks.append("</body></html>")
    return filename, "\n".join(blocks), "application/msword"


def _pdf_hex(text: str) -> str:
    encoded = text.encode("utf-16-be")
    return encoded.hex().upper()


def _pdf_wrap_line(text: str, limit: int = 30) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return [""]
    pieces: list[str] = []
    start = 0
    while start < len(stripped):
        pieces.append(stripped[start:start + limit])
        start += limit
    return pieces or [stripped]


def _build_simple_pdf(lines: list[str]) -> bytes:
    page_height = 842
    start_x = 48
    start_y = 794
    line_height = 18
    max_lines_per_page = 38
    wrapped_lines: list[str] = []
    for line in lines:
        wrapped_lines.extend(_pdf_wrap_line(line))
    if not wrapped_lines:
        wrapped_lines = [""]
    total_pages = max(1, math.ceil(len(wrapped_lines) / max_lines_per_page))
    objects: list[bytes] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    page_object_numbers = []
    content_object_numbers = []
    next_object_number = 5
    for _ in range(total_pages):
        page_object_numbers.append(next_object_number)
        content_object_numbers.append(next_object_number + 1)
        next_object_number += 2

    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects.append(f"<< /Type /Pages /Count {total_pages} /Kids [{kids}] >>".encode("utf-8"))
    objects.append(
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [4 0 R] >>"
    )
    objects.append(
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /DW 1000 >>"
    )

    for page_index in range(total_pages):
        page_lines = wrapped_lines[page_index * max_lines_per_page:(page_index + 1) * max_lines_per_page]
        stream_lines = ["BT", "/F1 11 Tf", f"{line_height} TL", f"{start_x} {start_y} Td"]
        first = True
        for line in page_lines:
            if first:
                stream_lines.append(f"<{_pdf_hex(line)}> Tj")
                first = False
            else:
                stream_lines.append("T*")
                stream_lines.append(f"<{_pdf_hex(line)}> Tj")
        stream_lines.append("ET")
        stream_bytes = "\n".join(stream_lines).encode("utf-8")
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 {page_height}] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_object_numbers[page_index]} 0 R >>"
        ).encode("utf-8")
        content_obj = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("utf-8")
            + stream_bytes
            + b"\nendstream"
        )
        objects.append(page_obj)
        objects.append(content_obj)

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("utf-8"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("utf-8"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("utf-8")
    )
    return bytes(output)


def build_research_pdf_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
) -> tuple[str, str, str, str]:
    report = ResearchReportDocument.model_validate(report_payload)
    resolved_language = normalize_output_language(output_language or report.output_language)
    filename_seed = "".join(
        ch for ch in (report.report_title or report.keyword or "research-report") if ch.isalnum() or ch in {" ", "-", "_"}
    ).strip().replace(" ", "_")
    if not filename_seed:
        filename_seed = "research-report"
    filename = f"{filename_seed[:48]}.pdf"
    _, plain_text = build_research_plaintext(report, output_language=resolved_language)
    pdf_bytes = _build_simple_pdf(plain_text.splitlines())
    return filename, plain_text, b64encode(pdf_bytes).decode("ascii"), "application/pdf"


def build_exec_brief(
    *,
    output_language: str = "zh-CN",
    report_payload: dict | None = None,
    items: list[Item] | None = None,
) -> str:
    resolved_language = normalize_output_language(output_language)
    lines = [
        f"# {localized_text(resolved_language, {'zh-CN': '老板简报', 'zh-TW': '老闆簡報', 'en': 'Executive Brief'}, '老板简报')}",
        "",
    ]
    if isinstance(report_payload, dict):
        report = ResearchReportDocument.model_validate(report_payload)
        lines.extend(
            [
                f"- {localized_text(resolved_language, {'zh-CN': '专题', 'zh-TW': '專題', 'en': 'Topic'}, '专题')}: {report.report_title}",
                f"- {localized_text(resolved_language, {'zh-CN': '一句话结论', 'zh-TW': '一句話結論', 'en': 'Headline'}, '一句话结论')}: {report.executive_summary}",
                "",
                f"## {localized_text(resolved_language, {'zh-CN': '需要老板知道的 3 点', 'zh-TW': '需要老闆知道的 3 點', 'en': 'Top 3 Takeaways'}, '需要老板知道的 3 点')}",
            ]
        )
        takeaways = (report.strategic_directions or report.leadership_focus or report.budget_signals or report.tender_timeline)[:3]
        lines.extend([f"- {row}" for row in takeaways] or ["- 暂无更多结构化结论"])
        lines.extend(["", "## 关键来源"])
        lines.extend([f"- [{source.title}]({source.url})" for source in report.sources[:3]] or ["- 暂无来源"])
        return "\n".join(lines)

    latest_items = items or []
    lines.extend(
        [
            f"- {localized_text(resolved_language, {'zh-CN': '今日重点', 'zh-TW': '今日重點', 'en': 'Today'}, '今日重点')}: {len(latest_items[:5])}",
            "",
        ]
    )
    for item in latest_items[:5]:
        lines.append(f"- {item.title or '未命名内容'}：{item.short_summary or item.source_url or ''}")
    return "\n".join(lines)


def build_sales_brief(
    *,
    output_language: str = "zh-CN",
    report_payload: dict | None = None,
    items: list[Item] | None = None,
) -> str:
    resolved_language = normalize_output_language(output_language)
    lines = [
        f"# {localized_text(resolved_language, {'zh-CN': '销售拜访 Brief', 'zh-TW': '銷售拜訪 Brief', 'en': 'Sales Brief'}, '销售拜访 Brief')}",
        "",
    ]
    if isinstance(report_payload, dict):
        report = ResearchReportDocument.model_validate(report_payload)
        lines.extend(
            [
                f"- {localized_text(resolved_language, {'zh-CN': '专题', 'zh-TW': '專題', 'en': 'Topic'}, '专题')}: {report.keyword}",
                "",
                "## 建议优先接触对象",
            ]
        )
        targets = (report.target_accounts or report.public_contact_channels or report.account_team_signals)[:4]
        lines.extend([f"- {row}" for row in targets] or ["- 暂无明确甲方对象"])
        lines.extend(["", "## 切入话术 / 证据"])
        evidence = (report.budget_signals or report.tender_timeline or report.strategic_directions)[:4]
        lines.extend([f"- {row}" for row in evidence] or ["- 暂无明确销售切入证据"])
        return "\n".join(lines)

    for item in (items or [])[:5]:
        lines.append(f"- {item.title or '未命名内容'}：{item.short_summary or item.source_url or ''}")
    return "\n".join(lines)


def build_outreach_draft(
    *,
    output_language: str = "zh-CN",
    report_payload: dict | None = None,
) -> str:
    resolved_language = normalize_output_language(output_language)
    if isinstance(report_payload, dict):
        report = ResearchReportDocument.model_validate(report_payload)
        hook = (report.strategic_directions or report.budget_signals or report.tender_timeline or ["最近公开信息里看到你们正在推进相关项目。"])[0]
        ask = (report.public_contact_channels or report.target_departments or ["是否方便安排 20 分钟沟通？"])[0]
        return "\n".join(
            [
                f"# {localized_text(resolved_language, {'zh-CN': '外联草稿', 'zh-TW': '外聯草稿', 'en': 'Outreach Draft'}, '外联草稿')}",
                "",
                f"你好，最近看到 {report.keyword} 相关公开动态，{hook}",
                "",
                f"我们这边近期也在跟进类似场景，想和你交流一下当前推进重点，尤其是 {ask}。",
                "",
                "如果方便，本周可以约一个 20 分钟的电话或线上沟通。",
            ]
        )
    return "# 外联草稿\n\n你好，最近看到你们团队的公开动态，想约一个 20 分钟沟通。"


def build_watchlist_digest(
    *,
    output_language: str = "zh-CN",
    changes: list[ResearchWatchlistChangeEvent] | list[dict] | None = None,
) -> str:
    resolved_language = normalize_output_language(output_language)
    lines = [
        f"# {localized_text(resolved_language, {'zh-CN': 'Watchlist Digest', 'zh-TW': 'Watchlist Digest', 'en': 'Watchlist Digest'}, 'Watchlist Digest')}",
        "",
    ]
    rows = changes or []
    if not rows:
        lines.append("- 今天暂无新的 watchlist 变化。")
        return "\n".join(lines)
    for row in rows[:8]:
        summary = getattr(row, "summary", None) if not isinstance(row, dict) else row.get("summary")
        severity = getattr(row, "severity", None) if not isinstance(row, dict) else row.get("severity")
        change_type = getattr(row, "change_type", None) if not isinstance(row, dict) else row.get("change_type")
        lines.append(f"- [{severity or 'medium'} / {change_type or 'rewritten'}] {summary or ''}")
    return "\n".join(lines)


def complete_task(
    task: WorkTask,
    *,
    content: str,
    extra_payload: dict | None = None,
) -> WorkTask:
    task.status = "done"
    task.finished_at = datetime.now(timezone.utc)
    output = {"content": content}
    if extra_payload:
        output.update(extra_payload)
    task.output_payload = output
    task.error_message = None
    return task


def fail_task(task: WorkTask, message: str) -> WorkTask:
    task.status = "failed"
    task.finished_at = datetime.now(timezone.utc)
    task.error_message = message
    return task
