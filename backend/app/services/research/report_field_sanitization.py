from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re
from typing import Pattern

from app.services.content_extractor import normalize_text


_TENDER_TIME_PATTERN = re.compile(
    r"(?:20\d{2}(?:年|年度)?|Q[1-4]|[一二三四1-4]季度|上半年|下半年|本季度|下季度|"
    r"\d{1,2}\s*月|未来|近期|本月|下月|财政周期|预算周期|窗口期)",
    re.IGNORECASE,
)
_TENDER_EVENT_TOKENS = (
    "采购",
    "招标",
    "招采",
    "中标",
    "开标",
    "比选",
    "立项",
    "预算",
    "合同",
    "采购意向",
    "申报",
    "窗口",
)
_PERSON_ROW_PATTERN = re.compile(
    r"^(?P<name>[\u4e00-\u9fa5·]{2,4})(?P<role>书记|市长|副市长|局长|副局长|厅长|副厅长|"
    r"主任|副主任|董事长|总经理|总裁|副总裁|院长|校长|负责人)[：:]"
)
_PERSON_NAME_NOISE_TOKENS = (
    "省长",
    "市长",
    "书记",
    "局长",
    "厅长",
    "主任",
    "政府",
    "国资",
    "数据",
    "公司",
    "集团",
    "中心",
    "部门",
    "单位",
    "委",
    "局",
)
_PEER_MOVE_ACTION_TOKENS = (
    "发布",
    "建设",
    "采购",
    "招标",
    "中标",
    "成交",
    "上线",
    "落地",
    "启动",
    "推进",
    "扩容",
    "签约",
    "合作",
    "部署",
    "投入",
    "试点",
)
_OUTLOOK_TOKENS = (
    "未来",
    "预计",
    "预期",
    "有望",
    "趋势",
    "演进",
    "走向",
    "或将",
    "将从",
    "会从",
    "五年",
    "到2030",
    "至2030",
    "到2035",
    "至2035",
)
_OUTLOOK_CHANGE_TOKENS = (
    "二期",
    "三期",
    "四期",
    "扩容",
    "升级",
    "平台化",
    "统建",
    "根据规划",
)
_STRATEGIC_DIRECTION_TOKENS = (
    "战略",
    "方向",
    "目标",
    "重点",
    "推进",
    "深化",
    "提升",
    "打造",
    "构建",
    "转向",
    "一体化",
    "智能化",
    "数字化",
    "平台化",
    "统建",
)
_COMPETITION_TOKENS = (
    "竞争",
    "竞品",
    "替代",
    "差异化",
    "优势",
    "劣势",
    "壁垒",
    "份额",
    "中标",
    "入围",
    "既有厂商",
)
_PROJECT_PHASE_TOKENS = (
    "一期",
    "二期",
    "三期",
    "四期",
    "扩建",
    "扩容",
    "续建",
    "落地",
    "试点",
    "分布",
)
_FIELD_LABEL_NOISE_PREFIXES = (
    "在",
    "随着",
    "推广",
    "落实",
    "根据",
    "有关",
    "相关",
)
_GENERIC_DEPARTMENT_LABELS = {
    "政府办公室",
    "政府办公厅",
    "数据局",
    "大数据局",
    "政务服务部门",
    "采购部",
    "采购部门",
    "信息中心",
}
_DOCUMENT_TITLE_TOKENS = (
    "关于印发",
    "最新公报",
    "政府办公室(厅)文件",
    "公开 招标 公告",
    "公开招标公告",
    "再迎利好",
    "市县动态",
    "打造智慧政务新标杆",
    "网易订阅",
)
_PROCUREMENT_DOCUMENT_TITLE_PATTERN = re.compile(
    r"关于.{2,80}(?:采购|招标|中标|成交|项目).{0,16}(?:公告|公示|通知)$"
)
_PLACEHOLDER_QUANTITY_PATTERN = re.compile(r"(?:^|[^A-Za-z])(?:N|X|XX)\s*(?:项|个|家|条)(?:[^A-Za-z]|$)", re.IGNORECASE)


def _looks_like_document_title_row(value: str) -> bool:
    normalized = normalize_text(value)
    return (
        any(token in normalized for token in _DOCUMENT_TITLE_TOKENS)
        or "|" in normalized
        or "｜" in normalized
        or "_网易" in normalized
        or bool(_PROCUREMENT_DOCUMENT_TITLE_PATTERN.search(normalized))
        or (" - " in normalized and any(token in normalized for token in ("政府", "科技局", "人民政府")))
    )


def _is_tender_timeline_row(value: str) -> bool:
    return bool(_TENDER_TIME_PATTERN.search(value)) and any(token in value for token in _TENDER_EVENT_TOKENS)


