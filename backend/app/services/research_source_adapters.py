from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from typing import Iterable
from urllib import parse, request
import xml.etree.ElementTree as ET

from app.services.content_extractor import normalize_text


REGION_SCOPE_ALIASES: dict[str, tuple[str, ...]] = {
    "长三角": ("长三角", "上海", "江苏", "浙江", "安徽", "南京", "苏州", "杭州", "宁波", "无锡", "合肥"),
    "京津冀": ("京津冀", "北京", "天津", "河北"),
    "粤港澳": ("粤港澳", "广东", "广州", "深圳", "珠海", "佛山", "东莞", "中山", "香港", "澳门"),
    "成渝": ("成渝", "成都", "重庆", "四川"),
}


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP_DIR = PROJECT_ROOT / ".tmp"
SETTINGS_FILE = TMP_DIR / "research_source_settings.json"

DEFAULT_ENABLE_JIANYU_TENDER_FEED = True
DEFAULT_ENABLE_YUNTOUTIAO_FEED = True
DEFAULT_ENABLE_GGZY_FEED = True
DEFAULT_ENABLE_CECBID_FEED = True
DEFAULT_ENABLE_CCGP_FEED = True
DEFAULT_ENABLE_GOV_POLICY_FEED = True
DEFAULT_ENABLE_LOCAL_GGZY_FEED = True

JIANYU_HOME_URL = "https://www.jianyu360.com/"
YUNTOUTIAO_HOME_URL = "https://www.yuntoutiao.com/"
GGZY_HOME_URL = "https://www.ggzy.gov.cn/"
CECBID_HOME_URL = "https://www.cecbid.org.cn/"
DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/?q="
PROCUREMENT_COMPLIANT_DOMAINS = (
    "cebpubservice.com",
    "china-cpp.com",
    "chinabidding.com",
)

THEME_ALIASES: dict[str, tuple[str, ...]] = {
    "政务云": ("政务", "政府", "云", "云平台", "数据", "大数据", "数据中心", "信息化", "数字化", "平台"),
    "政务": ("政务", "政府", "财政", "采购", "预算", "信息化", "数字化"),
    "大模型": ("大模型", "模型", "训练数据", "算力", "人工智能", "智能", "AI"),
    "人工智能": ("人工智能", "AI", "智能", "大模型", "模型", "算力"),
    "数据中心": ("数据中心", "数据", "算力", "服务器", "机房", "存储"),
    "信息化": ("信息化", "数字化", "系统", "平台", "软件", "集成", "网络"),
    "网络安全": ("网络安全", "安全", "等保", "态势感知", "平台", "系统"),
    "智慧城市": ("智慧城市", "城市", "平台", "智能化", "数字化", "治理"),
}

GENERIC_MATCH_TOKENS = {
    "预算", "招标", "采购", "中标", "甲方", "竞品", "生态伙伴", "生态", "伙伴", "领导讲话",
    "领导", "讲话", "项目", "商机", "区域", "行业", "客户", "公司", "同行", "战略", "规划",
}

JIANYU_PRIORITY_SECTIONS = {
    "招标公告": 18,
    "招标预告": 16,
    "中标成交": 16,
    "采购意向": 15,
    "项目分包": 14,
}


@dataclass(slots=True)
class ResearchSourceSettings:
    enable_jianyu_tender_feed: bool = DEFAULT_ENABLE_JIANYU_TENDER_FEED
    enable_yuntoutiao_feed: bool = DEFAULT_ENABLE_YUNTOUTIAO_FEED
    enable_ggzy_feed: bool = DEFAULT_ENABLE_GGZY_FEED
    enable_cecbid_feed: bool = DEFAULT_ENABLE_CECBID_FEED
    enable_ccgp_feed: bool = DEFAULT_ENABLE_CCGP_FEED
    enable_gov_policy_feed: bool = DEFAULT_ENABLE_GOV_POLICY_FEED
    enable_local_ggzy_feed: bool = DEFAULT_ENABLE_LOCAL_GGZY_FEED
    updated_at: datetime | None = None

    def enabled_labels(self) -> list[str]:
        labels: list[str] = []
        if self.enable_jianyu_tender_feed:
            labels.append("剑鱼标讯")
        if self.enable_yuntoutiao_feed:
            labels.append("云头条")
        if self.enable_ggzy_feed:
            labels.append("全国公共资源交易平台")
        if self.enable_cecbid_feed:
            labels.append("中国招标投标网")
        if self.enable_ccgp_feed:
            labels.append("政府采购合规聚合")
        if self.enable_gov_policy_feed:
            labels.append("中国政府网政策/讲话")
        if self.enable_local_ggzy_feed:
            labels.append("地方公共资源交易平台")
        return labels


