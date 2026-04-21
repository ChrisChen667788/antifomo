function normalizeText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function buildTitleKeywords(title: string): string[] {
  const normalized = normalizeText(title);
  const parts = normalized
    .split(/[，,、：:；;（）()【】\[\]\s/]+/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 2 && part.length <= 18);
  if (normalized.length >= 6 && normalized.length <= 24) {
    parts.unshift(normalized);
  }
  return parts;
}

function buildSummaryKeywords(summary: string): string[] {
  return normalizeText(summary)
    .split(/[。！？!?；;\n]/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 4 && part.length <= 18)
    .slice(0, 2);
}

export function buildHighlightKeywords(input: {
  title: string;
  tags: string[];
  shortSummary: string;
}): string[] {
  const candidates = [
    ...input.tags,
    ...buildTitleKeywords(input.title),
    ...buildSummaryKeywords(input.shortSummary),
  ].map((value) => normalizeText(value));

  const unique: string[] = [];
  for (const candidate of candidates) {
    if (!candidate || candidate.length < 2 || candidate.length > 24) continue;
    if (unique.some((existing) => existing.includes(candidate) || candidate.includes(existing))) {
      continue;
    }
    unique.push(candidate);
    if (unique.length >= 6) break;
  }
  return unique;
}

function splitSentences(content: string): string[] {
  return content
    .replace(/\r/g, "")
    .replace(/([。！？!?])/g, "$1\n")
    .split(/\n+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function splitIntoParagraphs(content: string): string[] {
  const normalized = content.replace(/\r/g, "").trim();
  if (!normalized) return [];

  const directParagraphs = normalized
    .split(/\n{2,}/)
    .map((part) => normalizeText(part))
    .filter(Boolean);
  if (directParagraphs.length >= 2) {
    return directParagraphs.map((paragraph) => paragraph.slice(0, 280));
  }

  const sentences = splitSentences(normalized);
  const paragraphs: string[] = [];
  let buffer = "";
  for (const sentence of sentences) {
    const next = buffer ? `${buffer} ${sentence}` : sentence;
    if (next.length <= 120) {
      buffer = next;
      continue;
    }
    if (buffer) {
      paragraphs.push(buffer);
    }
    buffer = sentence;
  }
  if (buffer) {
    paragraphs.push(buffer);
  }

  return (paragraphs.length ? paragraphs : [normalized]).map((paragraph) => paragraph.slice(0, 280));
}

function scoreParagraph(paragraph: string, keywords: string[], index: number): number {
  const text = paragraph.toLowerCase();
  let score = Math.max(0, 18 - index * 2);
  for (const keyword of keywords) {
    const needle = keyword.toLowerCase();
    if (!needle) continue;
    if (text.startsWith(needle)) score += 24;
    else if (text.includes(needle)) score += 12;
  }
  score += Math.min(paragraph.length, 120) / 40;
  return score;
}

export function extractKeyParagraphs(content: string, keywords: string[], limit = 3): string[] {
  const paragraphs = splitIntoParagraphs(content);
  return paragraphs
    .map((paragraph, index) => ({
      paragraph,
      score: scoreParagraph(paragraph, keywords, index),
      index,
    }))
    .sort((a, b) => (b.score !== a.score ? b.score - a.score : a.index - b.index))
    .slice(0, limit)
    .sort((a, b) => a.index - b.index)
    .map((entry) => entry.paragraph);
}

export function highlightSegments(text: string, keywords: string[]): Array<{ text: string; hit: boolean }> {
  if (!text) return [];
  const needles = [...keywords]
    .map((value) => normalizeText(value))
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);

  if (!needles.length) {
    return [{ text, hit: false }];
  }

  const lowerText = text.toLowerCase();
  const segments: Array<{ text: string; hit: boolean }> = [];
  let cursor = 0;

  while (cursor < text.length) {
    let bestIndex = -1;
    let bestNeedle = "";
    for (const needle of needles) {
      const matchIndex = lowerText.indexOf(needle.toLowerCase(), cursor);
      if (matchIndex === -1) continue;
      if (bestIndex === -1 || matchIndex < bestIndex) {
        bestIndex = matchIndex;
        bestNeedle = needle;
      }
    }

    if (bestIndex === -1) {
      segments.push({ text: text.slice(cursor), hit: false });
      break;
    }

    if (bestIndex > cursor) {
      segments.push({ text: text.slice(cursor, bestIndex), hit: false });
    }

    segments.push({
      text: text.slice(bestIndex, bestIndex + bestNeedle.length),
      hit: true,
    });
    cursor = bestIndex + bestNeedle.length;
  }

  return segments.filter((segment) => segment.text);
}
