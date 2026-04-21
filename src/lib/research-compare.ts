import type { ApiKnowledgeEntry, ApiResearchCompareSnapshotLinkedVersionDiff } from "@/lib/api";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";
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
  weakSections: ResearchCompareWeakSection[];
}

export interface ResearchCompareMarkdownOptions {
  query?: string;
  region?: string;
  industry?: string;
  role?: ResearchCompareRole | "all";
  generatedAt?: Date;
  snapshotName?: string;
  linkedVersionTitle?: string;
  linkedVersionRefreshedAt?: string | null;
  linkedDiff?: ApiResearchCompareSnapshotLinkedVersionDiff | null;
}

export interface ResearchCompareEvidenceSummary {
  sourceEntryCount: number;
  directEvidenceCount: number;
  officialEvidenceCount: number;
  mediaEvidenceCount: number;
  aggregateEvidenceCount: number;
  uncoveredEntities: string[];
  officialCoverageLeaders: string[];
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
  sections?: Array<{
    title?: string;
    status?: string;
    insufficiency_summary?: string;
    insufficiency_reasons?: string[];
    next_verification_steps?: string[];
  }>;
  sources?: Array<{ title?: string; url?: string; source_tier?: string; source_label?: string; source_type?: string; domain?: string }>;
};

type ResearchCompareWeakSection = {
  title: string;
  status: string;
  insufficiencySummary: string;
  insufficiencyReasons: string[];
  nextVerificationSteps: string[];
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

function sanitizeFilenamePart(value: string): string {
  return normalizeText(value)
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 32);
}

function formatDateStamp(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateTimeStamp(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hours = String(value.getHours()).padStart(2, "0");
  const minutes = String(value.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) {
    return "—";
  }
  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return normalizeText(value);
  }
  return formatDateTimeStamp(parsed);
}

function sourceTierMarkdownLabel(tier: "official" | "media" | "aggregate"): string {
  if (tier === "official") return "官方源";
  if (tier === "aggregate") return "聚合源";
  return "媒体源";
}

function formatInlineList(values: string[], fallback = "—", limit = 6): string {
  const next = uniqueTake(values, limit);
  return next.length ? next.join("；") : fallback;
}

function compareDiffStatusLabel(status: ApiResearchCompareSnapshotLinkedVersionDiff["status"]): string {
  if (status === "aligned") return "主线一致";
  if (status === "expanded") return "快照扩展";
  if (status === "trimmed") return "快照收敛";
  if (status === "mixed") return "双向差异";
  return "无法比较";
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

function extractWeakSections(report: ReportPayload): ResearchCompareWeakSection[] {
  return (report.sections || [])
    .map((section) => ({
      title: normalizeText(section.title || ""),
      status: normalizeText(section.status || ""),
      insufficiencySummary: normalizeText(section.insufficiency_summary || ""),
      insufficiencyReasons: uniqueTake(section.insufficiency_reasons || [], 3),
      nextVerificationSteps: uniqueTake(section.next_verification_steps || [], 3),
    }))
    .filter((section) => {
      if (!section.title) {
        return false;
      }
      return section.status === "needs_evidence" || section.status === "degraded" || Boolean(section.insufficiencySummary);
    })
    .slice(0, 3);
}

function buildCompareWeakSectionGroups(rows: ResearchCompareRow[]): Array<{
  sourceEntryId: string;
  sourceEntryTitle: string;
  updatedAt: string;
  sections: ResearchCompareWeakSection[];
}> {
  const groups = new Map<string, { sourceEntryId: string; sourceEntryTitle: string; updatedAt: string; sections: ResearchCompareWeakSection[] }>();
  rows.forEach((row) => {
    if (!row.weakSections.length || groups.has(row.sourceEntryId)) {
      return;
    }
    groups.set(row.sourceEntryId, {
      sourceEntryId: row.sourceEntryId,
      sourceEntryTitle: row.sourceEntryTitle,
      updatedAt: row.updatedAt,
      sections: row.weakSections,
    });
  });
  return [...groups.values()];
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
  const weakSections = extractWeakSections(report);

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
    weakSections,
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
        weakSections: row.weakSections.length ? row.weakSections : existing.weakSections,
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
        weakSections: existing.weakSections.length ? existing.weakSections : row.weakSections,
      });
    }
  });
  return [...merged.values()].sort(
    (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
  );
}

