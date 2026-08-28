from __future__ import annotations

from functools import lru_cache
from dataclasses import dataclass
import re

from app.schemas.research import ResearchSourceOut
from app.services.content_extractor import normalize_text


@dataclass(slots=True)
class SourceDocument:
    title: str
    url: str
    domain: str | None
    snippet: str
    search_query: str
    source_type: str
    content_status: str
    excerpt: str
    source_label: str | None = None
    source_tier: str = "media"
    source_origin: str = "search"


SOURCE_ARTIFACT_TOKENS = (
    "错误页面",
    "页面错误",
    "error page",
    "header_",
    "deal/deallist.html",
    "交易公开-全国公共资源交易平台",
    "全国公共资源交易平台 ·",
    "[政府采购](",
    "* [政府采购](",
    "返回顶部",
    "跳转到主要内容区域",
    "首页 关于我们 价值定位 组织架构",
    "报告共计：",
    "报告共计:",
    "发布于：",
    "发布于:",
    "文章标签：",
    "文章标签:",
    "csdn博客",
    "互联网公开网页",
    "公开线索 1 条，代表样本",
    "中国政府网政策/讲话",
    "豆瓣 ",
    "关注民生周刊",
    "微信 微博",
    "民生网首页",
    "首页 云头条",
    "ai头条 联系我们",
    "微信公众号 扫码",
    "中国招标投标网 主站",
    "欢迎您来到中国招标投标网",
    "客服中心 隐私声明 登录 注册",
    "公司简介 愿景及使命 发展历程 业务架构",
    "工作环境 员工活动 esg 环境 社会",
    "省级层面 ",
    "yahoo search",
    "bing search",
    "360 搜索",
)

SOURCE_AWARD_NOISE_TOKENS = (
    "奖项",
    "获奖",
    "颁奖",
    "热力榜",
    "作品奖",
    "企业奖",
    "创新奖",
    "荣誉奖",
    "入围名单",
    "获奖名单",
    "评选结果",
)

SOURCE_FORUM_NOISE_TOKENS = (
    "论坛",
    "峰会",
    "大会",
    "年会",
    "沙龙",
    "闭门会",
    "圆桌",
)

SOURCE_FORUM_SPEECH_TOKENS = (
    "发言",
    "致辞",
    "演讲",
    "分享",
    "主持",
    "对话",
    "观点",
)

SOURCE_MARKDOWN_DUMP_TOKENS = (
    "markdown content",
    "source dump",
    "图片来源",
    "图源",
    "原图",
    "封面图",
    "点击查看原图",
    "查看原图",
    "source:",
    "sources:",
    "source url:",
    "source link:",
)

MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]*\)")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!\!)\[([^\]]+)\]\(([^)]+)\)")
RAW_MEDIA_URL_PATTERN = re.compile(r"https?://\S+\.(?:png|jpg|jpeg|gif|webp|svg|bmp)(?:\?\S*)?", re.IGNORECASE)
TRAILING_ENGLISH_DATE_PATTERN = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+20\d{2}$",
    re.IGNORECASE,
)
SOURCE_LABEL_FRAGMENT_PATTERN = re.compile(
    r"^(?:中国政府采购网|全国公共资源交易平台|政府采购网|公共资源交易平台)\s+(?:其|该|主办单位|网站)",
    re.IGNORECASE,
)
SOURCE_TEXT_SPLIT_PATTERN = re.compile(r"[。！？!?；;\n]+|\s+[|｜]\s+|\s+-\s+|(?<=\S)\s+·\s+(?=\S)")
SOURCE_DUMP_PREFIX_PATTERN = re.compile(
    r"^(?:source|sources|source url|source link|来源|圖片來源|图片来源|图源|原图|封面图|image source)[:：-]",
    re.IGNORECASE,
)


