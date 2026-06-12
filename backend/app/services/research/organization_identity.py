from __future__ import annotations

from functools import lru_cache
import re

from app.services.content_extractor import extract_domain, normalize_text
from app.services.research.entity_policy import (
    COMPACT_ENTITY_PATTERN,
    ENTITY_SUFFIX_TOKENS,
    KNOWN_LIGHTWEIGHT_ENTITY_NAMES,
    ORG_PATTERN,
    SPECIAL_ENTITY_ALIASES,
    contains_low_value_entity_token,
    is_lightweight_entity_name,
    is_plausible_entity_name,
    looks_like_fragment_entity_name,
    strip_entity_leading_noise,
    trim_product_spec_from_entity_name,
)
from app.services.research.report_common import dedupe_strings
from app.services.research.scope_entity_runtime_dependencies import scope_term_dependencies
from app.services.research.scope_terms import looks_like_scope_prompt_noise
from app.services.research.source_documents import SourceDocument, source_document_text


KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS: dict[str, tuple[tuple[str, str], ...]] = {
    "爱奇艺": (
        ("https://www.iqiyi.com/", "爱奇艺官网"),
        ("https://ir.iqiyi.com/", "爱奇艺投资者关系"),
    ),
    "快手": (
        ("https://www.kuaishou.com/", "快手官网"),
        ("https://ir.kuaishou.com/", "快手投资者关系"),
    ),
    "抖音": (
        ("https://www.douyin.com/", "抖音官网"),
        ("https://www.bytedance.com/zh/", "字节跳动官网"),
    ),
    "字节跳动": (
        ("https://www.bytedance.com/zh/", "字节跳动官网"),
        ("https://www.bytedance.com/zh/contact", "字节跳动联系我们"),
    ),
    "阿里云": (
        ("https://www.aliyun.com/", "阿里云官网"),
        ("https://www.alibabagroup.com/cn/global/home", "阿里巴巴集团官网"),
    ),
    "优酷": (
        ("https://www.youku.com/", "优酷官网"),
        ("https://www.alibabagroup.com/cn/global/home", "阿里巴巴集团官网"),
    ),
    "腾讯云": (
        ("https://cloud.tencent.com/", "腾讯云官网"),
        ("https://www.tencent.com/zh-cn/", "腾讯官网"),
    ),
    "腾讯视频": (
        ("https://v.qq.com/", "腾讯视频官网"),
        ("https://www.tencent.com/zh-cn/", "腾讯官网"),
    ),
    "腾讯动漫": (
        ("https://ac.qq.com/", "腾讯动漫官网"),
        ("https://www.tencent.com/zh-cn/", "腾讯官网"),
    ),
    "华为": (
        ("https://www.huawei.com/cn/", "华为官网"),
        ("https://www.huawei.com/cn/contact-us", "华为联系我们"),
    ),
    "哔哩哔哩": (
        ("https://www.bilibili.com/", "哔哩哔哩官网"),
        ("https://ir.bilibili.com/", "哔哩哔哩投资者关系"),
    ),
    "快看漫画": (
        ("https://www.kuaikanmanhua.com/", "快看漫画官网"),
        ("https://www.kuaikanmanhua.com/about", "快看漫画公开入口"),
    ),
    "阅文集团": (
        ("https://www.yuewen.com/", "阅文集团官网"),
        ("https://ir.yuewen.com/", "阅文集团投资者关系"),
    ),
    "芒果超媒": (
        ("https://www.mgtv.com/", "芒果TV官网"),
        ("https://www.mangomedia.com.cn/", "芒果超媒官网"),
    ),
    "小红书": (
        ("https://www.xiaohongshu.com/", "小红书官网"),
        ("https://www.xiaohongshu.com/explore", "小红书公开入口"),
    ),
    "美图": (
        ("https://www.meitu.com/", "美图官网"),
        ("https://ir.meitu.com/", "美图投资者关系"),
    ),
    "中文在线": (
        ("https://www.col.com/", "中文在线官网"),
        ("https://www.col.com/About/contact", "中文在线联系我们"),
    ),
    "掌阅科技": (
        ("https://www.zhangyue.com/", "掌阅官网"),
        ("https://www.zhangyue.com/about", "掌阅公开入口"),
    ),
    "华策影视": (
        ("https://www.huacemedia.com/", "华策影视官网"),
        ("https://www.huacemedia.com/contact", "华策影视联系我们"),
    ),
    "光线传媒": (
        ("https://www.ewang.com/", "光线传媒官网"),
        ("https://www.ewang.com/about", "光线传媒公开入口"),
    ),
    "上海儒意": (
        ("https://www.ruyi.cn/", "儒意官网"),
        ("https://www.ruyi.cn/contact", "儒意联系我们"),
    ),
    "追光动画": (
        ("https://www.zhuiguang.com/", "追光动画官网"),
        ("https://www.zhuiguang.com/about", "追光动画公开入口"),
    ),
    "中兴通讯": (
        ("https://www.zte.com.cn/china/", "中兴通讯官网"),
        ("https://www.zte.com.cn/china/about/contact", "中兴通讯联系我们"),
    ),
    "中国移动": (
        ("https://www.10086.cn/", "中国移动官网"),
        ("https://ir.chinamobile.com/", "中国移动投资者关系"),
    ),
    "中国电信": (
        ("https://www.189.cn/", "中国电信官网"),
        ("https://www.chinatelecom-h.com/", "中国电信投资者关系"),
    ),
    "中国联通": (
        ("https://www.10010.com/", "中国联通官网"),
        ("https://www.chinaunicom.com.hk/", "中国联通投资者关系"),
    ),
    "神州数码": (
        ("https://www.digitalchina.com/", "神州数码官网"),
        ("https://www.digitalchina.com/Contact/index.html", "神州数码联系我们"),
    ),
    "新华三": (
        ("https://www.h3c.com/cn/", "新华三官网"),
        ("https://www.h3c.com/cn/About_H3C/Contact_Us/", "新华三联系我们"),
    ),
    "软通动力": (
        ("https://www.isoftstone.com/", "软通动力官网"),
        ("https://www.isoftstone.com/contact", "软通动力联系我们"),
    ),
    "太极股份": (
        ("https://www.taiji.com.cn/", "太极股份官网"),
        ("https://www.taiji.com.cn/col/col25/index.html", "太极股份联系我们"),
    ),
    "德勤": (
        ("https://www2.deloitte.com/cn/zh.html", "德勤官网"),
        ("https://www2.deloitte.com/cn/zh/pages/about-deloitte/articles/contact-us.html", "德勤联系我们"),
    ),
    "埃森哲": (
        ("https://www.accenture.com/cn-zh", "埃森哲官网"),
        ("https://www.accenture.com/cn-zh/about/contact-us", "埃森哲联系我们"),
    ),
}