@dataclass(slots=True)
class ResearchCrawlerHit:
    title: str
    url: str
    snippet: str
    search_query: str
    source_hint: str
    source_label: str


def build_research_connector_statuses(
    settings: ResearchSourceSettings | None = None,
) -> list[dict[str, object]]:
    resolved = settings or read_research_source_settings()
    public_sources_active = any(
        [
            resolved.enable_jianyu_tender_feed,
            resolved.enable_yuntoutiao_feed,
            resolved.enable_ggzy_feed,
            resolved.enable_cecbid_feed,
            resolved.enable_ccgp_feed,
            resolved.enable_gov_policy_feed,
            resolved.enable_local_ggzy_feed,
        ]
    )
    official_sources_active = any(
        [
            resolved.enable_ggzy_feed,
            resolved.enable_cecbid_feed,
            resolved.enable_ccgp_feed,
            resolved.enable_gov_policy_feed,
            resolved.enable_local_ggzy_feed,
        ]
    )
    return [
        {
            "key": "public_open_source_adapters",
            "label": "公开招采与行业源适配器",
            "status": "active" if public_sources_active else "available",
            "detail": "当前已接入公开招投标、政策讲话、行业媒体与聚合源；不绕过登录墙和付费墙。",
            "requires_authorization": False,
        },
        {
            "key": "official_policy_procurement_connectors",
            "label": "官方政策与采购公开源",
            "status": "active" if official_sources_active else "available",
            "detail": "优先走政府、公共资源交易、上市披露等官方公开站点，作为高可信证据层。",
            "requires_authorization": False,
        },
        {
            "key": "authorized_enterprise_procurement_api",
            "label": "企业采购授权接口",
            "status": "authorization_required",
            "detail": "如需更高命中率，可接入你合法持有的采购/招采 SaaS 授权接口或令牌型数据源。",
            "requires_authorization": True,
        },
        {
            "key": "authorized_wechat_archive_connector",
            "label": "授权微信/企业归档连接器",
            "status": "authorization_required",
            "detail": "如需把合规归档内容并入研报，请通过企业微信、会话存档或其他合法归档能力接入。",
            "requires_authorization": True,
        },
    ]


def _ensure_tmp_dir() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def read_research_source_settings() -> ResearchSourceSettings:
    if not SETTINGS_FILE.exists():
        return ResearchSourceSettings()
    try:
        loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ResearchSourceSettings()
    updated_at = None
    raw_updated = loaded.get("updated_at")
    if raw_updated:
        try:
            updated_at = datetime.fromisoformat(str(raw_updated).replace("Z", "+00:00"))
        except ValueError:
            updated_at = None
    return ResearchSourceSettings(
        enable_jianyu_tender_feed=bool(loaded.get("enable_jianyu_tender_feed", DEFAULT_ENABLE_JIANYU_TENDER_FEED)),
        enable_yuntoutiao_feed=bool(loaded.get("enable_yuntoutiao_feed", DEFAULT_ENABLE_YUNTOUTIAO_FEED)),
        enable_ggzy_feed=bool(loaded.get("enable_ggzy_feed", DEFAULT_ENABLE_GGZY_FEED)),
        enable_cecbid_feed=bool(loaded.get("enable_cecbid_feed", DEFAULT_ENABLE_CECBID_FEED)),
        enable_ccgp_feed=bool(loaded.get("enable_ccgp_feed", DEFAULT_ENABLE_CCGP_FEED)),
        enable_gov_policy_feed=bool(loaded.get("enable_gov_policy_feed", DEFAULT_ENABLE_GOV_POLICY_FEED)),
        enable_local_ggzy_feed=bool(loaded.get("enable_local_ggzy_feed", DEFAULT_ENABLE_LOCAL_GGZY_FEED)),
        updated_at=updated_at,
    )


