import type { ApiKnowledgeEntry } from "@/lib/api";
import { getResearchFacets } from "@/lib/research-facets";

export type ResearchCompareRole = "甲方" | "中标方" | "竞品" | "伙伴";

export interface ResearchCompareRow {
  id: string;
  role: ResearchCompareRole;
  name: string;
  clue: string;
  region: string;
  industry: string;
  keyword: string;
  budgetSignal: string;
  projectSignal: string;
  strategySignal: string;
  competitionSignal: string;
  budgetRange: string;
  targetDepartments: string[];
  publicContacts: string[];
  candidateProfileCompanies: string[];
  candidateProfileHitCount: number;
  candidateProfileOfficialHitCount: number;
  candidateProfileSourceLabels: string[];
  partnerHighlights: string[];
  competitorHighlights: string[];
  benchmarkCases: string[];
  evidenceLinks: Array<{ title: string; url: string; sourceTier: "official" | "media" | "aggregate"; sourceLabel: string }>;
  sourceCount: number;
  sourceEntryId: string;
  sourceEntryTitle: string;
  updatedAt: string;
}

type ReportPayload = {
  keyword?: string;
  source_count?: number;
  source_diagnostics?: {
    candidate_profile_companies?: string[];
    candidate_profile_hit_count?: number;
    candidate_profile_official_hit_count?: number;
    candidate_profile_source_labels?: string[];
  };
  target_accounts?: string[];
  top_target_accounts?: Array<{ name?: string; reasoning?: string }>;
  target_departments?: string[];
  public_contact_channels?: string[];
  budget_signals?: string[];
  project_distribution?: string[];
  strategic_directions?: string[];
  tender_timeline?: string[];
  leadership_focus?: string[];
  ecosystem_partners?: string[];
  top_ecosystem_partners?: Array<{ name?: string; reasoning?: string }>;
  competitor_profiles?: string[];
  top_competitors?: Array<{ name?: string; reasoning?: string }>;
  benchmark_cases?: string[];
  client_peer_moves?: string[];
  winner_peer_moves?: string[];
  competition_analysis?: string[];
  sources?: Array<{ title?: string; url?: string; source_tier?: string; source_label?: string; source_type?: string; domain?: string }>;
};

const ORG_PATTERN =
  /([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,40}(?:集团|公司|有限公司|股份有限公司|研究院|研究所|大学|医院|银行|政府|厅|局|委|办|中心|学院|学校|科技|智能|信息|控股|实验室))/;