RESEARCH_ACCOUNT_ALIAS_MAP = {
    "微软": "Microsoft",
    "Open AI": "OpenAI",
    "上海市文旅局": "上海市文化和旅游局",
    "华为云服务": "华为云",
    "阿里巴巴云": "阿里云",
    "腾讯视频": "腾讯",
    "腾讯动漫": "腾讯",
}

OFFICIAL_DOMAIN_ENTITY_MAP: dict[str, str] = {}
for canonical_name, seed_sources in KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.items():
    for seed_url, _ in seed_sources:
        seed_domain = normalize_text(extract_domain(seed_url) or "").lower().removeprefix("www.")
        if seed_domain:
            OFFICIAL_DOMAIN_ENTITY_MAP.setdefault(seed_domain, canonical_name)

PUBLIC_ORG_SUFFIXES = (
    "集团官网", "官网入口", "官网主页", "官网首页", "官方网站", "官网", "投资者关系",
    "投资者关系主页", "联系我们", "公开入口", "品牌官网",
)


@lru_cache(maxsize=8192)
def strip_org_public_suffixes(value: str) -> str:
    stripped = normalize_text(value)
    if not stripped:
        return ""
    changed = True
    while changed:
        changed = False
        for suffix in PUBLIC_ORG_SUFFIXES:
            if stripped.endswith(suffix) and len(stripped) > len(suffix) + 1:
                stripped = normalize_text(stripped[: -len(suffix)])
                changed = True
                break
    return stripped


@lru_cache(maxsize=1)
def normalized_entity_suffixes() -> tuple[str, ...]:
    return tuple(
        sorted(
            {normalize_text(suffix) for suffix in ENTITY_SUFFIX_TOKENS if normalize_text(suffix)},
            key=len,
            reverse=True,
        )
    )


@lru_cache(maxsize=16384)
def entity_alias_lookup_key(value: str) -> str:
    lowered = strip_org_public_suffixes(value).lower()
    stripped = lowered
    changed = True
    while changed:
        changed = False
        for suffix in normalized_entity_suffixes():
            suffix_lower = suffix.lower()
            if stripped.endswith(suffix_lower) and len(stripped) > len(suffix_lower) + 1:
                stripped = stripped[: -len(suffix_lower)]
                changed = True
                break
    return re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "", stripped) or lowered


@lru_cache(maxsize=8192)
def org_surface_variants(value: str) -> tuple[str, ...]:
    normalized = strip_org_public_suffixes(value)
    if not normalized:
        return ()
    variants = [normalized]
    cleaned = strip_entity_leading_noise(normalized)
    if cleaned and cleaned not in variants:
        variants.append(cleaned)
    bracketless = normalize_text(re.sub(r"[（(][^（）()]{1,24}[）)]", "", normalized))
    if bracketless and bracketless not in variants:
        variants.append(bracketless)
    stripped = normalized
    changed = True
    while changed:
        changed = False
        for suffix in normalized_entity_suffixes():
            if stripped.endswith(suffix) and len(stripped) > len(suffix) + 1:
                stripped = normalize_text(stripped[: -len(suffix)])
                changed = True
                break
    scope_deps = scope_term_dependencies()
    if (
        stripped
        and stripped != normalized
        and len(stripped) >= 2
        and stripped not in variants
        and not looks_like_scope_prompt_noise(stripped, deps=scope_deps)
        and not contains_low_value_entity_token(stripped)
    ):
        variants.append(stripped)
    return tuple(dedupe_strings(variants, 6))


