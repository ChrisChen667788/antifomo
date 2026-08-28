from __future__ import annotations

from collections.abc import Iterable
import re

from app.services.content_extractor import normalize_text
from app.services.research.report_common import dedupe_strings
from app.services.research.source_documents import looks_like_source_artifact_text


MONEY_PATTERN = re.compile(
    r"(?:预算|投资|金额|规模|采购金额|中标金额|合同金额|总投资|资金|经费|财政投入|项目投资)"
    r"[^。；;\n]{0,28}?"
    r"(\d+(?:\.\d+)?(?:亿|万|千)?元|\d+(?:\.\d+)?\s?(?:million|billion|mn|bn)\s?(?:usd|dollars?)?)",
    re.IGNORECASE,
)

SUMMARY_GUIDANCE_TOKENS = (
    "建议",
    "建議",
    "追加",
    "优先",
    "優先",
    "继续",
    "繼續",
    "收敛到",
    "收斂到",
    "交叉检索",
    "交叉檢索",
    "重新生成",
    "后重试",
    "後重試",
    "把搜索范围",
    "把搜尋範圍",
    "不要只盯",
    "至少要回答",
)

BAD_SUMMARY_PHRASES = (
    *SUMMARY_GUIDANCE_TOKENS,
    "当前关键词范围",
    "优先给具体公司",
    "官方业务联系方式",
    "公开渠道联络人信息",
    "已向美国证券交易委",
    "美国证券交易委",
    "当前证据不足",
    "建议补充",
)

BAD_EXEC_SUMMARY_PHRASES = (
    "当前关键词范围",
    "优先给具体公司",
    "官方业务联系方式",
    "公开渠道联络人信息",
    "已向美国证券交易委",
    "美国证券交易委",
    "当前证据不足",
    "建议补充",
    "继续扩大搜索范围",
    "扩大搜索范围",
)

FIELD_ROW_NOISE_TOKENS = (
    "公开线索",
    "代表样本",
    "若金额仍缺失",
    "若暂未拿到明确金额",
    "可先给出高价值预算口径",
    "这些口径最适合后续销售",
    "尽量颗粒度细致到具体的垂直赛道",
    "精确到有预算的甲方公司",
    "建议补充公开服务热线",
    "建议将关键词收敛到具体甲方公司或项目名称",
    "继续扩大搜索范围",
    "当前证据不足",
    "优先给具体公司",
    "把高价值甲方",
    "预算判断不要只盯",
    "优先收集公开业务入口",
    "当前已收敛到具体公司，但公开联系方式仍不足",
    "如果公开联系方式依旧不足",
    "若需形成前三名单",
    "建议追加政府采购、公共资源交易、上市公告和行业媒体对",
)

COMMERCIAL_BUDGET_SIGNAL_TOKENS = (
    "预算",
    "采购",
    "招标",
    "中标",
    "项目",
    "投资",
    "经费",
    "金额",
    "资金",
    "专项",
    "立项",
    "合同额",
    "财政",
    "扩容",
)

BUDGET_ROW_NOISE_TOKENS = (
    "同比增长",
    "经济数据",
    "中国经济",
    "开局良好",
    "民生网首页",
    "微信 微博",
    "豆瓣 ",
    "关注民生周刊",
    "客户端 专题报道",
    "市场规模",
    "爆发元年",
    "公开市场投资者",
    "newcomer",
    "云头条",
)

BUDGET_ROW_CONTEXT_TOKENS = (
    "预算",
    "采购",
    "招标",
    "中标",
    "项目",
    "立项",
    "合同",
    "签约",
    "批复",
    "经费",
    "专项",
    "财政",
)


def looks_like_insufficient(value: str) -> bool:
    lowered = normalize_text(value).lower()
    return any(
        token in lowered
        for token in (
            "当前证据不足",
            "目前證據不足",
            "current evidence is insufficient",
            "evidence is insufficient",
            "待补充",
            "待補充",
            "insufficient",
        )
    )


def is_actionable_budget_row(value: str) -> bool:
    normalized = normalize_text(value)
    if (
        not normalized
        or looks_like_insufficient(normalized)
        or looks_like_source_artifact_text(normalized)
        or any(token in normalized for token in BUDGET_ROW_NOISE_TOKENS)
        or any(token in normalized for token in FIELD_ROW_NOISE_TOKENS)
    ):
        return False
    has_money_signal = bool(MONEY_PATTERN.search(normalized))
    signal_text = re.sub(
        r"(?:计划)?(?:采购|招标)(?:部|处|科|组|中心|办公室|负责人|经理|组长)",
        "",
        normalized,
    )
    has_strict_budget_signal = any(
        token in signal_text for token in ("预算", "采购", "招标", "中标", "经费", "金额", "资金", "专项", "立项", "合同额", "财政", "扩容")
    )
    has_budget_context = any(token in signal_text for token in BUDGET_ROW_CONTEXT_TOKENS)
    has_project_or_investment_signal = any(token in signal_text for token in ("项目", "投资"))
    if has_money_signal or has_strict_budget_signal:
        return True
    if has_project_or_investment_signal and any(
        token in signal_text for token in ("预算", "采购", "招标", "中标", "立项", "合同", "财政", "金额", "经费", "专项")
    ):
        return True
    if "投资" in normalized and not (has_money_signal or has_budget_context):
        return False
    return False


def is_summary_fact_row(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or looks_like_insufficient(normalized):
        return False
    if looks_like_source_artifact_text(normalized):
        return False
    if any(token in normalized for token in SUMMARY_GUIDANCE_TOKENS):
        return False
    if any(token in normalized for token in FIELD_ROW_NOISE_TOKENS):
        return False
    if len(normalized) > 48 and "：" not in normalized and ":" not in normalized and "（" not in normalized:
        return False
    return True


def summary_fact_rows(values: Iterable[str], *, limit: int = 3) -> list[str]:
    return dedupe_strings([normalize_text(value) for value in values if is_summary_fact_row(value)], limit)