def write_research_source_settings(
    *,
    enable_jianyu_tender_feed: bool,
    enable_yuntoutiao_feed: bool,
    enable_ggzy_feed: bool,
    enable_cecbid_feed: bool,
    enable_ccgp_feed: bool,
    enable_gov_policy_feed: bool,
    enable_local_ggzy_feed: bool,
) -> ResearchSourceSettings:
    _ensure_tmp_dir()
    payload = {
        "enable_jianyu_tender_feed": bool(enable_jianyu_tender_feed),
        "enable_yuntoutiao_feed": bool(enable_yuntoutiao_feed),
        "enable_ggzy_feed": bool(enable_ggzy_feed),
        "enable_cecbid_feed": bool(enable_cecbid_feed),
        "enable_ccgp_feed": bool(enable_ccgp_feed),
        "enable_gov_policy_feed": bool(enable_gov_policy_feed),
        "enable_local_ggzy_feed": bool(enable_local_ggzy_feed),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    SETTINGS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return read_research_source_settings()


def _fetch_html(url: str, *, timeout_seconds: int, allow_insecure: bool = False) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        )
    }
    try:
        req = request.Request(url, headers=headers)
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        command = ["curl", "-L", "--max-time", str(timeout_seconds), url]
        if allow_insecure:
            command.insert(1, "-k")
        run = subprocess.run(
            command,
            capture_output=True,
            timeout=max(timeout_seconds + 2, 6),
            check=False,
        )
        if run.returncode != 0:
            raise RuntimeError(run.stderr.decode("utf-8", errors="ignore") or f"curl failed: {url}")
        return run.stdout.decode("utf-8", errors="ignore")


def _build_match_tokens(keyword: str, research_focus: str | None) -> list[str]:
    values = [normalize_text(keyword), normalize_text(research_focus or "")]
    tokens: list[str] = []
    for value in values:
        if not value:
            continue
        rough = re.split(r"[\s,，、/|:：;；（）()]+", value)
        for token in rough:
            normalized = normalize_text(token)
            if len(normalized) >= 2:
                if normalized in GENERIC_MATCH_TOKENS:
                    continue
                tokens.append(normalized.lower())
                if normalized in THEME_ALIASES:
                    tokens.extend(alias.lower() for alias in THEME_ALIASES[normalized])
            compact = re.sub(r"\s+", "", normalized)
            if 2 <= len(compact) <= 16:
                if compact in GENERIC_MATCH_TOKENS:
                    continue
                tokens.append(compact.lower())
                for trigger, aliases in THEME_ALIASES.items():
                    if trigger in compact:
                        tokens.extend(alias.lower() for alias in aliases)
    return list(dict.fromkeys(item for item in tokens if item))


def _score_candidate(
    *,
    title: str,
    snippet: str,
    section: str = "",
    tokens: Iterable[str],
    source_label: str,
) -> int:
    haystack = normalize_text(" ".join([title, snippet, section])).lower()
    if not haystack:
        return 0
    token_hit_count = 0
    score = 0
    for token in tokens:
        if token and token in haystack:
            token_hit_count += 1
            score += 4 if len(token) >= 3 else 2
    if token_hit_count == 0:
        return 0
    if any(word in haystack for word in ("招标", "采购", "中标", "预算", "项目", "二期", "三期", "四期", "立项")):
        score += 3
    if source_label == "剑鱼标讯":
        score += JIANYU_PRIORITY_SECTIONS.get(section, 0)
    if source_label == "云头条" and any(word in haystack for word in ("云", "大模型", "算力", "AI", "平台", "战略")):
        score += 5
    return score


class _YuntoutiaoSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.entries: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_title: str = ""
        self._capture_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        attrs_map = {str(k).lower(): str(v) for k, v in attrs if k and v}
        if tag.lower() == "a" and attrs_map.get("href", "").endswith(".html"):
            self._current_href = attrs_map.get("href", "")
            self._current_title = normalize_text(attrs_map.get("title", ""))
            self._capture_title = True

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag.lower() == "a" and self._current_href:
            href = self._current_href
            title = self._current_title
            if href and title:
                self.entries.append({"href": href, "title": title})
            self._current_href = None
            self._current_title = ""
            self._capture_title = False

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self._capture_title and self._current_href:
            text = normalize_text(data)
            if text and len(self._current_title) < len(text):
                self._current_title = text


def _extract_meta_description(html: str) -> str:
    match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return normalize_text(unescape(match.group(1)))