function buildResearchCompareFilenameBase(
  prefix: string,
  options: ResearchCompareMarkdownOptions = {},
): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const segments = [
    prefix,
    sanitizeFilenamePart(options.snapshotName || ""),
    sanitizeFilenamePart(options.query || ""),
    sanitizeFilenamePart(options.region || ""),
    sanitizeFilenamePart(options.industry || ""),
    options.role && options.role !== "all" ? sanitizeFilenamePart(options.role) : "",
    formatDateStamp(generatedAt),
  ].filter(Boolean);
  return segments.join("-");
}

function collectEvidenceLinks(
  rows: ResearchCompareRow[],
): Array<{ url: string; title: string; sourceTier: "official" | "media" | "aggregate"; sourceLabel: string }> {
  const deduped = new Map<string, { url: string; title: string; sourceTier: "official" | "media" | "aggregate"; sourceLabel: string }>();
  rows.forEach((row) => {
    row.evidenceLinks.forEach((item) => {
      const url = normalizeText(item.url);
      if (!url || deduped.has(url)) {
        return;
      }
      deduped.set(url, {
        url,
        title: normalizeText(item.title || "") || "参考来源",
        sourceTier: item.sourceTier,
        sourceLabel: normalizeText(item.sourceLabel || ""),
      });
    });
  });
  return [...deduped.values()];
}

function buildCompareDeliverySummary(rows: ResearchCompareRow[]): ResearchCompareEvidenceSummary {
  const evidenceLinks = collectEvidenceLinks(rows);
  return {
    sourceEntryCount: new Set(rows.map((row) => row.sourceEntryId).filter(Boolean)).size,
    directEvidenceCount: evidenceLinks.length,
    officialEvidenceCount: evidenceLinks.filter((item) => item.sourceTier === "official").length,
    mediaEvidenceCount: evidenceLinks.filter((item) => item.sourceTier === "media").length,
    aggregateEvidenceCount: evidenceLinks.filter((item) => item.sourceTier === "aggregate").length,
    uncoveredEntities: uniqueTake(
      rows.filter((row) => !row.evidenceLinks.length).map((row) => row.name),
      12,
    ),
    officialCoverageLeaders: rows
      .filter((row) => row.candidateProfileOfficialHitCount > 0)
      .sort((left, right) => {
        if (right.candidateProfileOfficialHitCount !== left.candidateProfileOfficialHitCount) {
          return right.candidateProfileOfficialHitCount - left.candidateProfileOfficialHitCount;
        }
        return right.candidateProfileHitCount - left.candidateProfileHitCount;
      })
      .map((row) => `${row.name} ×${row.candidateProfileOfficialHitCount}`)
      .filter((value, index, list) => list.indexOf(value) === index)
      .slice(0, 4),
  };
}

function buildVersionDiffSummaryLines(linkedDiff: ApiResearchCompareSnapshotLinkedVersionDiff | null): string[] {
  if (!linkedDiff || linkedDiff.status === "unavailable") {
    return [];
  }
  const lines = [
    `差异状态: ${compareDiffStatusLabel(linkedDiff.status)}`,
    `差异标题: ${normalizeText(linkedDiff.headline) || "—"}`,
  ];
  linkedDiff.summary_lines.forEach((line) => {
    lines.push(line);
  });
  linkedDiff.axes.forEach((axis) => {
    lines.push(`${axis.label}: 快照 ${axis.snapshot_count} / 关联版本 ${axis.linked_count} / 交集 ${axis.overlap_count}`);
    if (axis.snapshot_only.length) {
      lines.push(`快照独有: ${formatInlineList(axis.snapshot_only, "无", 4)}`);
    }
    if (axis.linked_only.length) {
      lines.push(`关联版本独有: ${formatInlineList(axis.linked_only, "无", 4)}`);
    }
  });
  return lines;
}

function buildPriorityEntityLines(rows: ResearchCompareRow[]): string[] {
  return rows.slice(0, 5).map((row) => {
    const signals = [row.budgetSignal, row.projectSignal, row.strategySignal]
      .map((value) => normalizeText(value))
      .filter((value) => value && value !== "—")
      .slice(0, 2)
      .join(" / ");
    return `${row.name}｜${row.role}｜${signals || "待补充关键信号"}｜${row.evidenceLinks.length ? `${row.evidenceLinks.length} 条直接证据` : "暂无直接证据"}`;
  });
}

export function summarizeResearchCompareEvidence(rows: ResearchCompareRow[]): ResearchCompareEvidenceSummary {
  return buildCompareDeliverySummary(rows);
}

