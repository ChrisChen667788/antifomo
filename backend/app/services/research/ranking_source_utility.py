from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re
from typing import Pattern

from app.services.content_extractor import normalize_text
from app.services.language import localized_text
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class RankingSourceUtilityDependencies:
    source_text: Callable[[SourceDocument], str]
    truncate_text: Callable[[str, int], str]
    is_plausible_entity_name: Callable[[str], bool]
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    org_pattern: Pattern[str]
    person_role_pattern: Pattern[str]
    department_pattern: Pattern[str]
    email_pattern: Pattern[str]
    phone_pattern: Pattern[str]
    generic_content_domains: tuple[str, ...]


def rank_org_rows(
    sources: list[SourceDocument],
    *,
    role: str,
    context_keywords: tuple[str, ...],
    preferred_source_types: tuple[str, ...],
    name_bias_tokens: tuple[str, ...],
    scope_hints: dict[str, object],
    theme_terms: list[str],
    limit: int,
    deps: RankingSourceUtilityDependencies,
) -> list[str]:
    scored: dict[str, tuple[int, str]] = {}
    scope_regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    scope_clients = [normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    scope_anchor = normalize_text(str(scope_hints.get("anchor_text", ""))).lower()

    for source in sources:
        text = deps.source_text(source)
        lowered = text.lower()
        title_text = normalize_text(source.title or "")
        label_text = normalize_text(source.source_label or "")
        if theme_terms and not any(term in lowered for term in theme_terms):
            continue
        for match in deps.org_pattern.findall(text):
            name = normalize_text(match)
            if not deps.is_plausible_entity_name(name):
                continue
            if role == "target" and source.source_tier == "media":
                if not any(client in name for client in scope_clients) and not any(
                    token in name for token in ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "集团", "城投", "交投")
                ):
                    if not any(token in text for token in ("采购", "预算", "招标", "项目", "建设", "立项", "扩容")):
                        continue
            if role == "partner" and source.source_tier == "media":
                if not any(token in name for token in ("咨询", "顾问", "集成", "渠道", "联盟", "研究院", "研究所", "运营", "服务")):
                    if not any(token in text for token in ("合作", "伙伴", "联合", "联盟", "咨询", "顾问", "渠道", "集成")):
                        continue
            score = 1
            if any(token in text for token in context_keywords):
                score += 4
            if any(token in name for token in name_bias_tokens):
                score += 3
            if source.source_type in preferred_source_types:
                score += 3
            if source.source_tier == "official":
                score += 4
            elif source.source_tier == "aggregate":
                score += 2
            if any(client in name for client in scope_clients):
                score += 4
            if any(client and (client in title_text or client in label_text or client in text) for client in scope_clients):
                score += 3
            if any(region in text for region in scope_regions):
                score += 2
            if scope_anchor and scope_anchor in lowered:
                score += 1
            row = f"{name}：{deps.truncate_text(source.title or source.snippet or source.excerpt, 88)}"
            current = scored.get(name)
            if current is None or score > current[0]:
                scored[name] = (score, row)

    ordered = sorted(scored.items(), key=lambda item: (-item[1][0], item[0]))
    return [row for _, (_, row) in ordered[:limit]]


def extract_key_people_rows(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    limit: int,
    deps: RankingSourceUtilityDependencies,
) -> list[str]:
    scored: dict[str, tuple[int, str]] = {}
    scope_regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    for source in sources:
        text = deps.source_text(source)
        for name, role in deps.person_role_pattern.findall(text):
            person = normalize_text(name)
            if len(person) < 2:
                continue
            score = 1
            if source.source_type in {"policy", "procurement", "filing"}:
                score += 2
            if any(region in text for region in scope_regions):
                score += 1
            row = f"{person}{role}：{deps.truncate_text(source.title or source.snippet, 88)}"
            current = scored.get(person)
            if current is None or score > current[0]:
                scored[person] = (score, row)
    ordered = sorted(scored.items(), key=lambda item: (-item[1][0], item[0]))
    return [row for _, (_, row) in ordered[:limit]]


def extract_department_rows(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    limit: int,
    deps: RankingSourceUtilityDependencies,
) -> list[str]:
    scored: dict[str, tuple[int, str]] = {}
    scope_regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    for source in sources:
        text = deps.source_text(source)
        lowered = text.lower()
        for match in deps.department_pattern.findall(text):
            department = normalize_text(match)
            if len(department) < 3:
                continue
            score = 1
            if source.source_type in {"procurement", "policy", "filing", "official_tender_feed", "official_policy_speech"}:
                score += 2
            if any(region in text for region in scope_regions):
                score += 1
            if any(token in lowered for token in ("预算", "招标", "采购", "规划", "信息化", "数字化")):
                score += 1
            row = f"{department}：{deps.truncate_text(source.title or source.snippet, 92)}"
            current = scored.get(department)
            if current is None or score > current[0]:
                scored[department] = (score, row)
    ordered = sorted(scored.items(), key=lambda item: (-item[1][0], item[0]))
    return [row for _, (_, row) in ordered[:limit]]