def _crawl_yuntoutiao_hits(
    keyword: str,
    research_focus: str | None,
    *,
    timeout_seconds: int,
    limit: int,
) -> list[ResearchCrawlerHit]:
    search_url = f"{YUNTOUTIAO_HOME_URL}search/?keyword={parse.quote(keyword)}"
    html = _fetch_html(search_url, timeout_seconds=timeout_seconds)
    parser = _YuntoutiaoSearchParser()
    parser.feed(html)

    tokens = _build_match_tokens(keyword, research_focus)
    hits: list[tuple[int, ResearchCrawlerHit]] = []
    seen_urls: set[str] = set()
    for entry in parser.entries:
        url = parse.urljoin(YUNTOUTIAO_HOME_URL, entry["href"])
        if url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            detail_html = _fetch_html(url, timeout_seconds=min(timeout_seconds, 8))
        except Exception:
            detail_html = ""
        snippet = _extract_meta_description(detail_html) or entry["title"]
        score = _score_candidate(
            title=entry["title"],
            snippet=snippet,
            tokens=tokens,
            source_label="云头条",
        )
        if score <= 0 and len(hits) >= limit:
            continue
        hits.append(
            (
                score,
                ResearchCrawlerHit(
                    title=entry["title"],
                    url=url,
                    snippet=f"云头条 · {_truncate(snippet, 108)}",
                    search_query=f"云头条站内搜索: {keyword}",
                    source_hint="tech_media_feed",
                    source_label="云头条",
                ),
            )
        )

    hits.sort(key=lambda item: item[0], reverse=True)
    direct_hits = [hit for score, hit in hits if score > 0]
    return direct_hits[:limit]


def _truncate(value: str, limit: int) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip(' ，,：:；;')}…"


def _extract_jianyu_sections(html: str) -> list[tuple[str, list[tuple[str, str, str]]]]:
    sections: list[tuple[str, list[tuple[str, str, str]]]] = []
    section_pattern = re.compile(
        r'<h3 class="cms-card-title">(.*?)</h3>.*?<ul class="cms-card-list clearfix">(.*?)</ul>',
        re.DOTALL,
    )
    item_pattern = re.compile(
        r'<a class="cms-card-list-item-left[^"]*"[^>]*title="(.*?)" href="(.*?)"[^>]*>.*?</a>\s*'
        r'<span class="cms-card-list-item-right">(.*?)</span>',
        re.DOTALL,
    )
    for section_title, block in section_pattern.findall(html):
        normalized_section = normalize_text(unescape(section_title))
        if normalized_section not in JIANYU_PRIORITY_SECTIONS:
            continue
        items: list[tuple[str, str, str]] = []
        for title, href, date_text in item_pattern.findall(block):
            normalized_title = normalize_text(unescape(title))
            normalized_href = parse.urljoin(JIANYU_HOME_URL, href)
            normalized_date = normalize_text(date_text)
            if normalized_title and normalized_href:
                items.append((normalized_title, normalized_href, normalized_date))
        if items:
            sections.append((normalized_section, items))
    return sections


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.entries: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_title: list[str] = []
        self._capture_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        attrs_map = {str(k).lower(): str(v) for k, v in attrs if k and v}
        if tag.lower() == "a" and "result__a" in attrs_map.get("class", ""):
            self._current_href = attrs_map.get("href", "")
            self._current_title = []
            self._capture_title = True

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag.lower() == "a" and self._current_href:
            href = _unwrap_duckduckgo_link(self._current_href)
            title = normalize_text(" ".join(self._current_title))
            if href and title:
                self.entries.append({"href": href, "title": title})
            self._current_href = None
            self._current_title = []
            self._capture_title = False

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self._capture_title and self._current_href:
            text = normalize_text(data)
            if text:
                self._current_title.append(text)


def _unwrap_duckduckgo_link(url: str) -> str:
    raw = unescape(url or "").strip()
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = f"https:{raw}"
    parsed = parse.urlparse(raw)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        params = parse.parse_qs(parsed.query)
        redirect = params.get("uddg")
        if redirect:
            return parse.unquote(redirect[0])
    return raw


