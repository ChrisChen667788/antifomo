function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function buildTitleKeywords(title) {
  const normalized = normalizeText(title);
  const parts = normalized
    .split(/[，,、：:；;（）()【】[\]\s/]+/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 2 && part.length <= 18);
  if (normalized.length >= 6 && normalized.length <= 24) {
    parts.unshift(normalized);
  }
  return parts;
}

function buildSummaryKeywords(summary) {
  return normalizeText(summary)
    .split(/[。！？!?；;\n]/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 4 && part.length <= 18)
    .slice(0, 2);
}

function buildHighlightKeywords({ title, tags, shortSummary }) {
  const candidates = []
    .concat(tags || [])
    .concat(buildTitleKeywords(title))
    .concat(buildSummaryKeywords(shortSummary))
    .map((value) => normalizeText(value));

  const unique = [];
  candidates.forEach((candidate) => {
    if (!candidate || candidate.length < 2 || candidate.length > 24) return;
    if (unique.some((existing) => existing.indexOf(candidate) >= 0 || candidate.indexOf(existing) >= 0)) {
      return;
    }
    unique.push(candidate);
  });
  return unique.slice(0, 6);
}

function splitIntoParagraphs(content) {
  const normalized = String(content || "").replace(/\r/g, "").trim();
  if (!normalized) return [];

  const directParagraphs = normalized
    .split(/\n{2,}/)
    .map((part) => normalizeText(part))
    .filter(Boolean);
  if (directParagraphs.length >= 2) {
    return directParagraphs.map((paragraph) => paragraph.slice(0, 280));
  }

  const sentences = normalized
    .replace(/([。！？!?])/g, "$1\n")
    .split(/\n+/)
    .map((part) => part.trim())
    .filter(Boolean);

  const paragraphs = [];
  let buffer = "";
  sentences.forEach((sentence) => {
    const next = buffer ? `${buffer} ${sentence}` : sentence;
    if (next.length <= 120) {
      buffer = next;
      return;
    }
    if (buffer) paragraphs.push(buffer);
    buffer = sentence;
  });
  if (buffer) {
    paragraphs.push(buffer);
  }

  return (paragraphs.length ? paragraphs : [normalized]).map((paragraph) => paragraph.slice(0, 280));
}

function scoreParagraph(paragraph, keywords, index) {
  const lower = paragraph.toLowerCase();
  let score = Math.max(0, 18 - index * 2);
  keywords.forEach((keyword) => {
    const needle = String(keyword || "").toLowerCase();
    if (!needle) return;
    if (lower.indexOf(needle) === 0) score += 24;
    else if (lower.indexOf(needle) >= 0) score += 12;
  });
  score += Math.min(paragraph.length, 120) / 40;
  return score;
}

function extractKeyParagraphs(content, keywords, limit = 3) {
  return splitIntoParagraphs(content)
    .map((paragraph, index) => ({
      paragraph,
      index,
      score: scoreParagraph(paragraph, keywords, index)
    }))
    .sort((a, b) => (b.score !== a.score ? b.score - a.score : a.index - b.index))
    .slice(0, limit)
    .sort((a, b) => a.index - b.index)
    .map((entry) => entry.paragraph);
}

function highlightSegments(text, keywords) {
  const value = String(text || "");
  const needles = (keywords || [])
    .map((keyword) => normalizeText(keyword))
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);

  if (!needles.length) {
    return [{ text: value, hit: false }];
  }

  const lower = value.toLowerCase();
  const segments = [];
  let cursor = 0;

  while (cursor < value.length) {
    let bestIndex = -1;
    let bestNeedle = "";
    needles.forEach((needle) => {
      const index = lower.indexOf(needle.toLowerCase(), cursor);
      if (index === -1) return;
      if (bestIndex === -1 || index < bestIndex) {
        bestIndex = index;
        bestNeedle = needle;
      }
    });

    if (bestIndex === -1) {
      segments.push({ text: value.slice(cursor), hit: false });
      break;
    }

    if (bestIndex > cursor) {
      segments.push({ text: value.slice(cursor, bestIndex), hit: false });
    }

    segments.push({
      text: value.slice(bestIndex, bestIndex + bestNeedle.length),
      hit: true
    });
    cursor = bestIndex + bestNeedle.length;
  }

  return segments.filter((segment) => segment.text);
}

function buildOriginalViewModel({ title, tags, shortSummary, content }) {
  const keywords = buildHighlightKeywords({ title, tags, shortSummary });
  const paragraphs = splitIntoParagraphs(content);
  const keyParagraphs = extractKeyParagraphs(content, keywords, 3).map((paragraph) => ({
    raw: paragraph,
    segments: highlightSegments(paragraph, keywords)
  }));
  return {
    keywords,
    paragraphs,
    keyParagraphs
  };
}

module.exports = {
  buildOriginalViewModel
};
