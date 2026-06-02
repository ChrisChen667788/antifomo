from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Pattern

from app.services.content_extractor import normalize_text


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
    if deps.contains_low_value_entity_token(normalized):
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
    if field_key == "budget_signals" and not deps.is_actionable_budget_row(normalized):
        return ""
    if field_key == "benchmark_cases":
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
        if any(token in normalized for token in ("营商环境", "服务保障", "全力支持项目落地", "共同培育")) and not any(
            token in normalized for token in ("中标", "部署", "平台", "试点", "案例")
        ):
            return ""
        if len(normalized) > 96 and "：" not in normalized and ":" not in normalized:
            return ""
    if field_key == "flagship_products" and not any(token in normalized for token in deps.product_hint_tokens):
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
    canonical_rows: dict[str, str] = {}
    canonical_order: list[str] = []
    for raw in values:
        normalized = normalize_text(str(raw))
        if not normalized:
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
        seen.add(candidate)
        cleaned.append(candidate)
    for canonical_key in canonical_order:
        candidate = normalize_text(canonical_rows.get(canonical_key, ""))
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        cleaned.append(candidate)
    return cleaned
