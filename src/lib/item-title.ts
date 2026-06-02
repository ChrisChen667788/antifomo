import type { ApiItem } from "@/lib/api/types";

const WECHAT_HOME_HEADER_TITLE_RE =
  /^[\u4e00-\u9fffA-Za-z0-9·_-]{2,20}\s+[\u4e00-\u9fffA-Za-z0-9·_-]{2,30}\s+20[2-3]\d年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2})?$/;
const WECHAT_HOME_HEADER_RE =
  /^[\u4e00-\u9fffA-Za-z0-9·_-]{2,20}\s+[\u4e00-\u9fffA-Za-z0-9·_-]{2,30}\s+20[2-3]\d年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2})?\s*/;
const WECHAT_FOLLOW_PROMPT_RE =
  /(?:[\u4e00-\u9fff]{0,8}\d+\s*人\s*)?点击蓝字\s*可以关注我们[喔哦]?[!！]?/g;
const BROWSER_NAV_NOISE_TOKENS = [
  "个人收藏",
  "京东",
  "天猫",
  "淘宝",
  "苏宁易购",
  "维基百科",
  "iCloud",
  "百度",
  "新浪微博",
];

function cleanCandidate(text: string | null | undefined): string {
  return (text || "")
    .replace(/\s+/g, " ")
    .replace(/^标题[:：]\s*/i, "")
    .replace(/^关键词[:：].*$/i, "")
    .replace(/^作者[:：].*$/i, "")
    .trim();
}

function isWechatSource(
  item: Pick<ApiItem, "source_domain" | "source_url">,
): boolean {
  const source = `${item.source_domain || ""} ${item.source_url || ""}`.toLowerCase();
  return source.includes("wechat.local") || source.includes("mp.weixin.qq.com");
}

function cleanWechatSummaryText(text: string): string {
  let cleaned = text;
  if (looksLikeBrowserNavNoise(cleaned)) {
    const marker = cleaned.search(/本地服务|第一次跑|已积累|source_url:|正文[:：]/);
    if (marker >= 0) {
      cleaned = cleaned.slice(marker);
    }
  }
  return cleaned
    .replace(WECHAT_HOME_HEADER_RE, "")
    .replace(WECHAT_FOLLOW_PROMPT_RE, "")
    .replace(/\s+/g, " ")
    .trim();
}

function looksLikeBrowserNavNoise(text: string): boolean {
  const normalized = cleanCandidate(text);
  if (!normalized.startsWith("个人收藏")) return false;
  return BROWSER_NAV_NOISE_TOKENS.filter((token) => normalized.includes(token)).length >= 4;
}

export function resolveItemTitle(
  item: Pick<ApiItem, "title" | "short_summary" | "long_summary" | "source_domain" | "source_url">,
  fallback: string,
): string {
  const wechatSource = isWechatSource(item);
  const rawTitle = cleanCandidate(item.title);
  const isPlaceholder =
    !rawTitle ||
    /^wechat\s+(auto|ocr)/i.test(rawTitle) ||
    /^untitled/i.test(rawTitle) ||
    /^未命名/.test(rawTitle) ||
    (wechatSource && WECHAT_HOME_HEADER_TITLE_RE.test(rawTitle)) ||
    (wechatSource && looksLikeBrowserNavNoise(rawTitle));

  if (!isPlaceholder) {
    return rawTitle;
  }

  const seeds = [item.short_summary, item.long_summary];
  for (const seed of seeds) {
    const text = (wechatSource ? cleanWechatSummaryText(cleanCandidate(seed)) : cleanCandidate(seed))
      .replace(/^短摘要[:：]\s*/i, "")
      .replace(/^长摘要[:：]\s*/i, "");
    if (!text) continue;
    if (wechatSource && (/pixcull_demo/i.test(text) || (text.includes("模型加载") && text.includes("本地缓存")))) {
      return "本地照片分拣工具运行状态";
    }

    const candidates = text
      .split(/[。！？!?；;\n]/)
      .map((part) =>
        part
          .replace(/^(这篇文章|本文|文章|这条内容|内容主要|文章主要|本文主要|文中主要|核心信息是|核心观点是|主要讲的是)/, "")
          .replace(/\s+/g, " ")
          .trim(),
      )
      .filter(Boolean);

    for (const candidate of candidates) {
      if (candidate.length < 8) continue;
      return candidate.slice(0, 30).replace(/[，,、:：-]+$/, "");
    }
  }

  return rawTitle || fallback;
}