export function buildResearchCompareExportFilename(options: ResearchCompareMarkdownOptions = {}): string {
  return `${buildResearchCompareFilenameBase("research-compare", options)}.md`;
}

export function buildResearchComparePdfFilename(options: ResearchCompareMarkdownOptions = {}): string {
  return `${buildResearchCompareFilenameBase("research-compare", options)}.pdf`;
}

export function buildResearchCompareExecBriefFilename(options: ResearchCompareMarkdownOptions = {}): string {
  return `${buildResearchCompareFilenameBase("research-compare-exec-brief", options)}.md`;
}

export function buildResearchCompareMarkdown(
  rows: ResearchCompareRow[],
  options: ResearchCompareMarkdownOptions = {},
): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const roleCounts: ResearchCompareRole[] = ["甲方", "中标方", "竞品", "伙伴"];
  const linkedDiff = options.linkedDiff && options.linkedDiff.status !== "unavailable" ? options.linkedDiff : null;
  const evidenceSummary = buildCompareDeliverySummary(rows);
  const lines = [
    "# 甲方 / 中标方 / 竞品 / 伙伴 对比矩阵",
    "",
    `- 导出时间: ${formatDateTimeStamp(generatedAt)}`,
    `- 快照名称: ${normalizeText(options.snapshotName || "") || "实时视图"}`,
    `- 关键词筛选: ${normalizeText(options.query || "") || "全部"}`,
    `- 区域筛选: ${normalizeText(options.region || "") || "全部"}`,
    `- 行业筛选: ${normalizeText(options.industry || "") || "全部"}`,
    `- 角色筛选: ${options.role && options.role !== "all" ? options.role : "全部角色"}`,
    `- 实体数量: ${rows.length}`,
    `- 角色分布: ${roleCounts.map((role) => `${role} ${rows.filter((row) => row.role === role).length}`).join(" | ")}`,
  ];

  if (options.linkedVersionTitle || options.linkedVersionRefreshedAt) {
    lines.push(
      `- 关联版本: ${
        normalizeText(options.linkedVersionTitle || "") || "未绑定"
      }${options.linkedVersionRefreshedAt ? ` (${formatDateTime(options.linkedVersionRefreshedAt)})` : ""}`,
    );
  }

  lines.push("", "## 交付摘要", "");
  lines.push(`- 来源研报数: ${evidenceSummary.sourceEntryCount}`);
  lines.push(`- 直接证据链接: ${evidenceSummary.directEvidenceCount}`);
  lines.push(
    `- 证据结构: 官方源 ${evidenceSummary.officialEvidenceCount} / 媒体源 ${evidenceSummary.mediaEvidenceCount} / 聚合源 ${evidenceSummary.aggregateEvidenceCount}`,
  );
  lines.push(`- 无直接证据实体: ${formatInlineList(evidenceSummary.uncoveredEntities, "无", 6)}`);
  if (evidenceSummary.officialCoverageLeaders.length) {
    lines.push(`- 官方补证命中最高: ${formatInlineList(evidenceSummary.officialCoverageLeaders, "无", 4)}`);
  }

  if (linkedDiff) {
    lines.push("", "## 版本差异摘要", "");
    lines.push(`- 差异状态: ${compareDiffStatusLabel(linkedDiff.status)}`);
    lines.push(`- 差异标题: ${linkedDiff.headline || "—"}`);
    if (linkedDiff.summary_lines.length) {
      lines.push("", "### 差异摘要", "");
      linkedDiff.summary_lines.forEach((line) => {
        lines.push(`- ${line}`);
      });
    }
    if (linkedDiff.axes.length) {
      lines.push("", "### 轴向差异", "");
      linkedDiff.axes.forEach((axis) => {
        lines.push(`- ${axis.label}: 快照 ${axis.snapshot_count} / 关联版本 ${axis.linked_count} / 交集 ${axis.overlap_count}`);
        lines.push(`  - 快照独有: ${formatInlineList(axis.snapshot_only, "无", 4)}`);
        lines.push(`  - 关联版本独有: ${formatInlineList(axis.linked_only, "无", 4)}`);
      });
    }
  }

  const weakSectionGroups = buildCompareWeakSectionGroups(rows);
  if (weakSectionGroups.length) {
    lines.push("", "## Section Evidence Diagnostics", "");
    weakSectionGroups.forEach((group) => {
      lines.push(`### ${group.sourceEntryTitle}`);
      lines.push("");
      lines.push(`- 最近更新时间: ${formatDateTime(group.updatedAt)}`);
      group.sections.forEach((section) => {
        lines.push(`- ${section.title}: ${section.insufficiencySummary || formatInlineList(section.insufficiencyReasons, "仍需补证", 3)}`);
        if (section.nextVerificationSteps.length) {
          lines.push(`  - 建议补证: ${formatInlineList(section.nextVerificationSteps, "无", 2)}`);
        }
      });
      lines.push("");
    });
  }

  if (!rows.length) {
    lines.push("", "## 当前结果", "", "- 当前筛选下没有可导出的实体线索。");
    return sanitizeExternalDisplayText(lines.join("\n"));
  }

  lines.push("", "## 对比清单", "");
  rows.forEach((row, index) => {
    lines.push(`### ${index + 1}. ${row.name}｜${row.role}`);
    lines.push("");
    lines.push(`- 线索摘要: ${row.clue}`);
    lines.push(`- 地区 / 行业: ${formatInlineList([row.region, row.industry], "未标注", 2)}`);
    lines.push(`- 关键词: ${row.keyword || "—"}`);
    lines.push(`- 预算信号: ${row.budgetSignal}`);
    lines.push(`- 预算区间: ${row.budgetRange}`);
    lines.push(`- 项目 / 招采: ${row.projectSignal}`);
    lines.push(`- 战略 / 讲话: ${row.strategySignal}`);
    lines.push(`- 竞合压力: ${row.competitionSignal}`);
    lines.push(`- 高概率决策部门: ${formatInlineList(row.targetDepartments)}`);
    lines.push(`- 公开业务联系方式: ${formatInlineList(row.publicContacts)}`);
    lines.push(`- 竞品公司: ${formatInlineList(row.competitorHighlights)}`);
    lines.push(`- 生态伙伴: ${formatInlineList(row.partnerHighlights)}`);
    lines.push(`- 标杆案例: ${formatInlineList(row.benchmarkCases)}`);
    lines.push(`- 候选补证公司: ${formatInlineList(row.candidateProfileCompanies)}`);
    lines.push(`- 补证公开源命中: ${row.candidateProfileHitCount}`);
    lines.push(`- 补证官方源命中: ${row.candidateProfileOfficialHitCount}`);
    lines.push(`- 补证来源标签: ${formatInlineList(row.candidateProfileSourceLabels)}`);
    lines.push(`- 来源研报: ${row.sourceEntryTitle}`);
    lines.push(`- 来源数: ${row.sourceCount}`);
    lines.push(`- 最近更新时间: ${formatDateStamp(new Date(row.updatedAt))}`);
    lines.push("");
  });

  lines.push("## Evidence Appendix Summary", "");
  lines.push(`- 附录直接证据总数: ${evidenceSummary.directEvidenceCount}`);
  lines.push(`- 官方源证据: ${evidenceSummary.officialEvidenceCount}`);
  lines.push(`- 媒体源证据: ${evidenceSummary.mediaEvidenceCount}`);
  lines.push(`- 聚合源证据: ${evidenceSummary.aggregateEvidenceCount}`);
  lines.push(`- 需继续补证实体: ${formatInlineList(evidenceSummary.uncoveredEntities, "无", 6)}`);
  lines.push("");
  lines.push("## 证据附录", "");
  rows.forEach((row, index) => {
    lines.push(`### ${index + 1}. ${row.name}｜${row.role}`);
    lines.push("");
    if (!row.evidenceLinks.length) {
      lines.push("- 暂无可直接打开的证据链接。");
      lines.push("");
      return;
    }
    row.evidenceLinks.forEach((item, evidenceIndex) => {
      lines.push(`${evidenceIndex + 1}. ${item.title}`);
      lines.push(`   - 来源层级: ${sourceTierMarkdownLabel(item.sourceTier)}`);
      lines.push(`   - 来源标签: ${item.sourceLabel || "—"}`);
      lines.push(`   - 链接: ${item.url}`);
    });
    lines.push("");
  });

  return sanitizeExternalDisplayText(lines.join("\n"));
}

