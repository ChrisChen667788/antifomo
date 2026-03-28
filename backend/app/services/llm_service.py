from __future__ import annotations

import json
import logging
import re
import time
import ssl
from functools import lru_cache
from typing import Protocol
from urllib import error, request

from app.core.config import get_settings
from app.services.content_extractor import normalize_text
from app.services.language import localized_text, normalize_output_language
from app.services.prompt_loader import load_prompt, render_prompt


class LLMService(Protocol):
    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        """Return JSON text result for the given prompt template and variables."""


def _truncate_text(value: str, limit: int) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip(' ，,：:；;')}…"


class MockLLMService:
    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        # Ensure prompt template exists, so missing prompt fails fast in local development.
        _ = load_prompt(prompt_name)

        if prompt_name == "summarize.txt":
            return self._summarize_json(variables)
        if prompt_name == "tags.txt":
            return self._tags_json(variables)
        if prompt_name == "score.txt":
            return self._score_json(variables)
        if prompt_name == "session_summary.txt":
            return self._session_summary_json(variables)
        if prompt_name == "interpret.txt":
            return self._interpret_json(variables)
        if prompt_name == "research_report.txt":
            return self._research_report_json(variables)
        return "{}"

    def _resolve_language(self, variables: dict[str, str]) -> str:
        return normalize_output_language(variables.get("output_language"))

    def _contains_access_limited_signal(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            token in lowered
            for token in (
                "访问受限",
                "未能抓取到正文",
                "暂未获取到正文",
                "验证码",
                "环境异常",
                "access restricted",
                "captcha",
            )
        )

    def _summarize_json(self, variables: dict[str, str]) -> str:
        output_language = self._resolve_language(variables)
        title = normalize_text(
            variables.get(
                "title",
                localized_text(
                    output_language,
                    {
                        "zh-CN": "未命名内容",
                        "zh-TW": "未命名內容",
                        "en": "Untitled item",
                        "ja": "無題コンテンツ",
                        "ko": "제목 없음",
                    },
                    "未命名内容",
                ),
            )
        )
        clean_content = normalize_text(variables.get("clean_content", ""))
        display_title = self._build_display_title(
            title=title,
            clean_content=clean_content,
            output_language=output_language,
        )
        if "正文：" in clean_content or "正文:" in clean_content:
            _, _, body = clean_content.partition("正文：")
            if not body:
                _, _, body = clean_content.partition("正文:")
            normalized_body = normalize_text(body)
            if len(normalized_body) >= 60:
                clean_content = normalized_body

        if not clean_content:
            payload = {
                "display_title": display_title,
                "short_summary": localized_text(
                    output_language,
                    {
                        "zh-CN": f"{title}：当前缺少可用正文，建议补充文本后重新处理。",
                        "zh-TW": f"{title}：目前缺少可用正文，建議補充文本後重新處理。",
                        "en": f"{title}: the full text is missing. Please add content and reprocess.",
                        "ja": f"{title}: 本文が不足しています。テキストを追加して再処理してください。",
                        "ko": f"{title}: 본문이 부족합니다. 텍스트를 보완한 뒤 다시 처리하세요.",
                    },
                    f"{title}：当前缺少可用正文，建议补充文本后重新处理。",
                ),
                "long_summary": localized_text(
                    output_language,
                    {
                        "zh-CN": "这条输入内容正文不足，暂时无法生成稳定的长摘要。可补充原文或重新抓取后再处理。",
                        "zh-TW": "這條輸入內容正文不足，暫時無法生成穩定的長摘要。可補充原文或重新抓取後再處理。",
                        "en": "The input does not contain enough body text for a stable detailed summary. Add full content or fetch again.",
                        "ja": "入力本文が不足しているため、安定した詳細要約を生成できません。本文を補足するか再取得してください。",
                        "ko": "입력 본문이 부족해 안정적인 상세 요약을 생성할 수 없습니다. 원문을 보완하거나 다시 수집해 주세요.",
                    },
                    "这条输入内容正文不足，暂时无法生成稳定的长摘要。可补充原文或重新抓取后再处理。",
                ),
                "key_points": [
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "正文不足",
                            "zh-TW": "正文不足",
                            "en": "Missing full text",
                            "ja": "本文不足",
                            "ko": "본문 부족",
                        },
                        "正文不足",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "建议补充文本",
                            "zh-TW": "建議補充文本",
                            "en": "Add article text",
                            "ja": "本文を補足",
                            "ko": "본문 보완 필요",
                        },
                        "建议补充文本",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "可点击重新处理",
                            "zh-TW": "可點擊重新處理",
                            "en": "Then reprocess",
                            "ja": "再処理を実行",
                            "ko": "재처리 실행",
                        },
                        "可点击重新处理",
                    ),
                ],
            }
            return json.dumps(payload, ensure_ascii=False)

        if self._contains_access_limited_signal(clean_content):
            payload = {
                "display_title": display_title,
                "short_summary": localized_text(
                    output_language,
                    {
                        "zh-CN": "该链接暂未获取正文，可能需要登录或验证码。建议在已登录浏览器中重新提交，或直接粘贴正文。",
                        "zh-TW": "此連結暫未取得正文，可能需要登入或驗證碼。建議在已登入瀏覽器中重新提交，或直接貼上正文。",
                        "en": "Full text was not captured. Login or CAPTCHA may be required. Resubmit from a logged-in browser or paste content directly.",
                        "ja": "本文を取得できませんでした。ログインや CAPTCHA が必要な可能性があります。ログイン済みブラウザから再送するか、本文を貼り付けてください。",
                        "ko": "본문을 가져오지 못했습니다. 로그인 또는 CAPTCHA가 필요할 수 있습니다. 로그인된 브라우저에서 다시 제출하거나 본문을 붙여넣어 주세요.",
                    },
                    "该链接暂未获取正文，可能需要登录或验证码。建议在已登录浏览器中重新提交，或直接粘贴正文。",
                ),
                "long_summary": localized_text(
                    output_language,
                    {
                        "zh-CN": "系统已识别到这是可访问受限页面，当前无法稳定抓取正文内容。建议改用浏览器插件在已登录状态下提交，或在 Inbox 直接粘贴全文再处理。",
                        "zh-TW": "系統已識別為訪問受限頁面，當前無法穩定抓取正文。建議改用瀏覽器外掛在已登入狀態下提交，或在 Inbox 直接貼上全文再處理。",
                        "en": "The page appears access-restricted, so body extraction is unstable. Submit via logged-in browser extension or paste full content in Inbox.",
                        "ja": "このページはアクセス制限があるため本文抽出が不安定です。ログイン済み拡張で送信するか、Inbox に全文を貼り付けて再処理してください。",
                        "ko": "접근 제한 페이지로 판단되어 본문 추출이 불안정합니다. 로그인된 확장에서 제출하거나 Inbox에 본문 전체를 붙여넣어 재처리하세요.",
                    },
                    "系统已识别到这是可访问受限页面，当前无法稳定抓取正文内容。",
                ),
                "key_points": [
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "正文抓取受限",
                            "zh-TW": "正文抓取受限",
                            "en": "Body extraction blocked",
                            "ja": "本文抽出が制限",
                            "ko": "본문 추출 제한",
                        },
                        "正文抓取受限",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "需要登录或验证码",
                            "zh-TW": "需要登入或驗證碼",
                            "en": "Login/CAPTCHA required",
                            "ja": "ログイン/CAPTCHA が必要",
                            "ko": "로그인/CAPTCHA 필요",
                        },
                        "需要登录或验证码",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "建议插件提交或粘贴正文",
                            "zh-TW": "建議外掛提交或貼上正文",
                            "en": "Use extension or paste full text",
                            "ja": "拡張利用か本文貼り付けを推奨",
                            "ko": "확장 제출 또는 본문 붙여넣기 권장",
                        },
                        "建议改用插件或粘贴正文",
                    ),
                ],
            }
            return json.dumps(payload, ensure_ascii=False)

        short_summary = clean_content[:110] + ("..." if len(clean_content) > 110 else "")
        long_summary_template = localized_text(
            output_language,
            {
                "zh-CN": "本文围绕“{title}”展开，核心内容是：{body}。整体信息可用于快速判断是否需要深读。",
                "zh-TW": "本文圍繞「{title}」展開，核心內容是：{body}。整體資訊可用於快速判斷是否需要深讀。",
                "en": "This article centers on \"{title}\". Core content: {body}. Use this to quickly decide whether a deep read is worthwhile.",
                "ja": "本記事は「{title}」を中心に展開されています。要点: {body}。深読みすべきかを素早く判断できます。",
                "ko": "이 글은 \"{title}\"를 중심으로 전개됩니다. 핵심 내용: {body}. 정독 필요 여부를 빠르게 판단하는 데 유용합니다.",
            },
            "本文围绕“{title}”展开，核心内容是：{body}。整体信息可用于快速判断是否需要深读。",
        )
        long_summary = long_summary_template.format(
            title=title,
            body=f"{clean_content[:280]}{'...' if len(clean_content) > 280 else ''}",
        )

        raw_points = re.split(r"[。！？!?]", clean_content)
        key_points: list[str] = []
        for point in raw_points:
            sentence = normalize_text(point)
            if len(sentence) >= 8:
                key_points.append(sentence[:36])
            if len(key_points) >= 3:
                break
        if not key_points:
            key_points = [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "信息密度偏低",
                        "zh-TW": "資訊密度偏低",
                        "en": "Lower information density",
                        "ja": "情報密度は低め",
                        "ko": "정보 밀도 낮음",
                    },
                    "信息密度偏低",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "可先略读",
                        "zh-TW": "可先略讀",
                        "en": "Skim first",
                        "ja": "まずは流し読み",
                        "ko": "우선 훑어보기",
                    },
                    "可先略读",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "再决定是否深读",
                        "zh-TW": "再決定是否深讀",
                        "en": "Decide deep read by task fit",
                        "ja": "必要なら深読み",
                        "ko": "업무 연관성 보고 정독 결정",
                    },
                    "根据任务再决定是否深读",
                ),
            ]

        payload = {
            "display_title": display_title,
            "short_summary": short_summary,
            "long_summary": long_summary,
            "key_points": key_points[:3],
        }
        return json.dumps(payload, ensure_ascii=False)

    def _build_display_title(self, *, title: str, clean_content: str, output_language: str) -> str:
        text = normalize_text(clean_content)
        lowered = text.lower()
        rules = [
            (
                any(token in lowered for token in ("百图生科", "港交所", "ipo", "上市")),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "百图生科赴港上市，AI制药进入兑现期",
                        "zh-TW": "百圖生科赴港上市，AI 製藥進入兌現期",
                        "en": "BioMap seeks Hong Kong IPO as AI drug discovery heats up",
                        "ja": "百図生科が香港上場へ、AI創薬の資本化が加速",
                        "ko": "바이오맵 홍콩 상장 추진, AI 신약개발 상용화 가속",
                    },
                    "百图生科赴港上市，AI制药进入兑现期",
                ),
            ),
            (
                any(token in lowered for token in ("vllm", "sglang", "fp8")),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "vLLM 与 SGLang 融合 FP8，推理栈继续提速",
                        "zh-TW": "vLLM 與 SGLang 融合 FP8，推理堆疊持續提速",
                        "en": "vLLM and SGLang push inference faster with FP8",
                        "ja": "vLLM と SGLang が FP8 で推論高速化",
                        "ko": "vLLM·SGLang, FP8 결합으로 추론 가속",
                    },
                    "vLLM 与 SGLang 融合 FP8，推理栈继续提速",
                ),
            ),
        ]
        for matched, candidate in rules:
            if matched:
                return candidate

        base = normalize_text(title)
        base = (
            base.replace("深度", "")
            .replace("重磅", "")
            .replace("彻底", "")
            .replace("终于", "")
            .replace("爆了", "")
            .replace("疯传", "")
        ).strip("：:，,。！？!?· ")
        if 10 <= len(base) <= 28:
            return base

        if text:
            for sentence in re.split(r"[。！？!?]", text):
                cleaned = normalize_text(sentence)
                if 12 <= len(cleaned) <= 28:
                    return cleaned
                if len(cleaned) > 28:
                    return cleaned[:28].rstrip("，,：:；; ")

        return localized_text(
            output_language,
            {
                "zh-CN": "内容主题待确认",
                "zh-TW": "內容主題待確認",
                "en": "Topic pending",
                "ja": "テーマ確認待ち",
                "ko": "주제 확인 대기",
            },
            "内容主题待确认",
        )

    def _tags_json(self, variables: dict[str, str]) -> str:
        output_language = self._resolve_language(variables)
        title = variables.get("title", "")
        summary = variables.get("short_summary", "")
        clean_content = variables.get("clean_content", "")
        text = f"{title} {summary} {clean_content}".lower()

        if self._contains_access_limited_signal(text) or "待补全" in text or "needs completion" in text:
            tags = [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "待补全",
                        "zh-TW": "待補全",
                        "en": "Needs Completion",
                        "ja": "補完待ち",
                        "ko": "보완 필요",
                    },
                    "待补全",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "访问受限",
                        "zh-TW": "訪問受限",
                        "en": "Access Restricted",
                        "ja": "アクセス制限",
                        "ko": "접근 제한",
                    },
                    "访问受限",
                ),
            ]
            if "mp.weixin.qq.com" in text or "微信" in text or "wechat" in text:
                tags.insert(
                    0,
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "公众号",
                            "zh-TW": "公眾號",
                            "en": "WeChat OA",
                            "ja": "WeChat公式アカウント",
                            "ko": "위챗 공식계정",
                        },
                        "公众号",
                    ),
                )
            return json.dumps({"tags": tags[:5]}, ensure_ascii=False)

        localized_rules = [
            (
                localized_text(
                    output_language,
                    {
                        "zh-CN": "公众号",
                        "zh-TW": "公眾號",
                        "en": "WeChat OA",
                        "ja": "WeChat公式アカウント",
                        "ko": "위챗 공식계정",
                    },
                    "公众号",
                ),
                ("mp.weixin.qq.com", "公众号", "微信", "wechat"),
            ),
            ("AI Agent", ("agent", "ai", "智能体")),
            (
                localized_text(
                    output_language,
                    {
                        "zh-CN": "浏览器",
                        "zh-TW": "瀏覽器",
                        "en": "Browser",
                        "ja": "ブラウザ",
                        "ko": "브라우저",
                    },
                    "浏览器",
                ),
                ("浏览器", "browser"),
            ),
            (
                localized_text(
                    output_language,
                    {
                        "zh-CN": "自动化",
                        "zh-TW": "自動化",
                        "en": "Automation",
                        "ja": "自動化",
                        "ko": "자동화",
                    },
                    "自动化",
                ),
                ("自动化", "workflow", "流程", "automation"),
            ),
            (
                localized_text(
                    output_language,
                    {
                        "zh-CN": "效率工具",
                        "zh-TW": "效率工具",
                        "en": "Productivity",
                        "ja": "生産性ツール",
                        "ko": "생산성 도구",
                    },
                    "效率工具",
                ),
                ("效率", "productivity", "工具"),
            ),
            (
                localized_text(
                    output_language,
                    {
                        "zh-CN": "求职",
                        "zh-TW": "求職",
                        "en": "Career",
                        "ja": "就職",
                        "ko": "구직",
                    },
                    "求职",
                ),
                ("求职", "招聘", "岗位", "career", "job"),
            ),
            (
                localized_text(
                    output_language,
                    {
                        "zh-CN": "创业",
                        "zh-TW": "創業",
                        "en": "Startup",
                        "ja": "スタートアップ",
                        "ko": "스타트업",
                    },
                    "创业",
                ),
                ("创业", "融资", "初创", "startup"),
            ),
            (
                localized_text(
                    output_language,
                    {
                        "zh-CN": "商业趋势",
                        "zh-TW": "商業趨勢",
                        "en": "Business Trend",
                        "ja": "ビジネストレンド",
                        "ko": "비즈니스 트렌드",
                    },
                    "商业趋势",
                ),
                ("市场", "趋势", "商业", "business", "market"),
            ),
            ("Web", ("web", "前端", "浏览器标准", "权限")),
        ]

        tags: list[str] = []
        for tag, keywords in localized_rules:
            if any(keyword in text for keyword in keywords):
                tags.append(tag)
            if len(tags) >= 5:
                break

        if not tags:
            tags = [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "信息筛选",
                        "zh-TW": "資訊篩選",
                        "en": "Info Filtering",
                        "ja": "情報フィルタリング",
                        "ko": "정보 필터링",
                    },
                    "信息筛选",
                )
            ]

        return json.dumps({"tags": tags[:5]}, ensure_ascii=False)

    def _research_report_json(self, variables: dict[str, str]) -> str:
        output_language = self._resolve_language(variables)
        keyword = normalize_text(variables.get("keyword", ""))
        research_focus = normalize_text(variables.get("research_focus", ""))
        source_count = int(variables.get("source_count", "0") or 0)
        source_digest = normalize_text(variables.get("source_digest", ""))
        try:
            source_intelligence = json.loads(variables.get("source_intelligence", "{}") or "{}")
        except json.JSONDecodeError:
            source_intelligence = {}

        def intelligence_rows(key: str, fallback: list[str], limit: int = 6) -> list[str]:
            rows = [
                normalize_text(item)
                for item in source_intelligence.get(key, [])
                if isinstance(item, str) and normalize_text(item)
            ]
            if rows:
                return rows[:limit]
            return fallback[:limit]

        title_template = localized_text(
            output_language,
            {
                "zh-CN": "{keyword} 研报：政策、商机与落地策略总览",
                "zh-TW": "{keyword} 研報：政策、商機與落地策略總覽",
                "en": "{keyword} Briefing: policy signals, opportunity map, and go-to-market actions",
            },
            "{keyword} 研报：政策、商机与落地策略总览",
        )
        report_title = title_template.format(keyword=keyword or localized_text(output_language, {"en": "Topic"}, "主题"))

        summary_template = localized_text(
            output_language,
            {
                "zh-CN": "系统围绕“{keyword}”检索了 {count} 个可访问来源，并按政策信号、项目商机、预算与后续扩建线索进行归纳。当前结论适合作为行业跟踪、方案切入、销售推进与投标准备的工作底稿；若需更强结论，建议继续补充区域、客户类型和项目关键词。",
                "zh-TW": "系統圍繞「{keyword}」檢索了 {count} 個可訪問來源，並按政策信號、專案商機、預算與後續擴建線索進行歸納。目前結論適合作為產業跟蹤、方案切入、銷售推進與投標準備的工作底稿；若需更強結論，建議補充地區、客戶類型與專案關鍵詞。",
                "en": "The system reviewed {count} accessible sources around \"{keyword}\" and organized them into policy signals, opportunity clues, budget hints, and follow-on project signals. Use this as a working memo for market tracking, solution positioning, sales pursuit, and bid preparation.",
            },
            "系统围绕“{keyword}”检索了 {count} 个可访问来源，并按政策信号、项目商机、预算与后续扩建线索进行归纳。",
        )
        executive_summary = summary_template.format(keyword=keyword or "该主题", count=source_count)

        focus_suffix = f"（重点关注：{research_focus}）" if research_focus and output_language.startswith("zh") else ""
        evidence_suffix = _truncate_text(source_digest, 220) if source_digest else ""
        payload = {
            "report_title": report_title,
            "executive_summary": f"{executive_summary}{focus_suffix}",
            "consulting_angle": localized_text(
                output_language,
                {
                    "zh-CN": "适合作为行业资讯、解决方案设计、销售策略、投标规划与生态合作的综合底稿。",
                    "zh-TW": "適合作為產業資訊、解決方案設計、銷售策略、投標規劃與生態合作的綜合底稿。",
                    "en": "Use this as a unified memo for market updates, solution design, sales strategy, bid planning, and ecosystem partnership work.",
                },
                "适合作为行业资讯、解决方案设计、销售策略、投标规划与生态合作的综合底稿。",
            ),
            "industry_brief": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": f"{keyword} 相关公开信息正在向政策、项目和落地节奏集中。",
                        "zh-TW": f"{keyword} 相關公開資訊正集中於政策、專案與落地節奏。",
                        "en": f"Public signals around {keyword} are clustering around policy, projects, and deployment rhythm.",
                    },
                    f"{keyword} 相关公开信息正在向政策、项目和落地节奏集中。",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "适合把资讯筛选从“看文章”转为“看信号、看预算、看节奏”。",
                        "zh-TW": "適合把資訊篩選從「看文章」轉為「看信號、看預算、看節奏」。",
                        "en": "Shift from reading articles to reading signals, budgets, and timing.",
                    },
                    "适合把资讯筛选从“看文章”转为“看信号、看预算、看节奏”。",
                ),
            ],
            "key_signals": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "优先关注政策文件、领导表态、重点项目公告与预算口径。",
                        "zh-TW": "優先關注政策文件、領導表態、重點專案公告與預算口徑。",
                        "en": "Prioritize policy documents, leadership statements, key project notices, and budget language.",
                    },
                    "优先关注政策文件、领导表态、重点项目公告与预算口径。",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "二期、三期、四期项目通常意味着已有试点基础和更高成交概率。",
                        "zh-TW": "二期、三期、四期專案通常意味著已有試點基礎與更高成交機率。",
                        "en": "Phase II/III/IV projects often indicate prior pilots and a higher probability of conversion.",
                    },
                    "二期、三期、四期项目通常意味着已有试点基础和更高成交概率。",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "若同一主题同时出现媒体报道、公众号评论与官方文件，应以官方口径优先校验。",
                        "zh-TW": "若同一主題同時出現媒體報導、公眾號評論與官方文件，應以官方口徑優先校驗。",
                        "en": "When media, WeChat commentary, and official sources disagree, validate against official sources first.",
                    },
                    "若同一主题同时出现媒体报道、公众号评论与官方文件，应以官方口径优先校验。",
                ),
            ],
            "policy_and_leadership": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "把政策发布与领导发言映射到采购方向、预算归口和时间窗口。",
                        "zh-TW": "將政策發布與領導發言映射到採購方向、預算歸口與時間窗口。",
                        "en": "Map policy releases and leadership remarks to procurement direction, budget owners, and timing windows.",
                    },
                    "把政策发布与领导发言映射到采购方向、预算归口和时间窗口。",
                )
            ],
            "commercial_opportunities": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "优先筛出带有预算、扩建、试点转正式、平台升级和分期建设特征的项目线索。",
                        "zh-TW": "優先篩出帶有預算、擴建、試點轉正式、平台升級與分期建設特徵的專案線索。",
                        "en": "Prioritize projects with budget, expansion, pilot-to-scale, platform upgrade, or phased-build signals.",
                    },
                    "优先筛出带有预算、扩建、试点转正式、平台升级和分期建设特征的项目线索。",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "重点盯住‘已立项但方案未定型’的客户窗口，这类阶段更适合方案顾问切入。",
                        "zh-TW": "重點盯住「已立項但方案未定型」的客戶窗口，這類階段更適合方案顧問切入。",
                        "en": "Focus on buyers with approved projects but undecided architectures; this is where consultative sellers can enter.",
                    },
                    "重点盯住‘已立项但方案未定型’的客户窗口，这类阶段更适合方案顾问切入。",
                ),
            ],
            "solution_design": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "把方案拆成‘试点场景 + 平台能力 + 交付节奏 + 可量化成效’四段式。",
                        "zh-TW": "將方案拆成「試點場景 + 平台能力 + 交付節奏 + 可量化成效」四段式。",
                        "en": "Structure solutions into pilot scenario, platform capabilities, delivery rhythm, and measurable outcomes.",
                    },
                    "把方案拆成‘试点场景 + 平台能力 + 交付节奏 + 可量化成效’四段式。",
                )
            ],
            "sales_strategy": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "先锁定牵头部门、预算归口和技术把关人，再决定是高层切入还是场景切入。",
                        "zh-TW": "先鎖定牽頭部門、預算歸口與技術把關人，再決定是高層切入還是場景切入。",
                        "en": "Identify the lead department, budget owner, and technical gatekeeper before choosing an executive or use-case entry.",
                    },
                    "先锁定牵头部门、预算归口和技术把关人，再决定是高层切入还是场景切入。",
                )
            ],
            "bidding_strategy": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "标前阶段优先准备伙伴组合、资质补齐和需求引导材料，而不是只等招标文件。",
                        "zh-TW": "標前階段優先準備夥伴組合、資質補齊與需求引導材料，而不是只等招標文件。",
                        "en": "Before tender release, prepare partner structure, required qualifications, and requirement-shaping materials.",
                    },
                    "标前阶段优先准备伙伴组合、资质补齐和需求引导材料，而不是只等招标文件。",
                )
            ],
            "outreach_strategy": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "陌生拜访时避免泛泛介绍产品，直接带着‘政策/项目/预算’线索切入更容易获得对话。",
                        "zh-TW": "陌生拜訪時避免泛泛介紹產品，直接帶著「政策/專案/預算」線索切入更容易獲得對話。",
                        "en": "Cold outreach works better when anchored in policy, project, or budget clues rather than generic product intros.",
                    },
                    "陌生拜访时避免泛泛介绍产品，直接带着‘政策/项目/预算’线索切入更容易获得对话。",
                )
            ],
            "ecosystem_strategy": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "优先盘点本地总包、集成商、顾问机构和行业研究伙伴，形成联合触达与联合投标能力。",
                        "zh-TW": "優先盤點在地總包、集成商、顧問機構與產業研究夥伴，形成聯合觸達與聯合投標能力。",
                        "en": "Map local prime contractors, integrators, consultancies, and research partners to build joint access and bid capability.",
                    },
                    "优先盘点本地总包、集成商、顾问机构和行业研究伙伴，形成联合触达与联合投标能力。",
                )
            ],
            "target_accounts": intelligence_rows(
                "target_accounts",
                [
                    localized_text(
                        output_language,
                        {
                            "zh-CN": f"{keyword} 相关重点甲方仍需补充更明确的区域和部门名称。",
                            "zh-TW": f"{keyword} 相關重點甲方仍需補充更明確的區域與部門名稱。",
                            "en": f"Key buyer names for {keyword} still need clearer regional and departmental evidence.",
                        },
                        f"{keyword} 相关重点甲方仍需补充更明确的区域和部门名称。",
                    )
                ],
            ),
            "budget_signals": intelligence_rows(
                "budget_signals",
                [
                    localized_text(
                        output_language,
                        {
                            "zh-CN": f"{keyword} 的公开预算口径仍偏少，建议增加预算、投资、合同金额等搜索词。",
                            "zh-TW": f"{keyword} 的公開預算口徑仍偏少，建議增加預算、投資、合同金額等搜尋詞。",
                            "en": f"Public budget evidence for {keyword} is still sparse; add budget, investment, and contract value terms.",
                        },
                        f"{keyword} 的公开预算口径仍偏少，建议增加预算、投资、合同金额等搜索词。",
                    )
                ],
            ),
            "project_distribution": intelligence_rows("project_distribution", []),
            "strategic_directions": intelligence_rows("strategic_directions", []),
            "tender_timeline": intelligence_rows("tender_timeline", []),
            "leadership_focus": intelligence_rows("leadership_focus", []),
            "ecosystem_partners": intelligence_rows("ecosystem_partners", []),
            "competitor_profiles": intelligence_rows("competitor_profiles", []),
            "benchmark_cases": intelligence_rows("benchmark_cases", []),
            "flagship_products": intelligence_rows("flagship_products", []),
            "key_people": intelligence_rows("key_people", []),
            "five_year_outlook": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "未来五年更可能沿着‘试点验证 -> 区域复制 -> 二三期扩容 -> 统一平台化’路径演进。",
                        "zh-TW": "未來五年更可能沿著「試點驗證 -> 區域複製 -> 二三期擴容 -> 統一平台化」路徑演進。",
                        "en": "The next five years are likely to move from pilot validation to regional replication, then phase-II/III expansion and unified platforms.",
                    },
                    "未来五年更可能沿着‘试点验证 -> 区域复制 -> 二三期扩容 -> 统一平台化’路径演进。",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "预算节奏通常会从单点项目预算，转向年度专项或平台化预算池。",
                        "zh-TW": "預算節奏通常會從單點專案預算，轉向年度專項或平台化預算池。",
                        "en": "Budgets often evolve from one-off project lines into annual strategic or platform-level pools.",
                    },
                    "预算节奏通常会从单点项目预算，转向年度专项或平台化预算池。",
                ),
            ],
            "client_peer_moves": intelligence_rows(
                "client_peer_moves",
                [
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "当前证据不足：建议先补充甲方全称、区域和项目阶段后再输出前三同行。",
                            "zh-TW": "目前證據不足：建議先補充甲方全稱、區域與專案階段後再輸出前三同行。",
                            "en": "Current evidence is insufficient: add buyer full names, regions, and project phases before ranking peer buyers.",
                        },
                        "当前证据不足：建议先补充甲方全称、区域和项目阶段后再输出前三同行。",
                    )
                ],
            ),
            "winner_peer_moves": intelligence_rows(
                "winner_peer_moves",
                [
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "当前证据不足：建议补充中标公告、成交结果和联合体信息后再输出前三同行。",
                            "zh-TW": "目前證據不足：建議補充中標公告、成交結果與聯合體資訊後再輸出前三同行。",
                            "en": "Current evidence is insufficient: add award notices, result pages, and consortium data before ranking winning peers.",
                        },
                        "当前证据不足：建议补充中标公告、成交结果和联合体信息后再输出前三同行。",
                    )
                ],
            ),
            "competition_analysis": intelligence_rows(
                "competition_analysis",
                [
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "竞争判断应优先围绕具体竞品名称、区域打法和中标路径，而不是抽象谈“市场竞争”。",
                            "zh-TW": "競爭判斷應優先圍繞具體競品名稱、區域打法與中標路徑，而不是抽象談「市場競爭」。",
                            "en": "Competition analysis should center on named rivals, regional plays, and award paths rather than generic market rivalry.",
                        },
                        "竞争判断应优先围绕具体竞品名称、区域打法和中标路径，而不是抽象谈“市场竞争”。",
                    )
                ],
            ),
            "risks": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "若当前来源更多来自媒体和公众号，结论要与正式公告交叉校验。",
                        "zh-TW": "若目前來源更多來自媒體與公眾號，結論需與正式公告交叉校驗。",
                        "en": "If sources are mostly media and WeChat commentary, cross-check conclusions against formal announcements.",
                    },
                    "若当前来源更多来自媒体和公众号，结论要与正式公告交叉校验。",
                ),
                evidence_suffix or localized_text(
                    output_language,
                    {
                        "zh-CN": "当前有效证据片段有限，建议持续补充来源。",
                        "zh-TW": "目前有效證據片段有限，建議持續補充來源。",
                        "en": "The current evidence base is still limited. Continue adding sources.",
                    },
                    "当前有效证据片段有限，建议持续补充来源。",
                ),
            ],
            "next_actions": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "把关键词进一步拆成‘地区 + 行业 + 客户类型 + 项目阶段’后再跑一轮。",
                        "zh-TW": "將關鍵詞進一步拆成「地區 + 產業 + 客戶類型 + 專案階段」後再跑一輪。",
                        "en": "Run another round with region, sector, buyer type, and project stage added to the query.",
                    },
                    "把关键词进一步拆成‘地区 + 行业 + 客户类型 + 项目阶段’后再跑一轮。",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "把高价值来源加入收藏或知识库，持续沉淀线索库。",
                        "zh-TW": "將高價值來源加入收藏或知識庫，持續沉澱線索庫。",
                        "en": "Save high-value sources into the reading list or knowledge base for continued signal tracking.",
                    },
                    "把高价值来源加入收藏或知识库，持续沉淀线索库。",
                ),
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    def _score_json(self, variables: dict[str, str]) -> str:
        output_language = self._resolve_language(variables)
        short_summary = normalize_text(variables.get("short_summary", ""))
        long_summary = normalize_text(variables.get("long_summary", ""))
        text = f"{short_summary} {long_summary}"
        length = len(text)
        lowered = text.lower()

        if self._contains_access_limited_signal(text):
            payload = {
                "score_value": 1.2,
                "action_suggestion": "skip",
                "recommendation_reason": [
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "正文未抓取成功，信息不完整",
                            "zh-TW": "正文未抓取成功，資訊不完整",
                            "en": "Body extraction failed; information is incomplete.",
                            "ja": "本文抽出に失敗し、情報が不完全です。",
                            "ko": "본문 추출에 실패해 정보가 불완전합니다.",
                        },
                        "正文未抓取成功，信息不完整",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "当前仅可作为待补全占位内容",
                            "zh-TW": "目前僅可作為待補全占位內容",
                            "en": "This item is currently only a placeholder.",
                            "ja": "現時点では補完待ちのプレースホルダーです。",
                            "ko": "현재는 보완 대기용 플레이스홀더 항목입니다.",
                        },
                        "当前仅可作为待补全占位内容",
                    ),
                    localized_text(
                        output_language,
                        {
                            "zh-CN": "建议补充正文后再评估价值",
                            "zh-TW": "建議補充正文後再評估價值",
                            "en": "Re-evaluate after full text is provided.",
                            "ja": "本文補完後に再評価してください。",
                            "ko": "본문 보완 후 다시 평가하세요.",
                        },
                        "建议补充正文后再评估价值",
                    ),
                ],
                "content_density": "low",
                "novelty_level": "low",
            }
            return json.dumps(payload, ensure_ascii=False)

        base = 2.0
        if length > 500:
            base += 1.1
        elif length > 260:
            base += 0.8
        elif length > 120:
            base += 0.4

        novelty = "low"
        if any(token in lowered for token in ("发布", "首次", "新", "最新", "breaking", "new")):
            base += 0.4
            novelty = "high"
        elif any(token in lowered for token in ("更新", "改进", "优化", "release", "update")):
            base += 0.2
            novelty = "medium"

        density = "low"
        if length > 420:
            density = "high"
        elif length > 180:
            density = "medium"

        score_value = max(1.0, min(5.0, round(base, 2)))
        action = "skip"
        if score_value >= 3.5:
            action = "deep_read"
        elif score_value >= 2.1:
            action = "later"

        payload = {
            "score_value": score_value,
            "action_suggestion": action,
            "recommendation_reason": [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "基于信息密度与长度估计",
                        "zh-TW": "基於資訊密度與長度估計",
                        "en": "Estimated from information density and content length.",
                        "ja": "情報密度と文量をもとに推定しています。",
                        "ko": "정보 밀도와 분량을 기준으로 추정했습니다.",
                    },
                    "基于信息密度与长度估计",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "结合新增信息信号进行初筛",
                        "zh-TW": "結合新增資訊信號進行初篩",
                        "en": "Initial screening includes novelty signals.",
                        "ja": "新規性シグナルも加味して一次判定しています。",
                        "ko": "신규성 신호를 결합해 1차 분류했습니다.",
                    },
                    "结合新增信息信号进行初筛",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "该结果可由用户反馈持续修正",
                        "zh-TW": "此結果可由用戶回饋持續修正",
                        "en": "User feedback can continuously refine this result.",
                        "ja": "この結果はユーザーフィードバックで継続改善されます。",
                        "ko": "이 결과는 사용자 피드백으로 계속 보정됩니다.",
                    },
                    "该结果可由用户反馈持续修正",
                ),
            ],
            "content_density": density,
            "novelty_level": novelty,
        }
        return json.dumps(payload, ensure_ascii=False)

    def _session_summary_json(self, variables: dict[str, str]) -> str:
        output_language = self._resolve_language(variables)
        goal = variables.get(
            "goal_text",
            localized_text(
                output_language,
                {
                    "zh-CN": "完成一次专注任务",
                    "zh-TW": "完成一次專注任務",
                    "en": "finish one focused task",
                    "ja": "1回の集中タスク完了",
                    "ko": "한 번의 집중 작업 완료",
                },
                "完成一次专注任务",
            ),
        )
        payload = {
            "summary_text": localized_text(
                output_language,
                {
                    "zh-CN": f"你已完成本次专注，目标为“{goal}”。建议先处理高相关深读内容，再集中整理稍后读，其余可归档。",
                    "zh-TW": f"你已完成本次專注，目標為「{goal}」。建議先處理高相關深讀內容，再集中整理稍後讀，其餘可歸檔。",
                    "en": f"You completed this focus block with the goal \"{goal}\". Start with highly relevant deep reads, then batch the later reads and archive the rest.",
                    "ja": f"目標「{goal}」で集中セッションを完了しました。まず関連度の高い深読み項目を処理し、その後で後で読む項目をまとめて整理し、残りはアーカイブしてください。",
                    "ko": f"목표 \"{goal}\"로 집중 세션을 완료했습니다. 먼저 관련도 높은 정독 항목을 처리하고, 이후 나중에 읽기 항목을 묶어 정리한 뒤 나머지는 보관하세요.",
                },
                f"你已完成本次专注，目标为“{goal}”。建议先处理高相关深读内容，再集中整理稍后读，其余可归档。",
            ),
        }
        return json.dumps(payload, ensure_ascii=False)

    def _interpret_json(self, variables: dict[str, str]) -> str:
        output_language = self._resolve_language(variables)
        title = normalize_text(variables.get("title", ""))
        short_summary = normalize_text(variables.get("short_summary", ""))
        long_summary = normalize_text(variables.get("long_summary", ""))
        clean_content = normalize_text(variables.get("clean_content", ""))
        combined = normalize_text(f"{short_summary} {long_summary} {clean_content}")
        insight_title = self._build_display_title(
            title=title or short_summary,
            clean_content=combined,
            output_language=output_language,
        )
        expert_take = localized_text(
            output_language,
            {
                "zh-CN": f"这条内容真正值得关注的不是原始叙事包装，而是“{insight_title}”所代表的实际变化。结合摘要看，它提供了可用于后续判断的事实信号，适合放进你的持续跟踪列表，而不是仅停留在表面浏览。",
                "zh-TW": f"這條內容真正值得關注的，不是原始敘事包裝，而是「{insight_title}」所代表的實際變化。結合摘要來看，它提供了可用於後續判斷的事實訊號，適合納入持續追蹤清單。",
                "en": f"The real value here is not the original framing but the concrete shift behind “{insight_title}”. It provides factual signals that are worth tracking over time, not just skimming once.",
                "ja": f"重要なのは元の煽り方ではなく、「{insight_title}」が示す実質的な変化です。後続判断に使える事実シグナルが含まれており、継続監視対象に向いています。",
                "ko": f"핵심은 원래의 자극적 포장이 아니라 “{insight_title}”가 보여주는 실제 변화입니다. 이후 판단에 쓸 수 있는 사실 신호가 있어, 단순 소비보다 지속 추적이 적합합니다.",
            },
            f"这条内容真正值得关注的不是原始叙事包装，而是“{insight_title}”所代表的实际变化。",
        )
        key_signals = []
        for sentence in re.split(r"[。！？!?]", combined):
            cleaned = normalize_text(sentence)
            if len(cleaned) >= 8:
                key_signals.append(cleaned[:28])
            if len(key_signals) >= 3:
                break
        if not key_signals:
            key_signals = [
                localized_text(
                    output_language,
                    {
                        "zh-CN": "出现新的事实信号",
                        "zh-TW": "出現新的事實訊號",
                        "en": "New factual signals emerged",
                        "ja": "新しい事実シグナルが出現",
                        "ko": "새로운 사실 신호 등장",
                    },
                    "出现新的事实信号",
                )
            ]
        knowledge_note = localized_text(
            output_language,
            {
                "zh-CN": f"知识库笔记：{insight_title}。核心结论是，这条内容更适合被当作持续观察的行业/产品/策略信号，而不是一次性的标题信息。",
                "zh-TW": f"知識庫筆記：{insight_title}。核心結論是，這條內容更適合作為持續觀察的產業 / 產品 / 策略訊號，而不是一次性的標題資訊。",
                "en": f"Knowledge note: {insight_title}. Treat this as a signal worth tracking across product, market, or strategy changes instead of a one-off headline.",
                "ja": f"ナレッジノート: {insight_title}。単発の見出し情報ではなく、製品・市場・戦略の継続シグナルとして扱うべき内容です。",
                "ko": f"지식 노트: {insight_title}. 일회성 헤드라인이 아니라 제품·시장·전략 변화의 지속 신호로 관리할 가치가 있습니다.",
            },
            f"知识库笔记：{insight_title}。",
        )
        payload = {
            "insight_title": insight_title,
            "expert_take": expert_take,
            "key_signals": key_signals[:3],
            "knowledge_note": knowledge_note,
        }
        return json.dumps(payload, ensure_ascii=False)