def scope_org_names(scope_hints: dict[str, object] | None) -> list[str]:
    scope = scope_hints or {}
    return dedupe_strings(
        [
            *(scope.get("company_anchors", []) or []),
            *(scope.get("clients", []) or []),
            *(scope.get("seed_companies", []) or []),
        ],
        24,
    )


def org_alias_map(scope_hints: dict[str, object] | None) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    candidates = [*KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS, *SPECIAL_ENTITY_ALIASES, *scope_org_names(scope_hints)]
    for canonical in candidates:
        for alias in org_surface_variants(canonical):
            alias_map.setdefault(entity_alias_lookup_key(alias), normalize_text(canonical))
    for alias, canonical in RESEARCH_ACCOUNT_ALIAS_MAP.items():
        alias_map[entity_alias_lookup_key(alias)] = canonical
        alias_map[entity_alias_lookup_key(canonical)] = canonical
    return alias_map


def resolve_known_org_name(
    value: str,
    *,
    scope_hints: dict[str, object] | None = None,
    source: SourceDocument | None = None,
) -> str:
    normalized = strip_org_public_suffixes(value)
    if not normalized:
        return ""
    alias_map = org_alias_map(scope_hints)
    resolved = normalized
    for variant in org_surface_variants(normalized):
        mapped = alias_map.get(entity_alias_lookup_key(variant))
        if mapped:
            resolved = mapped
            break
    if source is not None:
        domain_canonical = canonical_org_name_from_domain(source.domain or extract_domain(source.url))
        if domain_canonical:
            text = source_document_text(source)
            if any(alias in text for alias in org_surface_variants(domain_canonical)) or is_lightweight_entity_name(resolved):
                return domain_canonical
    return resolved


def canonical_org_name_from_domain(domain: str | None) -> str:
    normalized = normalize_text(domain or "").lower().removeprefix("www.")
    if not normalized:
        return ""
    for known_domain, canonical_name in OFFICIAL_DOMAIN_ENTITY_MAP.items():
        if normalized == known_domain or normalized.endswith(f".{known_domain}"):
            return canonical_name
    return ""


def extract_rank_entity_candidates(
    value: str,
    *,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    candidates = [*ORG_PATTERN.findall(text), *COMPACT_ENTITY_PATTERN.findall(text)]
    candidates.extend(alias for alias in KNOWN_LIGHTWEIGHT_ENTITY_NAMES if alias in text)
    candidates.extend(
        canonical
        for canonical in [
            *KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS,
            *SPECIAL_ENTITY_ALIASES,
            *RESEARCH_ACCOUNT_ALIAS_MAP,
            *scope_org_names(scope_hints),
        ]
        if any(alias in text for alias in org_surface_variants(canonical))
    )
    filtered: list[str] = []
    for candidate in candidates:
        normalized = resolve_known_org_name(candidate, scope_hints=scope_hints)
        normalized = strip_entity_leading_noise(trim_product_spec_from_entity_name(normalized))
        if not (is_plausible_entity_name(normalized) or is_lightweight_entity_name(normalized)):
            continue
        if looks_like_fragment_entity_name(normalized):
            continue
        if (
            any(connector in normalized for connector in ("与", "及", "和"))
            and normalized not in SPECIAL_ENTITY_ALIASES
            and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS)
        ):
            continue
        filtered.append(normalized)
    return dedupe_strings(filtered, 5)


def org_entity_variants(value: str, *, scope_hints: dict[str, object] | None = None) -> list[str]:
    canonical = resolve_known_org_name(value, scope_hints=scope_hints)
    if not canonical:
        return []
    variants = list(org_surface_variants(canonical))
    for alias, mapped in RESEARCH_ACCOUNT_ALIAS_MAP.items():
        if normalize_text(mapped) == canonical:
            variants.extend(org_surface_variants(alias))
    for candidate in [*KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS, *SPECIAL_ENTITY_ALIASES, *scope_org_names(scope_hints)]:
        if resolve_known_org_name(candidate, scope_hints=scope_hints) == canonical:
            variants.extend(org_surface_variants(candidate))
    return dedupe_strings(variants, 10)


def entity_canonical_key(value: str) -> str:
    return entity_alias_lookup_key(resolve_known_org_name(value))


def source_mentions_entity(source: SourceDocument, entity_name: str) -> bool:
    normalized_name = normalize_text(entity_name)
    if not normalized_name:
        return False
    text = source_document_text(source)
    if any(variant in text for variant in org_entity_variants(normalized_name)):
        return True
    canonical_name = entity_canonical_key(normalized_name)
    canonical_text = re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", "", text.lower())
    return bool(canonical_name and canonical_text and canonical_name in canonical_text)