export function buildResearchCompareExecBrief(
  rows: ResearchCompareRow[],
  options: ResearchCompareMarkdownOptions = {},
): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const roleCounts: ResearchCompareRole[] = ["甲方", "中标方", "竞品", "伙伴"];
  const linkedDiff = options.linkedDiff && options.linkedDiff.status !== "unavailable" ? options.linkedDiff : null;
  const evidenceSummary = buildCompareDeliverySummary(rows);
  const lines = [
    "# Compare Exec Brief",
    "",
    `- 导出时间: ${formatDateTimeStamp(generatedAt)}`,
    `- 快照名称: ${normalizeText(options.snapshotName || "") || "实时视图"}`,
    `- 关键词 / 区域 / 行业: ${formatInlineList([options.query || "全部", options.region || "全部", options.industry || "全部"], "全部", 3)}`,
    `- 实体概览: ${rows.length} 个实体；${roleCounts.map((role) => `${role} ${rows.filter((row) => row.role === role).length}`).join(" | ")}`,
    `- 直接证据: ${evidenceSummary.directEvidenceCount} 条，其中官方源 ${evidenceSummary.officialEvidenceCount} 条`,
    `- 无直接证据实体: ${formatInlineList(evidenceSummary.uncoveredEntities, "无", 4)}`,
  ];

  if (options.linkedVersionTitle || options.linkedVersionRefreshedAt) {
    lines.push(
      `- 关联版本: ${
        normalizeText(options.linkedVersionTitle || "") || "未绑定"
      }${options.linkedVersionRefreshedAt ? ` (${formatDateTime(options.linkedVersionRefreshedAt)})` : ""}`,
    );
  }

  const weakSectionGroups = buildCompareWeakSectionGroups(rows);
  if (weakSectionGroups.length) {
    lines.push("", "## 待补证章节", "");
    weakSectionGroups.slice(0, 3).forEach((group) => {
      const sectionLines = group.sections
        .slice(0, 2)
        .map((section) => `${section.title}：${section.insufficiencySummary || formatInlineList(section.insufficiencyReasons, "仍需补证", 2)}`)
        .join("；");
      lines.push(`- ${group.sourceEntryTitle}: ${sectionLines || "仍需补证章节"}`);
    });
  }

  lines.push("", "## 管理层判断", "");
  const diffLines = buildVersionDiffSummaryLines(linkedDiff);
  if (diffLines.length) {
    diffLines.slice(0, 5).forEach((line) => {
      lines.push(`- ${line}`);
    });
  } else {
    lines.push("- 当前快照未绑定可比较的研报版本，建议先保存版本基线。");
  }

  lines.push("", "## 优先实体", "");
  const priorityLines = buildPriorityEntityLines(rows);
  (priorityLines.length ? priorityLines : ["当前筛选下暂无可导出的实体。"]).forEach((line) => {
    lines.push(`- ${line}`);
  });

  lines.push("", "## 后续动作", "");
  lines.push(`- 优先复核 ${formatInlineList(evidenceSummary.uncoveredEntities, "暂无", 3)} 这类缺少直接证据的实体。`);
  if (evidenceSummary.officialCoverageLeaders.length) {
    lines.push(`- 可围绕 ${formatInlineList(evidenceSummary.officialCoverageLeaders, "无", 3)} 继续扩展官网/IR/招采公开源。`);
  } else {
    lines.push("- 当前没有明显的官方补证强命中实体，建议继续追加官方源 corrective retrieval。");
  }
  return sanitizeExternalDisplayText(lines.join("\n"));
}