class OpenAILLMService:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        timeout_seconds: int,
        organization: str | None = None,
        project: str | None = None,
        verify_ssl: bool = True,
        ca_bundle: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.organization = organization
        self.project = project
        self.verify_ssl = verify_ssl
        self.ca_bundle = ca_bundle

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if not self.verify_ssl:
            return ssl._create_unverified_context()

        cafile = self.ca_bundle
        if not cafile:
            try:
                import certifi

                cafile = certifi.where()
            except Exception:
                cafile = None

        if cafile:
            return ssl.create_default_context(cafile=cafile)
        return None

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        runtime_variables = dict(variables)
        timeout_override = runtime_variables.pop("__timeout_seconds", None)
        prompt = render_prompt(prompt_name, runtime_variables)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        if self.project:
            headers["OpenAI-Project"] = self.project

        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        ssl_context = self._build_ssl_context()
        timeout_seconds = self.timeout_seconds
        if timeout_override is not None:
            try:
                timeout_seconds = max(1, int(timeout_override))
            except Exception:
                timeout_seconds = self.timeout_seconds
        max_attempts = 2 if prompt_name == "research_report.txt" else 1
        body = ""
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                with request.urlopen(req, timeout=timeout_seconds, context=ssl_context) as resp:
                    body = resp.read().decode("utf-8", errors="ignore")
                last_error = None
                break
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="ignore")
                last_error = RuntimeError(f"OpenAI HTTP {exc.code}: {details}")
                should_retry = exc.code >= 500 and attempt < max_attempts
                if not should_retry:
                    raise last_error from exc
            except Exception as exc:
                last_error = RuntimeError(f"OpenAI request failed: {exc}")
                message = str(exc).lower()
                should_retry = attempt < max_attempts and any(
                    token in message
                    for token in ("timed out", "timeout", "temporarily unavailable", "connection reset", "remote end closed")
                )
                if not should_retry:
                    raise last_error from exc
            time.sleep(min(2.0, 0.8 * attempt))
        if last_error is not None and not body:
            raise last_error

        try:
            response_json = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI returned non-JSON response") from exc

        content = extract_openai_message_content(response_json)
        if not content:
            raise RuntimeError("OpenAI returned empty message content")
        return content