def _search_domain_hits(
    query: str,
    *,
    timeout_seconds: int,
    limit: int,
    source_label: str,
    source_hint: str,
    allowed_domains: tuple[str, ...] = (),
    domain_keyword: str | None = None,
    tokens: list[str],
) -> list[ResearchCrawlerHit]:
    entries: list[dict[str, str]] = []
    try:
        rss = _fetch_html(
            f"https://www.bing.com/search?format=rss&q={parse.quote_plus(query)}",
            timeout_seconds=timeout_seconds,
        )
        root = ET.fromstring(rss)
        for item in root.findall("./channel/item"):
            title = normalize_text(item.findtext("title") or "")
            href = normalize_text(item.findtext("link") or "")
            if title and href:
                entries.append({"href": href, "title": title})
    except Exception:
        entries = []

    if not entries:
        html = _fetch_html(
            f"{DUCKDUCKGO_HTML_URL}{parse.quote_plus(query)}",
            timeout_seconds=timeout_seconds,
        )
        parser = _DuckDuckGoResultParser()
        parser.feed(html)
        entries = parser.entries

    hits: list[tuple[int, ResearchCrawlerHit]] = []
    seen_urls: set[str] = set()
    for entry in entries:
        url = normalize_text(entry.get("href", ""))
        title = normalize_text(entry.get("title", ""))
        if not url or not title or url in seen_urls:
            continue
        domain = (parse.urlparse(url).netloc or "").lower()
        if allowed_domains and not any(allowed in domain for allowed in allowed_domains):
            continue
        if domain_keyword and domain_keyword not in domain and domain_keyword not in normalize_text(url).lower():
            continue
        seen_urls.add(url)
        try:
            detail_html = _fetch_html(url, timeout_seconds=min(timeout_seconds, 8), allow_insecure=True)
        except Exception:
            detail_html = ""
        snippet = _extract_meta_description(detail_html) or title
        score = _score_candidate(
            title=title,
            snippet=snippet,
            tokens=tokens,
            source_label=source_label,
        )
        if score <= 0:
            continue
        hits.append(
            (
                score,
                ResearchCrawlerHit(
                    title=title,
                    url=url,
                    snippet=f"{source_label} · {_truncate(snippet, 108)}",
                    search_query=query,
                    source_hint=source_hint,
                    source_label=source_label,
                ),
            )
        )
    hits.sort(key=lambda item: item[0], reverse=True)
    return [hit for score, hit in hits if score > 0][:limit]


def _crawl_jianyu_hits(
    keyword: str,
    research_focus: str | None,
    *,
    timeout_seconds: int,
    limit: int,
) -> list[ResearchCrawlerHit]:
    html = _fetch_html(JIANYU_HOME_URL, timeout_seconds=timeout_seconds, allow_insecure=True)
    tokens = _build_match_tokens(keyword, research_focus)
    sections = _extract_jianyu_sections(html)

    hits: list[tuple[int, ResearchCrawlerHit]] = []
    for section, items in sections:
        for title, url, date_text in items:
            snippet = f"剑鱼标讯 · {section} · {date_text or '最新'}"
            score = _score_candidate(
                title=title,
                snippet=snippet,
                section=section,
                tokens=tokens,
                source_label="剑鱼标讯",
            )
            hits.append(
                (
                    score,
                    ResearchCrawlerHit(
                        title=title,
                        url=url,
                        snippet=snippet,
                        search_query=f"剑鱼标讯公开招采流: {keyword}",
                        source_hint="tender_feed",
                        source_label="剑鱼标讯",
                    ),
                )
            )

    hits.sort(key=lambda item: item[0], reverse=True)
    direct_hits = [hit for score, hit in hits if score > 0]
    return direct_hits[:limit]