def _is_key_person_row(value: str) -> bool:
    match = _PERSON_ROW_PATTERN.match(value)
    if not match:
        return False
    name = match.group("name")
    return not any(token in name for token in _PERSON_NAME_NOISE_TOKENS)


def _is_peer_move_row(value: str) -> bool:
    normalized = normalize_text(value)
    if _looks_like_document_title_row(normalized) or _PLACEHOLDER_QUANTITY_PATTERN.search(normalized):
        return False
    parts = re.split(r"[：:]", normalized, maxsplit=1)
    if len(parts) == 2:
        label, detail = (normalize_text(part) for part in parts)
        if (
            not label
            or len(label) > 36
            or label.startswith(("区）", "区)"))
            or any(token in label for token in ("是国内", "省内各", "各云中心"))
        ):
            return False
    else:
        detail = normalized
    return len(detail) >= 8 and any(token in detail for token in _PEER_MOVE_ACTION_TOKENS)


def _is_outlook_row(value: str) -> bool:
    normalized = normalize_text(value)
    if _looks_like_document_title_row(normalized):
        return False
    if any(token in normalized for token in _OUTLOOK_TOKENS):
        return True
    return "根据规划" in normalized and any(token in normalized for token in _OUTLOOK_CHANGE_TOKENS)


def _is_project_distribution_row(value: str) -> bool:
    return bool(re.match(r"^[^：:]{2,18}[：:]", value)) or any(token in value for token in _PROJECT_PHASE_TOKENS)


@dataclass(frozen=True, slots=True)
class ReportFieldSanitizationDependencies:
    looks_like_insufficient: Callable[[str], bool]
    looks_like_source_artifact_text: Callable[[str], bool]
    looks_like_placeholder_contact_row: Callable[[str], bool]
    contains_low_value_entity_token: Callable[[str], bool]
    is_plausible_entity_name: Callable[[str], bool]
    is_lightweight_entity_name: Callable[[str], bool]
    extract_rank_entity_name: Callable[[str], str]
    fallback_entity_name_from_row: Callable[[str], str]
    strip_entity_leading_noise: Callable[[str], str]
    looks_like_fragment_entity_name: Callable[[str], bool]
    looks_like_scope_prompt_noise: Callable[[str], bool]
    looks_like_placeholder_entity_name: Callable[[str], bool]
    is_actionable_budget_row: Callable[[str], bool]
    entity_canonical_key: Callable[[str], str]
    email_pattern: Pattern[str]
    phone_pattern: Pattern[str]
    department_pattern: Pattern[str]
    generic_content_domains: tuple[str, ...]
    non_contact_source_label_tokens: tuple[str, ...]
    contact_row_hint_tokens: tuple[str, ...]
    contact_page_tokens: tuple[str, ...]
    department_hint_tokens: tuple[str, ...]
    entity_role_fields: dict[str, str]
    entity_role_name_hints: dict[str, tuple[str, ...]]
    entity_role_context_tokens: dict[str, tuple[str, ...]]
    partner_connector_aliases: tuple[str, ...]
    field_row_noise_tokens: tuple[str, ...]
    case_hint_tokens: tuple[str, ...]
    product_hint_tokens: tuple[str, ...]