function normalizeText(value: unknown): string {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function extractReport(entry: ApiKnowledgeEntry): ReportPayload | null {
  const payload = (entry.metadata_payload || {}) as { report?: ReportPayload };
  return payload.report || null;
}

function extractEntityName(raw: string): string {
  const text = normalizeText(raw);
  if (!text) {
    return "";
  }
  const orgMatch = text.match(ORG_PATTERN);
  if (orgMatch?.[1]) {
    return orgMatch[1];
  }
  const firstSegment = text.split(/[：:，,；;。]/)[0] || text;
  return firstSegment.slice(0, 28).trim();
}

function uniqueTake(values: string[], limit = 3): string[] {
  const seen = new Set<string>();
  const next: string[] = [];
  values.forEach((value) => {
    const normalized = normalizeText(value);
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    next.push(normalized);
  });
  return next.slice(0, limit);
}

function mergeUnique(values: string[], additions: string[], limit = 4): string[] {
  return uniqueTake([...(values || []), ...(additions || [])], limit);
}

function classifySourceTier(source: NonNullable<ReportPayload["sources"]>[number]): "official" | "media" | "aggregate" {
  const domain = normalizeText(source.domain || "").toLowerCase();
  const sourceType = normalizeText(source.source_type || "").toLowerCase();
  const sourceTier = normalizeText(source.source_tier || "").toLowerCase();
  if (sourceTier === "official" || sourceType === "policy" || sourceType === "procurement" || sourceType === "filing" || domain.includes("gov.cn") || domain.includes("ggzy.gov.cn") || domain.includes("sec.gov") || domain.includes("hkexnews.hk") || domain.includes("cninfo.com.cn")) {
    return "official";
  }
  if (sourceTier === "aggregate" || sourceType === "tender_feed" || sourceType === "compliant_procurement_aggregate" || domain.includes("jianyu") || domain.includes("cecbid") || domain.includes("cebpubservice") || domain.includes("china-cpp") || domain.includes("chinabidding")) {
    return "aggregate";
  }
  return "media";
}

function parseBudgetRange(values: string[]): string {
  const matches = values
    .flatMap((value) => {
      const text = normalizeText(value);
      const found = [...text.matchAll(/(\d+(?:\.\d+)?)(亿|万|千)?元/g)];
      return found.map((match) => {
        const amount = Number(match[1] || 0);
        const unit = match[2] || "";
        const multiplier = unit === "亿" ? 100000000 : unit === "万" ? 10000 : unit === "千" ? 1000 : 1;
        return {
          raw: match[0],
          value: amount * multiplier,
        };
      });
    })
    .filter((item) => item.value > 0);
  if (!matches.length) {
    return "未明确";
  }
  const sorted = matches.sort((left, right) => left.value - right.value);
  if (sorted.length === 1) {
    return sorted[0].raw;
  }
  return `${sorted[0].raw} - ${sorted[sorted.length - 1].raw}`;
}

function buildRoleRows(
  entry: ApiKnowledgeEntry,
  role: ResearchCompareRole,
  values: string[],
  report: ReportPayload,
): ResearchCompareRow[] {
  const facets = getResearchFacets(entry);
  const budgetSignal = uniqueTake(report.budget_signals || [], 1)[0] || "—";
  const projectSignal = uniqueTake(
    [...(report.project_distribution || []), ...(report.tender_timeline || [])],
    1,
  )[0] || "—";
  const strategySignal = uniqueTake(
    [...(report.strategic_directions || []), ...(report.leadership_focus || [])],
    1,
  )[0] || "—";
  const competitionSignal = uniqueTake(report.competition_analysis || [], 1)[0] || "—";
  const benchmarkCases = uniqueTake(report.benchmark_cases || [], 3);
  const evidenceLinks = (report.sources || [])
    .map((source) => ({
      title: normalizeText(source.title || "") || "参考来源",
      url: normalizeText(source.url || ""),
      sourceTier: classifySourceTier(source),
      sourceLabel: normalizeText(source.source_label || source.domain || ""),
    }))
    .filter((source) => source.url)
    .slice(0, 4);

  return uniqueTake(values, 6).map((value, index) => ({
    id: `${entry.id}-${role}-${index}`,
    role,
    name: extractEntityName(value) || `未识别${role}`,
    clue: value,
    region: facets.region,
    industry: facets.industry,
    keyword: normalizeText(report.keyword || ""),
    budgetSignal,
    projectSignal,
    strategySignal,
    competitionSignal,
    budgetRange: parseBudgetRange(report.budget_signals || []),
    targetDepartments: uniqueTake(report.target_departments || [], 4),
    publicContacts: uniqueTake(report.public_contact_channels || [], 4),
    candidateProfileCompanies: uniqueTake((report.source_diagnostics?.candidate_profile_companies as string[] | undefined) || [], 4),
    candidateProfileHitCount: Number(report.source_diagnostics?.candidate_profile_hit_count || 0),
    candidateProfileOfficialHitCount: Number(report.source_diagnostics?.candidate_profile_official_hit_count || 0),
    candidateProfileSourceLabels: uniqueTake((report.source_diagnostics?.candidate_profile_source_labels as string[] | undefined) || [], 4),
    partnerHighlights: uniqueTake(report.ecosystem_partners || [], 4),
    competitorHighlights: uniqueTake(report.competitor_profiles || [], 4),
    benchmarkCases,
    evidenceLinks,
    sourceCount: Number(report.source_count || 0),
    sourceEntryId: entry.id,
    sourceEntryTitle: entry.title,
    updatedAt: entry.updated_at || entry.created_at,
  }));
}

export function buildResearchCompareRows(entries: ApiKnowledgeEntry[]): ResearchCompareRow[] {
  const rows = entries.flatMap((entry) => {
    if (entry.source_domain !== "research.report") {
      return [];
    }
    const report = extractReport(entry);
    if (!report) {
      return [];
    }
    const rankedTargets = uniqueTake((report.top_target_accounts || []).map((item) => item?.name || "").filter(Boolean), 6);
    const rankedCompetitors = uniqueTake((report.top_competitors || []).map((item) => item?.name || "").filter(Boolean), 6);
    const rankedPartners = uniqueTake((report.top_ecosystem_partners || []).map((item) => item?.name || "").filter(Boolean), 6);
    return [
      ...buildRoleRows(entry, "甲方", rankedTargets.length ? rankedTargets : report.target_accounts || [], report),
      ...buildRoleRows(entry, "中标方", report.winner_peer_moves || [], report),
      ...buildRoleRows(entry, "竞品", rankedCompetitors.length ? rankedCompetitors : report.competitor_profiles || [], report),
      ...buildRoleRows(entry, "伙伴", rankedPartners.length ? rankedPartners : report.ecosystem_partners || [], report),
    ];
  });

  const merged = new Map<string, ResearchCompareRow>();
  rows.forEach((row) => {
    const key = `${row.role}::${row.name}`;
    const existing = merged.get(key);
    if (!existing) {
      merged.set(key, row);
      return;
    }
    const existingTime = new Date(existing.updatedAt).getTime();
    const nextTime = new Date(row.updatedAt).getTime();
    if (nextTime > existingTime) {
      merged.set(key, {
        ...row,
        sourceCount: Math.max(existing.sourceCount, row.sourceCount),
        targetDepartments: mergeUnique(row.targetDepartments, existing.targetDepartments),
        publicContacts: mergeUnique(row.publicContacts, existing.publicContacts),
        candidateProfileCompanies: mergeUnique(row.candidateProfileCompanies, existing.candidateProfileCompanies),
        candidateProfileHitCount: Math.max(existing.candidateProfileHitCount, row.candidateProfileHitCount),
        candidateProfileOfficialHitCount: Math.max(existing.candidateProfileOfficialHitCount, row.candidateProfileOfficialHitCount),
        candidateProfileSourceLabels: mergeUnique(row.candidateProfileSourceLabels, existing.candidateProfileSourceLabels),
        partnerHighlights: mergeUnique(row.partnerHighlights, existing.partnerHighlights),
        competitorHighlights: mergeUnique(row.competitorHighlights, existing.competitorHighlights),
        benchmarkCases: mergeUnique(row.benchmarkCases, existing.benchmarkCases),
        evidenceLinks: [...row.evidenceLinks, ...existing.evidenceLinks]
          .filter((item, index, list) => item.url && list.findIndex((candidate) => candidate.url === item.url) === index)
          .slice(0, 4),
      });
    } else {
      merged.set(key, {
        ...existing,
        sourceCount: Math.max(existing.sourceCount, row.sourceCount),
        targetDepartments: mergeUnique(existing.targetDepartments, row.targetDepartments),
        publicContacts: mergeUnique(existing.publicContacts, row.publicContacts),
        candidateProfileCompanies: mergeUnique(existing.candidateProfileCompanies, row.candidateProfileCompanies),
        candidateProfileHitCount: Math.max(existing.candidateProfileHitCount, row.candidateProfileHitCount),
        candidateProfileOfficialHitCount: Math.max(existing.candidateProfileOfficialHitCount, row.candidateProfileOfficialHitCount),
        candidateProfileSourceLabels: mergeUnique(existing.candidateProfileSourceLabels, row.candidateProfileSourceLabels),
        partnerHighlights: mergeUnique(existing.partnerHighlights, row.partnerHighlights),
        competitorHighlights: mergeUnique(existing.competitorHighlights, row.competitorHighlights),
        benchmarkCases: mergeUnique(existing.benchmarkCases, row.benchmarkCases),
        evidenceLinks: [...existing.evidenceLinks, ...row.evidenceLinks]
          .filter((item, index, list) => item.url && list.findIndex((candidate) => candidate.url === item.url) === index)
          .slice(0, 4),
      });
    }
  });
  return [...merged.values()].sort(
    (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
  );
}
