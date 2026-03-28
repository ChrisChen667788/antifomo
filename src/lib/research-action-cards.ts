import type { ApiResearchActionCard } from "@/lib/api";

export type ResearchActionPhase = {
  label: string;
  horizon: string;
  content: string;
};

export type ResearchActionEvidenceCard = {
  label: string;
  url: string;
};

export type UiResearchActionCard = ApiResearchActionCard & {
  priorityLabel: string;
  phases: ResearchActionPhase[];
  evidenceCards: ResearchActionEvidenceCard[];
};

export function normalizeActionText(value: string) {
  return String(value || "")
    .replace(/\[Image\s*\d+\]/gi, " ")
    .replace(/!\[[^\]]*\]\((https?:\/\/[^)\s]+)\)/gi, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

export function parseActionPhases(steps: string[]): ResearchActionPhase[] {
  return (Array.isArray(steps) ? steps : [])
    .map((step) => normalizeActionText(step))
    .filter(Boolean)
    .map((step) => {
      const match = step.match(
        /^(短期|中期|长期|Short term|Mid term|Long term)(?:（([^）]+)）|\(([^)]+)\))?[:：]\s*(.+)$/i,
      );
      if (!match) {
        return {
          label: "短期",
          horizon: "",
          content: step,
        };
      }
      return {
        label: match[1],
        horizon: match[2] || match[3] || "",
        content: match[4],
      };
    })
    .slice(0, 3);
}

export function normalizeActionEvidence(evidence: string[]): ResearchActionEvidenceCard[] {
  const urlPattern = /https?:\/\/[^\s)]+/g;
  const items: ResearchActionEvidenceCard[] = [];
  for (const raw of Array.isArray(evidence) ? evidence : []) {
    const text = normalizeActionText(raw);
    if (!text) continue;
    const urls = text.match(urlPattern) || [];
    const label = text.replace(urlPattern, "").replace(/[()]/g, " ").replace(/\s+/g, " ").trim();
    if (urls.length) {
      items.push({
        label: label || "打开公开来源",
        url: urls[0] || "",
      });
      continue;
    }
    items.push({
      label: text,
      url: "",
    });
  }
  return items.slice(0, 3);
}

export function priorityLabel(priority: string, t: (key: string, fallback?: string) => string) {
  const normalized = String(priority || "").toLowerCase();
  if (normalized === "high") return t("summary.score.high", "高价值");
  if (normalized === "low") return t("summary.score.low", "低价值");
  return t("summary.score.medium", "普通价值");
}

export function normalizeResearchActionCards(
  cards: ApiResearchActionCard[],
  t: (key: string, fallback?: string) => string,
): UiResearchActionCard[] {
  return (Array.isArray(cards) ? cards : []).map((card) => ({
    ...card,
    summary: normalizeActionText(card.summary),
    recommended_steps: (Array.isArray(card.recommended_steps) ? card.recommended_steps : [])
      .map((step) => normalizeActionText(step))
      .filter(Boolean),
    evidence: (Array.isArray(card.evidence) ? card.evidence : [])
      .map((row) => normalizeActionText(row))
      .filter(Boolean),
    priorityLabel: priorityLabel(card.priority, t),
    phases: parseActionPhases(card.recommended_steps || []),
    evidenceCards: normalizeActionEvidence(card.evidence || []),
  }));
}