export function buildResearchComparePlainText(
  rows: ResearchCompareRow[],
  options: ResearchCompareMarkdownOptions = {},
): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const roleCounts: ResearchCompareRole[] = ["甲方", "中标方", "竞品", "伙伴"];
  const linkedDiff = options.linkedDiff && options.linkedDiff.status !== "unavailable" ? options.linkedDiff : null;
  const evidenceSummary = buildCompareDeliverySummary(rows);
  const lines = [
    "甲方 / 中标方 / 竞品 / 伙伴 对比矩阵",
    `导出时间: ${formatDateTimeStamp(generatedAt)}`,
    `快照名称: ${normalizeText(options.snapshotName || "") || "实时视图"}`,
    `关键词筛选: ${normalizeText(options.query || "") || "全部"}`,
    `区域筛选: ${normalizeText(options.region || "") || "全部"}`,
    `行业筛选: ${normalizeText(options.industry || "") || "全部"}`,
    `角色筛选: ${options.role && options.role !== "all" ? options.role : "全部角色"}`,
    `实体数量: ${rows.length}`,
    `角色分布: ${roleCounts.map((role) => `${role} ${rows.filter((row) => row.role === role).length}`).join(" | ")}`,
    "",
    "交付摘要",
    `来源研报数: ${evidenceSummary.sourceEntryCount}`,
    `直接证据链接: ${evidenceSummary.directEvidenceCount}`,
    `证据结构: 官方源 ${evidenceSummary.officialEvidenceCount} / 媒体源 ${evidenceSummary.mediaEvidenceCount} / 聚合源 ${evidenceSummary.aggregateEvidenceCount}`,
    `无直接证据实体: ${formatInlineList(evidenceSummary.uncoveredEntities, "无", 6)}`,
  ];

  if (evidenceSummary.officialCoverageLeaders.length) {
    lines.push(`官方补证命中最高: ${formatInlineList(evidenceSummary.officialCoverageLeaders, "无", 4)}`);
  }
  if (options.linkedVersionTitle || options.linkedVersionRefreshedAt) {
    lines.push(
      `关联版本: ${
        normalizeText(options.linkedVersionTitle || "") || "未绑定"
      }${options.linkedVersionRefreshedAt ? ` (${formatDateTime(options.linkedVersionRefreshedAt)})` : ""}`,
    );
  }
  if (linkedDiff) {
    lines.push("", "版本差异摘要");
    buildVersionDiffSummaryLines(linkedDiff).forEach((line) => {
      lines.push(line);
    });
  }

  const weakSectionGroups = buildCompareWeakSectionGroups(rows);
  if (weakSectionGroups.length) {
    lines.push("", "Section Evidence Diagnostics");
    weakSectionGroups.forEach((group) => {
      lines.push(group.sourceEntryTitle);
      group.sections.forEach((section) => {
        lines.push(`${section.title}: ${section.insufficiencySummary || formatInlineList(section.insufficiencyReasons, "仍需补证", 3)}`);
        if (section.nextVerificationSteps.length) {
          lines.push(`建议补证: ${formatInlineList(section.nextVerificationSteps, "无", 2)}`);
        }
      });
      lines.push("");
    });
  }

  lines.push("", "对比清单");
  if (!rows.length) {
    lines.push("当前筛选下没有可导出的实体线索。");
  }
  rows.forEach((row, index) => {
    lines.push("");
    lines.push(`${index + 1}. ${row.name} | ${row.role}`);
    lines.push(`线索摘要: ${row.clue}`);
    lines.push(`地区 / 行业: ${formatInlineList([row.region, row.industry], "未标注", 2)}`);
    lines.push(`预算信号: ${row.budgetSignal}`);
    lines.push(`项目 / 招采: ${row.projectSignal}`);
    lines.push(`战略 / 讲话: ${row.strategySignal}`);
    lines.push(`竞合压力: ${row.competitionSignal}`);
    lines.push(`高概率决策部门: ${formatInlineList(row.targetDepartments)}`);
    lines.push(`公开业务联系方式: ${formatInlineList(row.publicContacts)}`);
    lines.push(`候选补证公司: ${formatInlineList(row.candidateProfileCompanies)}`);
    lines.push(`补证公开源命中: ${row.candidateProfileHitCount}`);
    lines.push(`补证官方源命中: ${row.candidateProfileOfficialHitCount}`);
    lines.push(`来源研报: ${row.sourceEntryTitle}`);
    lines.push(`最近更新时间: ${formatDateStamp(new Date(row.updatedAt))}`);
  });

  lines.push("", "Evidence Appendix Summary");
  lines.push(`附录直接证据总数: ${evidenceSummary.directEvidenceCount}`);
  lines.push(`官方源证据: ${evidenceSummary.officialEvidenceCount}`);
  lines.push(`媒体源证据: ${evidenceSummary.mediaEvidenceCount}`);
  lines.push(`聚合源证据: ${evidenceSummary.aggregateEvidenceCount}`);

  lines.push("", "证据附录");
  rows.forEach((row, index) => {
    lines.push("");
    lines.push(`${index + 1}. ${row.name} | ${row.role}`);
    if (!row.evidenceLinks.length) {
      lines.push("暂无可直接打开的证据链接。");
      return;
    }
    row.evidenceLinks.forEach((item, evidenceIndex) => {
      lines.push(`${evidenceIndex + 1}. ${item.title}`);
      lines.push(`来源层级: ${sourceTierMarkdownLabel(item.sourceTier)}`);
      lines.push(`来源标签: ${item.sourceLabel || "—"}`);
      lines.push(`链接: ${item.url}`);
    });
  });
  return sanitizeExternalDisplayText(lines.join("\n"));
}