class FallbackLLMService:
    def __init__(
        self,
        primary: LLMService,
        fallback: LLMService,
        *,
        logger_name: str = "anti_fomo.llm",
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.logger = logging.getLogger(logger_name)

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        try:
            return self.primary.run_prompt(prompt_name, variables)
        except Exception as exc:
            self.logger.warning(
                "Primary LLM failed for prompt=%s, fallback to mock: %s",
                prompt_name,
                exc,
            )
            return self.fallback.run_prompt(prompt_name, variables)


def extract_openai_message_content(response_json: dict) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_chunks: list[str] = []
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            text = chunk.get("text")
            if isinstance(text, str):
                text_chunks.append(text)
        return "\n".join(text_chunks).strip()
    return ""


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    settings = get_settings()
    mock_service = MockLLMService()

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            return mock_service
        primary = OpenAILLMService(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            timeout_seconds=settings.openai_timeout_seconds,
            organization=settings.openai_organization,
            project=settings.openai_project,
            verify_ssl=settings.openai_verify_ssl,
            ca_bundle=settings.openai_ca_bundle,
        )
        if settings.llm_fallback_to_mock:
            return FallbackLLMService(primary, mock_service)
        return primary

    return mock_service


@lru_cache(maxsize=1)
def get_strategy_llm_service() -> LLMService | None:
    settings = get_settings()
    if not settings.strategy_openai_api_key:
        return None
    return OpenAILLMService(
        api_key=settings.strategy_openai_api_key,
        base_url=settings.strategy_openai_base_url,
        model=settings.strategy_openai_model,
        temperature=settings.strategy_openai_temperature,
        timeout_seconds=settings.strategy_openai_timeout_seconds,
        organization=settings.openai_organization,
        project=settings.openai_project,
        verify_ssl=settings.openai_verify_ssl,
        ca_bundle=settings.openai_ca_bundle,
    )