def extract_public_contact_rows(
    sources: list[SourceDocument],
    *,
    output_language: str,
    limit: int,
    deps: RankingSourceUtilityDependencies,
) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    contact_person_pattern = re.compile(r"(联系人|联络人|联系人姓名|项目联系人|采购人联系人|代理机构联系人)[:：]?\s*([A-Za-z\u4e00-\u9fa5]{2,24})")
    agency_pattern = re.compile(r"(采购代理机构|招标代理机构|代理机构)[:：]?\s*([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,40})")
    contact_page_tokens = ("contact", "lxwm", "about", "relation", "ir", "investor", "join", "service", "联系我们", "联络", "联系")
    department_contact_pattern = re.compile(
        r"((采购中心|招标办|信息中心|数据局|数字化部|科技部|计划财务部|预算处|运营管理部|办公室)[A-Za-z\u4e00-\u9fa5（）()\\-]{0,16})"
    )
    line_contact_pattern = re.compile(
        r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,36})(联系人|联系电话|联系邮箱|服务热线|咨询电话)[:：]?\s*([A-Za-z0-9@\-.+\u4e00-\u9fa5]{2,48})"
    )

    def is_valid_contact_value(value: str) -> bool:
        normalized = normalize_text(value)
        lowered = normalized.lower()
        if not normalized:
            return False
        if any(lowered.endswith(ext) for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp")):
            return False
        if lowered.startswith("http") and any(domain in lowered for domain in deps.generic_content_domains):
            return False
        return True

    def allow_public_entry(source: SourceDocument) -> bool:
        domain = normalize_text(source.domain or "").lower()
        title_or_url = f"{source.title or ''} {source.url or ''}".lower()
        if source.source_tier in {"official", "aggregate"}:
            return True
        if any(token in title_or_url for token in contact_page_tokens):
            return True
        if domain in deps.generic_content_domains:
            return False
        return False

    for source in sources:
        text = deps.source_text(source)
        emails = deps.email_pattern.findall(text)
        phones = deps.phone_pattern.findall(text)
        contacts = contact_person_pattern.findall(text)
        agencies = agency_pattern.findall(text)
        domain = normalize_text(source.domain or "")
        label = normalize_text(source.source_label or domain or source.title)
        title_or_url = f"{source.title or ''} {source.url or ''}".lower()
        contact_departments = [normalize_text(item[0]) for item in department_contact_pattern.findall(text)]
        line_contacts = line_contact_pattern.findall(text)
        for _, person in contacts[:2]:
            row = f"{label}：公开联系人 {normalize_text(person)}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for department in contact_departments[:2]:
            row = f"{label}：可能归口部门 {department}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for owner, field_name, value in line_contacts[:2]:
            normalized_owner = normalize_text(owner)
            normalized_value = normalize_text(value)
            if not normalized_value or not is_valid_contact_value(normalized_value):
                continue
            row = f"{label}：{normalized_owner}{field_name} {normalized_value}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for _, agency in agencies[:1]:
            row = f"{label}：代理/服务机构 {normalize_text(agency)}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for email in emails[:2]:
            if not is_valid_contact_value(email):
                continue
            row = f"{label}：公开邮箱 {email}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        for phone in phones[:2]:
            if not is_valid_contact_value(phone):
                continue
            row = f"{label}：公开电话 {normalize_text(phone)}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        if domain and allow_public_entry(source):
            row = f"{label}：官网/公开入口 https://{domain}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        if any(token in title_or_url for token in contact_page_tokens) and is_valid_contact_value(source.url or ""):
            row = f"{label}：高概率公开联系页 {source.url or f'https://{domain}'}"
            if row not in seen:
                seen.add(row)
                rows.append(row)
        if len(rows) >= limit:
            break
    if rows:
        return rows[:limit]
    return deps.dedupe_strings(
        [
            localized_text(
                output_language,
                {
                    "zh-CN": "当前证据不足：建议优先查看甲方官网“联系我们”与采购公告联系人信息。",
                    "zh-TW": "目前證據不足：建議優先查看甲方官網「聯絡我們」與採購公告聯絡人資訊。",
                    "en": "Evidence is insufficient: verify public contact channels through the buyer website and procurement notices.",
                },
                "当前证据不足：建议优先查看甲方官网“联系我们”与采购公告联系人信息。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "建议补充公开服务热线、采购公告联系人或投资者关系邮箱后重新生成。",
                    "zh-TW": "建議補充公開服務熱線、採購公告聯絡人或投資者關係郵箱後重新生成。",
                    "en": "Add public hotlines, procurement contacts, or investor relations emails and rerun.",
                },
                "建议补充公开服务热线、采购公告联系人或投资者关系邮箱后重新生成。",
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "建议将关键词收敛到具体甲方公司或项目名称，以提升公开联系方式命中率。",
                    "zh-TW": "建議將關鍵詞收斂到具體甲方公司或專案名稱，以提升公開聯絡方式命中率。",
                    "en": "Narrow the keyword to a specific buyer or project to improve public contact matching.",
                },
                "建议将关键词收敛到具体甲方公司或项目名称，以提升公开联系方式命中率。",
            ),
        ],
        limit,
    )