def is_useful_public_contact_row(value: str, *, deps: ReportFieldSanitizationDependencies) -> bool:
    normalized = normalize_text(value)
    lowered = normalized.lower()
    if not normalized or deps.looks_like_insufficient(normalized):
        return False
    if normalized.startswith(("对于 ", "對於 ", "围绕 ", "圍繞 ")):
        return False
    if deps.looks_like_source_artifact_text(normalized) or deps.looks_like_placeholder_contact_row(normalized):
        return False
    if deps.contains_low_value_entity_token(normalized):
        return False
    if any(lowered.endswith(ext) for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp")):
        return False
    if lowered.startswith("http") and any(domain in lowered for domain in deps.generic_content_domains):
        return False
    if any(domain in lowered for domain in deps.generic_content_domains):
        return False
    label = normalize_text(normalized.split("：", 1)[0].split(":", 1)[0])
    if any(token in label for token in deps.non_contact_source_label_tokens):
        return False
    if any(token in label for token in ("中国政府网", "政策/讲话", "互联网公开网页", "腾讯新闻")):
        return False
    if label in {"中国大学"}:
        return False
    if label and ("：" in normalized or ":" in normalized) and not (
        deps.is_plausible_entity_name(label) or deps.is_lightweight_entity_name(label)
    ):
        return False
    if deps.email_pattern.search(normalized) or deps.phone_pattern.search(normalized):
        return True
    if any(token in normalized for token in deps.contact_row_hint_tokens):
        return True
    if any(token in lowered for token in deps.contact_page_tokens):
        return True
    return False


def is_useful_department_row(value: str, *, deps: ReportFieldSanitizationDependencies) -> bool:
    normalized = normalize_text(value)
    if not normalized or deps.looks_like_insufficient(normalized):
        return False
    if deps.looks_like_source_artifact_text(normalized):
        return False
    if deps.contains_low_value_entity_token(normalized):
        return False
    label = normalize_text(normalized.split("：", 1)[0].split(":", 1)[0])
    detail = normalize_text(re.split(r"[：:]", normalized, maxsplit=1)[1]) if re.search(r"[：:]", normalized) else ""
    if (
        not label
        or len(label) > 40
        or any(char in label for char in "/|｜")
        or label.startswith(_FIELD_LABEL_NOISE_PREFIXES)
        or label in _GENERIC_DEPARTMENT_LABELS
        or "或" in label
        or label.count("（") != label.count("）")
        or label.count("(") != label.count(")")
        or _looks_like_document_title_row(detail)
    ):
        return False
    if any(token in normalized for token in deps.department_hint_tokens):
        return True
    return bool(deps.department_pattern.search(normalized))


def sanitize_entity_row(field_key: str, value: str, *, deps: ReportFieldSanitizationDependencies) -> str:
    normalized = normalize_text(value)
    if not normalized or deps.looks_like_insufficient(normalized) or deps.looks_like_source_artifact_text(normalized):
        return ""
    if deps.contains_low_value_entity_token(normalized):
        return ""
    role = deps.entity_role_fields.get(field_key, "")
    if not role:
        return normalized
    candidate = deps.extract_rank_entity_name(normalized)
    if not candidate:
        candidate = deps.fallback_entity_name_from_row(normalized)
    if not candidate:
        return ""
    candidate = deps.strip_entity_leading_noise(candidate)
    if not deps.is_plausible_entity_name(candidate) and not deps.is_lightweight_entity_name(candidate):
        return ""
    if deps.looks_like_fragment_entity_name(candidate):
        return ""
    if deps.contains_low_value_entity_token(candidate):
        return ""
    if deps.looks_like_scope_prompt_noise(candidate):
        return ""
    if deps.looks_like_placeholder_entity_name(candidate):
        return ""
    name_hints = deps.entity_role_name_hints.get(role, ())
    context_hints = deps.entity_role_context_tokens.get(role, ())
    has_name_hint = any(token in candidate for token in name_hints)
    has_context_hint = any(token in normalized for token in context_hints)
    if role == "target":
        if not has_name_hint and not has_context_hint:
            return ""
        if any(token in candidate for token in ("国际招标", "招标有限责任公司", "招标有限公司", "招标代理")):
            return ""
        if candidate.endswith(("办公厅", "办公室")) and not has_context_hint:
            return ""
        if any(token in candidate for token in ("科技", "软件", "智能", "平台", "模型", "芯片", "华为", "腾讯云", "阿里云", "火山引擎")) and not has_context_hint:
            return ""
    elif role == "competitor":
        if any(token in candidate for token in ("政府", "局", "委", "办", "中心", "医院", "大学", "学校", "银行")):
            return ""
    elif role == "partner":
        if any(token in candidate for token in ("政府", "市委", "市政府", "局", "委", "办", "中心", "办公室", "办公厅")):
            return ""
        if any(token in candidate for token in ("模型", "芯片", "平台", "产品")) and not any(
            alias in candidate for alias in deps.partner_connector_aliases
        ):
            return ""
        if any(
            token in candidate
            for token in ("建设工程咨询", "招标代理", "采购代理", "工程造价咨询")
        ):
            return ""
    if field_key in {"client_peer_moves", "winner_peer_moves"}:
        return normalized
    if not has_name_hint and not has_context_hint and candidate == normalized:
        return ""
    if candidate != normalized and ("：" in normalized or ":" in normalized):
        return candidate
    if "：" not in normalized and ":" not in normalized and candidate != normalized and len(normalized) > len(candidate) + 6:
        return candidate
    return normalized


def sanitize_generic_row(field_key: str, value: str, *, deps: ReportFieldSanitizationDependencies) -> str:
    normalized = normalize_text(value)
    if not normalized or deps.looks_like_insufficient(normalized):
        return ""
    if any(token in normalized for token in deps.field_row_noise_tokens):
        return ""
    if deps.looks_like_source_artifact_text(normalized):
        return ""
    if normalized.startswith("随着由"):
        normalized = f"由{normalized[len('随着由'):]}"
    if normalized.endswith(("…", "...")) and field_key in {
        "strategic_directions",
        "leadership_focus",
        "flagship_products",
        "five_year_outlook",
    }:
        return ""
    if field_key == "budget_signals" and not deps.is_actionable_budget_row(normalized):
        return ""
    if field_key == "tender_timeline" and not _is_tender_timeline_row(normalized):
        return ""
    if field_key == "project_distribution" and not _is_project_distribution_row(normalized):
        return ""
    if field_key == "strategic_directions":
        if _looks_like_document_title_row(normalized) or not any(
            token in normalized for token in _STRATEGIC_DIRECTION_TOKENS
        ):
            return ""
    if field_key == "key_people" and not _is_key_person_row(normalized):
        return ""
    if field_key == "five_year_outlook" and not _is_outlook_row(normalized):
        return ""
    if field_key == "competition_analysis" and not any(token in normalized for token in _COMPETITION_TOKENS):
        return ""
    if field_key == "account_team_signals":
        label = normalize_text(normalized.split("：", 1)[0].split(":", 1)[0])
        if not label or not (
            deps.is_plausible_entity_name(label)
            or deps.is_lightweight_entity_name(label)
            or deps.department_pattern.fullmatch(label)
        ):
            return ""
    if field_key == "benchmark_cases":
        if _looks_like_document_title_row(normalized):
            return ""
        if not any(token in normalized for token in deps.case_hint_tokens):
            return ""
        if normalized.startswith(("行业", "產業", "行业案例", "案例拆解")) or "拆解" in normalized:
            return ""
        if any(
            token in normalized
            for token in ("热力榜", "年度作品奖", "年度企业奖", "内容创作奖", "技术创新奖", "特别荣誉奖")
        ):
            return ""
        if normalized.startswith(("相关负责人表示", "有关负责人表示")):
            return ""
        if normalized.startswith("这背后"):
            return ""
        if _PLACEHOLDER_QUANTITY_PATTERN.search(normalized):
            return ""
        if "：" not in normalized and ":" not in normalized and not any(
            token in normalized for token in ("上线", "落地", "部署", "建成", "中标", "成交", "试点", "投产", "启用")
        ):
            return ""
        if any(token in normalized for token in ("营商环境", "服务保障", "全力支持项目落地", "共同培育")) and not any(
            token in normalized for token in ("中标", "部署", "平台", "试点", "案例")
        ):
            return ""
        if len(normalized) > 96 and "：" not in normalized and ":" not in normalized:
            return ""
    if field_key == "flagship_products" and not any(token in normalized for token in deps.product_hint_tokens):
        return ""
    if field_key == "flagship_products" and normalized.startswith("随着") and (
        len(normalized) > 120 or "打开手机" in normalized
    ):
        return ""
    if field_key == "flagship_products" and normalized.startswith(("加强", "推进", "统一", "整合")) and not re.search(
        r"[：:]",
        normalized,
    ):
        return ""
    if deps.contains_low_value_entity_token(normalized):
        return ""
    return normalized


def sanitize_report_field_rows(
    field_key: str,
    values: Iterable[str],
    *,
    deps: ReportFieldSanitizationDependencies,
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    compact_rows: dict[str, int] = {}
    canonical_rows: dict[str, str] = {}
    canonical_order: list[str] = []
    for raw in values:
        normalized = normalize_text(str(raw))
        if not normalized:
            continue
        if field_key in {"client_peer_moves", "winner_peer_moves"} and not _is_peer_move_row(normalized):
            continue
        if field_key == "public_contact_channels":
            candidate = normalized if is_useful_public_contact_row(normalized, deps=deps) else ""
        elif field_key == "target_departments":
            candidate = normalized if is_useful_department_row(normalized, deps=deps) else ""
        elif field_key in deps.entity_role_fields:
            candidate = sanitize_entity_row(field_key, normalized, deps=deps)
        else:
            candidate = sanitize_generic_row(field_key, normalized, deps=deps)
        candidate = normalize_text(candidate)
        if not candidate:
            continue
        if field_key in deps.entity_role_fields:
            entity_name = deps.extract_rank_entity_name(candidate) or deps.fallback_entity_name_from_row(candidate) or candidate
            canonical_key = deps.entity_canonical_key(entity_name)
            if canonical_key:
                existing = canonical_rows.get(canonical_key, "")
                if not existing:
                    canonical_rows[canonical_key] = candidate
                    canonical_order.append(canonical_key)
                elif len(candidate) > len(existing):
                    canonical_rows[canonical_key] = candidate
                continue
        if candidate in seen:
            continue
        compact_key = re.sub(r"\s+", "", candidate).casefold()
        existing_index = compact_rows.get(compact_key)
        if existing_index is not None:
            existing = cleaned[existing_index]
            if candidate.count(" ") < existing.count(" "):
                seen.discard(existing)
                cleaned[existing_index] = candidate
                seen.add(candidate)
            continue
        seen.add(candidate)
        compact_rows[compact_key] = len(cleaned)
        cleaned.append(candidate)
    for canonical_key in canonical_order:
        candidate = normalize_text(canonical_rows.get(canonical_key, ""))
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        cleaned.append(candidate)
    return cleaned