def _crawl_ggzy_hits(
    keyword: str,
    research_focus: str | None,
    *,
    timeout_seconds: int,
    limit: int,
) -> list[ResearchCrawlerHit]:
    html = _fetch_html(GGZY_HOME_URL, timeout_seconds=timeout_seconds, allow_insecure=True)
    tokens = _build_match_tokens(keyword, research_focus)
    section_pattern = re.compile(
        r"<h4>(交易公告|成交公示).*?</h4>\s*<ul>(.*?)</ul>",
        re.DOTALL,
    )
    item_pattern = re.compile(
        r'<a href="([^"]+)"[^>]*>\s*(.*?)\s*</a>.*?<span>(\d{4}-\d{2}-\d{2})</span>',
        re.DOTALL,
    )
    hits: list[tuple[int, ResearchCrawlerHit]] = []
    seen_urls: set[str] = set()
    for section, block in section_pattern.findall(html):
        for href, title, date_text in item_pattern.findall(block):
            url = parse.urljoin(GGZY_HOME_URL, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            normalized_title = normalize_text(unescape(title))
            if not normalized_title:
                continue
            snippet = f"全国公共资源交易平台 · {section} · {normalize_text(date_text)}"
            score = _score_candidate(
                title=normalized_title,
                snippet=snippet,
                section=section,
                tokens=tokens,
                source_label="全国公共资源交易平台",
            )
            hits.append(
                (
                    score,
                    ResearchCrawlerHit(
                        title=normalized_title,
                        url=url,
                        snippet=snippet,
                        search_query=f"全国公共资源交易平台公开流: {keyword}",
                        source_hint="official_tender_feed",
                        source_label="全国公共资源交易平台",
                    ),
                )
            )
    hits.sort(key=lambda item: item[0], reverse=True)
    return [hit for score, hit in hits if score > 0][:limit]


def _crawl_cecbid_hits(
    keyword: str,
    research_focus: str | None,
    *,
    timeout_seconds: int,
    limit: int,
) -> list[ResearchCrawlerHit]:
    html = _fetch_html(CECBID_HOME_URL, timeout_seconds=timeout_seconds)
    tokens = _build_match_tokens(keyword, research_focus)
    item_pattern = re.compile(
        r'<span class="badge[^"]*">\s*(推荐|招标|结果|专栏)\s*</span>\s*<a href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    info_pattern = re.compile(
        r'<a href="(https://www\.cecbid\.org\.cn/infos/details/[^"]+)"[^>]*title="([^"]+)"[^>]*>.*?</a>\s*<small[^>]*>(.*?)</small>',
        re.DOTALL,
    )
    hits: list[tuple[int, ResearchCrawlerHit]] = []
    seen_urls: set[str] = set()
    for badge, url, title in item_pattern.findall(html):
        if "/vips/details/" in url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        normalized_title = normalize_text(unescape(title))
        if not normalized_title:
            continue
        snippet = f"中国招标投标网 · {badge}"
        score = _score_candidate(
            title=normalized_title,
            snippet=snippet,
            section=badge,
            tokens=tokens,
            source_label="中国招标投标网",
        )
        hits.append(
            (
                score,
                ResearchCrawlerHit(
                    title=normalized_title,
                    url=url,
                    snippet=snippet,
                    search_query=f"中国招标投标网公开流: {keyword}",
                    source_hint="official_tender_feed",
                    source_label="中国招标投标网",
                ),
            )
        )
    for url, title, snippet_text in info_pattern.findall(html):
        if url in seen_urls:
            continue
        seen_urls.add(url)
        normalized_title = normalize_text(unescape(title))
        normalized_snippet = normalize_text(unescape(snippet_text))
        if not normalized_title:
            continue
        score = _score_candidate(
            title=normalized_title,
            snippet=normalized_snippet,
            section="资讯",
            tokens=tokens,
            source_label="中国招标投标网",
        )
        hits.append(
            (
                score,
                ResearchCrawlerHit(
                    title=normalized_title,
                    url=url,
                    snippet=f"中国招标投标网 · 资讯 · {_truncate(normalized_snippet or normalized_title, 108)}",
                    search_query=f"中国招标投标网资讯: {keyword}",
                    source_hint="official_tender_news",
                    source_label="中国招标投标网",
                ),
            )
        )
    hits.sort(key=lambda item: item[0], reverse=True)
    return [hit for score, hit in hits if score > 0][:limit]


def _extract_region_terms(keyword: str, research_focus: str | None) -> list[str]:
    scope_text = normalize_text(" ".join([keyword, research_focus or ""]))
    macro_regions = [
        label
        for label, aliases in REGION_SCOPE_ALIASES.items()
        if any(alias in scope_text for alias in aliases)
    ]
    region_patterns = (
        "北京", "上海", "天津", "重庆", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
        "广东", "广西", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "辽宁", "吉林", "黑龙江",
        "河北", "山西", "内蒙古", "宁夏", "新疆", "西藏", "成都", "杭州", "南京", "苏州", "深圳", "广州",
        "武汉", "西安", "长沙", "合肥", "青岛", "济南",
    )
    return [*macro_regions, *[item for item in region_patterns if item in scope_text]][:3]


def _crawl_ccgp_hits(
    keyword: str,
    research_focus: str | None,
    *,
    timeout_seconds: int,
    limit: int,
) -> list[ResearchCrawlerHit]:
    tokens = _build_match_tokens(keyword, research_focus)
    normalized_focus = normalize_text(research_focus or "")
    queries = [
        normalize_text(f"{keyword} {normalized_focus} 采购意向 中标 预算 采购人"),
        normalize_text(f"{keyword} {normalized_focus} 政府采购 项目 分期 预算"),
        normalize_text(f"{keyword} {normalized_focus} 公开采购 中标 集成商 厂商"),
    ]
    hits: list[ResearchCrawlerHit] = []
    seen_urls: set[str] = set()
    for query in queries:
        for hit in _search_domain_hits(
            query,
            timeout_seconds=timeout_seconds,
            limit=max(limit, 4),
            source_label="政府采购合规聚合",
            source_hint="compliant_procurement_aggregate",
            allowed_domains=PROCUREMENT_COMPLIANT_DOMAINS,
            tokens=tokens,
        ):
            if hit.url in seen_urls:
                continue
            seen_urls.add(hit.url)
            hits.append(hit)
            if len(hits) >= limit:
                return hits[:limit]
    return hits[:limit]


def _crawl_gov_policy_hits(
    keyword: str,
    research_focus: str | None,
    *,
    timeout_seconds: int,
    limit: int,
) -> list[ResearchCrawlerHit]:
    tokens = _build_match_tokens(keyword, research_focus)
    html = _fetch_html("https://www.gov.cn/zhengce/", timeout_seconds=timeout_seconds, allow_insecure=True)
    item_pattern = re.compile(
        r'<a href="(https://www\.gov\.cn[^"]+|\.\/[^"]+content_[^"]+\.htm)"[^>]*>\s*([^<]{8,120})\s*</a>'
        r'(?:.*?<p>\s*<a[^>]*>\s*([^<]{8,160})\s*</a>\s*</p>)?',
        re.DOTALL,
    )
    hits: list[tuple[int, ResearchCrawlerHit]] = []
    seen: set[str] = set()
    for href, title, desc in item_pattern.findall(html):
        url = parse.urljoin("https://www.gov.cn/zhengce/", href)
        if url in seen:
            continue
        seen.add(url)
        normalized_title = normalize_text(unescape(title))
        normalized_desc = normalize_text(unescape(desc))
        if not normalized_title:
            continue
        snippet = normalized_desc or "中国政府网政策/讲话"
        score = _score_candidate(
            title=normalized_title,
            snippet=snippet,
            section="政策",
            tokens=tokens,
            source_label="中国政府网政策/讲话",
        )
        if score <= 0:
            continue
        hits.append(
            (
                score,
                ResearchCrawlerHit(
                    title=normalized_title,
                    url=url,
                    snippet=f"中国政府网政策/讲话 · {_truncate(snippet, 108)}",
                    search_query=f"gov.cn/zhengce 直抓: {keyword}",
                    source_hint="official_policy_speech",
                    source_label="中国政府网政策/讲话",
                ),
            )
        )
    hits.sort(key=lambda item: item[0], reverse=True)
    direct_hits = [hit for score, hit in hits if score > 0][:limit]
    if direct_hits:
        return direct_hits
    queries = [
        normalize_text(f"site:gov.cn {keyword} {normalize_text(research_focus or '')} 领导 讲话 工作报告 战略 规划"),
        normalize_text(f"site:gov.cn {keyword} {normalize_text(research_focus or '')} 政策 文件 工作会议"),
    ]
    fallback_hits: list[ResearchCrawlerHit] = []
    fallback_seen: set[str] = set()
    for query in queries:
        for hit in _search_domain_hits(
            query,
            timeout_seconds=timeout_seconds,
            limit=limit,
            source_label="中国政府网政策/讲话",
            source_hint="official_policy_speech",
            allowed_domains=("gov.cn",),
            tokens=tokens,
        ):
            if hit.url in fallback_seen:
                continue
            fallback_seen.add(hit.url)
            fallback_hits.append(hit)
    return fallback_hits[:limit]


def _crawl_local_ggzy_hits(
    keyword: str,
    research_focus: str | None,
    *,
    timeout_seconds: int,
    limit: int,
) -> list[ResearchCrawlerHit]:
    tokens = _build_match_tokens(keyword, research_focus)
    regions = _extract_region_terms(keyword, research_focus)
    direct_hits: list[tuple[int, ResearchCrawlerHit]] = []
    if not regions or any(region in {"四川", "成都"} for region in regions):
        try:
            html = _fetch_html("https://ggzyjy.sc.gov.cn/", timeout_seconds=timeout_seconds, allow_insecure=True)
            item_pattern = re.compile(r'href="([^"]+)"[^>]*>\s*([^<]{8,120})\s*</a>')
            seen_direct: set[str] = set()
            for href, title in item_pattern.findall(html):
                url = parse.urljoin("https://ggzyjy.sc.gov.cn/", href)
                if url in seen_direct or "login" in url.lower():
                    continue
                seen_direct.add(url)
                normalized_title = normalize_text(unescape(title))
                if not normalized_title:
                    continue
                snippet = "四川省公共资源交易信息网 · 官方地方平台"
                score = _score_candidate(
                    title=normalized_title,
                    snippet=snippet,
                    section="地方平台",
                    tokens=tokens,
                    source_label="地方公共资源交易平台",
                )
                if score <= 0:
                    continue
                direct_hits.append(
                    (
                        score,
                        ResearchCrawlerHit(
                            title=normalized_title,
                            url=url,
                            snippet=f"地方公共资源交易平台 · 四川站 · {_truncate(normalized_title, 108)}",
                            search_query=f"四川省公共资源交易信息网直抓: {keyword}",
                            source_hint="regional_public_resource",
                            source_label="地方公共资源交易平台",
                        ),
                    )
                )
        except Exception:
            direct_hits = []
    if direct_hits:
        direct_hits.sort(key=lambda item: item[0], reverse=True)
        return [hit for score, hit in direct_hits if score > 0][:limit]
    queries = []
    if regions:
        for region in regions:
            queries.append(f"{region} 公共资源交易平台 {keyword} 招标 中标 项目")
            queries.append(f"{region} 政府采购网 {keyword} 预算 中标")
    else:
        queries.append(f"公共资源交易平台 {keyword} 招标 中标 项目")
    hits: list[ResearchCrawlerHit] = []
    seen: set[str] = set()
    for query in queries[:3]:
        for hit in _search_domain_hits(
            normalize_text(query),
            timeout_seconds=timeout_seconds,
            limit=limit,
            source_label="地方公共资源交易平台",
            source_hint="regional_public_resource",
            domain_keyword="ggzy",
            tokens=tokens,
        ):
            if hit.url in seen:
                continue
            seen.add(hit.url)
            hits.append(hit)
    return hits[:limit]


def collect_enabled_source_hits(
    keyword: str,
    research_focus: str | None,
    *,
    timeout_seconds: int,
    per_source_limit: int = 4,
    settings: ResearchSourceSettings | None = None,
) -> tuple[ResearchSourceSettings, list[ResearchCrawlerHit]]:
    resolved_settings = settings or read_research_source_settings()
    hits: list[ResearchCrawlerHit] = []

    if resolved_settings.enable_jianyu_tender_feed:
        try:
            hits.extend(
                _crawl_jianyu_hits(
                    keyword,
                    research_focus,
                    timeout_seconds=timeout_seconds,
                    limit=per_source_limit,
                )
            )
        except Exception:
            pass

    if resolved_settings.enable_yuntoutiao_feed:
        try:
            hits.extend(
                _crawl_yuntoutiao_hits(
                    keyword,
                    research_focus,
                    timeout_seconds=timeout_seconds,
                    limit=per_source_limit,
                )
            )
        except Exception:
            pass

    if resolved_settings.enable_ggzy_feed:
        try:
            hits.extend(
                _crawl_ggzy_hits(
                    keyword,
                    research_focus,
                    timeout_seconds=timeout_seconds,
                    limit=per_source_limit,
                )
            )
        except Exception:
            pass

    if resolved_settings.enable_cecbid_feed:
        try:
            hits.extend(
                _crawl_cecbid_hits(
                    keyword,
                    research_focus,
                    timeout_seconds=timeout_seconds,
                    limit=per_source_limit,
                )
            )
        except Exception:
            pass

    if resolved_settings.enable_ccgp_feed:
        try:
            hits.extend(
                _crawl_ccgp_hits(
                    keyword,
                    research_focus,
                    timeout_seconds=timeout_seconds,
                    limit=per_source_limit,
                )
            )
        except Exception:
            pass

    if resolved_settings.enable_gov_policy_feed:
        try:
            hits.extend(
                _crawl_gov_policy_hits(
                    keyword,
                    research_focus,
                    timeout_seconds=timeout_seconds,
                    limit=per_source_limit,
                )
            )
        except Exception:
            pass

    if resolved_settings.enable_local_ggzy_feed:
        try:
            hits.extend(
                _crawl_local_ggzy_hits(
                    keyword,
                    research_focus,
                    timeout_seconds=timeout_seconds,
                    limit=per_source_limit,
                )
            )
        except Exception:
            pass

    deduped: list[ResearchCrawlerHit] = []
    seen_urls: set[str] = set()
    for hit in hits:
        if hit.url in seen_urls:
            continue
        seen_urls.add(hit.url)
        deduped.append(hit)
    return resolved_settings, deduped
