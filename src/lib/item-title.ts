import type { ApiItem } from "@/lib/api";

function cleanCandidate(text: string | null | undefined): string {
  return (text || "")
    .replace(/\s+/g, " ")
    .replace(/^标题[:：]\s*/i, "")
    .replace(/^关键词[:：].*$/i, "")
    .replace(/^作者[:：].*$/i, "")
    .trim();
}

export function resolveItemTitle(
  item: Pick<ApiItem, "title" | "short_summary" | "long_summary">,
  fallback: string,
): string {
  const rawTitle = cleanCandidate(item.title);
  const isPlaceholder =
    !rawTitle ||
    /^wechat\s+(auto|ocr)/i.test(rawTitle) ||
    /^untitled/i.test(rawTitle) ||
    /^未命名/.test(rawTitle);

  if (!isPlaceholder) {
    return rawTitle;
  }

  const seeds = [item.short_summary, item.long_summary];
  for (const seed of seeds) {
    const text = cleanCandidate(seed)
      .replace(/^短摘要[:：]\s*/i, "")
      .replace(/^长摘要[:：]\s*/i, "");
    if (!text) continue;

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