@lru_cache(maxsize=8192)
def looks_like_source_artifact_text(value: str) -> bool:
    normalized = normalize_text(value)
    lowered = normalized.lower()
    if not normalized:
        return False
    if any(token in lowered for token in SOURCE_ARTIFACT_TOKENS):
        return True
    if normalized.startswith((".", "…")) or "**" in normalized:
        return True
    if normalized.count("_") >= 2:
        return True
    if TRAILING_ENGLISH_DATE_PATTERN.search(normalized):
        return True
    if SOURCE_LABEL_FRAGMENT_PATTERN.search(normalized):
        return True
    if "http://" in lowered or "https://" in lowered:
        if any(token in lowered for token in ("[", "](", "javascript:", "deal/deallist", "ggzy.gov.cn/deal")):
            return True
    if normalized.count("全国公共资源交易平台") >= 2:
        return True
    if normalized.count("·") >= 2 and any(token in normalized for token in ("公示", "公告", "交易公开")):
        return True
    if normalized.count("：") >= 2 and any(
        token in normalized for token in ("报告共计", "发布于", "文章标签", "CSDN博客", "腾讯新闻")
    ):
        return True
    return False


def looks_like_source_noise_segment(value: str, *, raw_value: str | None = None) -> bool:
    normalized = normalize_text(value)
    lowered = normalized.lower()
    raw_lower = str(raw_value or value).lower()
    if not normalized:
        return False
    if looks_like_source_artifact_text(normalized):
        return True
    if SOURCE_DUMP_PREFIX_PATTERN.match(normalized):
        return True
    if any(token in normalized for token in SOURCE_AWARD_NOISE_TOKENS):
        return True
    if any(token in normalized for token in SOURCE_FORUM_NOISE_TOKENS) and any(
        token in normalized for token in SOURCE_FORUM_SPEECH_TOKENS
    ):
        return True
    if any(token in lowered for token in SOURCE_MARKDOWN_DUMP_TOKENS):
        return True
    if any(token in raw_lower for token in ("![", "](http", "](https")):
        return True
    if raw_lower.count("](") >= 2:
        return True
    if RAW_MEDIA_URL_PATTERN.search(raw_lower):
        return True
    return False


def clean_source_text_for_analysis(value: str) -> str:
    return clean_source_text_for_analysis_cached(str(value or ""))


@lru_cache(maxsize=8192)
def clean_source_text_for_analysis_cached(raw: str) -> str:
    normalized_raw = normalize_text(raw)
    if not normalized_raw:
        return ""
    without_images = MARKDOWN_IMAGE_PATTERN.sub(" ", raw)
    without_links = MARKDOWN_LINK_PATTERN.sub(lambda match: match.group(1), without_images)
    without_media_urls = RAW_MEDIA_URL_PATTERN.sub(" ", without_links)
    cleaned_segments: list[str] = []
    for raw_segment in SOURCE_TEXT_SPLIT_PATTERN.split(without_media_urls):
        normalized = normalize_text(raw_segment)
        if not normalized or looks_like_source_noise_segment(normalized, raw_value=raw_segment):
            continue
        cleaned_segments.append(normalized)
    if cleaned_segments:
        return normalize_text("。".join(cleaned_segments))
    normalized = normalize_text(without_media_urls)
    if looks_like_source_noise_segment(normalized, raw_value=without_media_urls):
        return ""
    return normalized


def source_document_text(source: SourceDocument) -> str:
    return source_document_text_cached(source.title, source.snippet, source.excerpt)


@lru_cache(maxsize=4096)
def source_document_text_cached(title: str, snippet: str, excerpt: str) -> str:
    parts: list[str] = []
    for value in (title, snippet, excerpt):
        cleaned = clean_source_text_for_analysis(value)
        if cleaned and cleaned not in parts:
            parts.append(cleaned)
    return normalize_text("。".join(parts))


def _research_source_output_snippet(source: SourceDocument) -> str:
    snippet = clean_source_text_for_analysis(source.snippet)
    excerpt = clean_source_text_for_analysis(source.excerpt)
    if excerpt and (len(snippet) < 80 or len(excerpt) > len(snippet) + 40):
        value = excerpt
    else:
        value = snippet or excerpt
    return normalize_text(value)[:1600].rstrip()


def source_documents_to_research_source_outputs(sources: list[SourceDocument]) -> list[ResearchSourceOut]:
    return [
        ResearchSourceOut(
            title=source.title,
            url=source.url,
            domain=source.domain,
            snippet=_research_source_output_snippet(source),
            search_query=source.search_query,
            source_type=source.source_type,
            content_status=source.content_status,
            source_label=source.source_label,
            source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
            source_origin=(
                source.source_origin
                if source.source_origin in {"search", "adapter", "snapshot_cache", "user_supplied"}
                else "search"
            ),
        )
        for source in sources
    ]
