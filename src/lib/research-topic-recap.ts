import type {
  ApiResearchOfflineEvaluation,
  ApiResearchRankedEntity,
  ApiResearchTrackingTopic,
  ApiResearchTrackingTopicTimelineEvent,
  ApiResearchTrackingTopicVersionDetail,
} from "@/lib/api";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";

type ResearchTopicRecapEvidenceLink = {
  title: string;
  url: string;
  meta: string;
  tierLabel: string;
};

export type ResearchTopicRecapDiffHighlight = {
  title: string;
  items: string[];
};

export type ResearchTopicRecapFieldDiffRow = {
  key: string;
  title: string;
  baseline: string[];
  current: string[];
  added: string[];
  removed: string[];
  rewritten: string[];
  baselineEvidenceLinks: ResearchTopicRecapEvidenceLink[];
  currentEvidenceLinks: ResearchTopicRecapEvidenceLink[];
};

export type ResearchTopicRecapScorePanel = {
  key: string;
  title: string;
  baselineEntities: ApiResearchRankedEntity[];
  currentEntities: ApiResearchRankedEntity[];
};

export type ResearchTopicRecapSourceContributionRow = {
  tier: "official" | "media" | "aggregate";
  label: string;
  score: number;
  percent: number;
};

export type ResearchTopicRecapSourceContributionPanel = {
  key: string;
  title: string;
  baselineRows: ResearchTopicRecapSourceContributionRow[];
  currentRows: ResearchTopicRecapSourceContributionRow[];
};

export interface ResearchTopicRecapMarkdownOptions {
  topic: ApiResearchTrackingTopic;
  baselineVersion: ApiResearchTrackingTopicVersionDetail | null;
  currentVersion: ApiResearchTrackingTopicVersionDetail | null;
  compareSummary: string[];
  diffHighlights: ResearchTopicRecapDiffHighlight[];
  fieldDiffRows: ResearchTopicRecapFieldDiffRow[];
  scorePanels: ResearchTopicRecapScorePanel[];
  sourceContributionPanels: ResearchTopicRecapSourceContributionPanel[];
  timelineEvents: ApiResearchTrackingTopicTimelineEvent[];
  generatedAt?: Date;
  offlineEvaluation?: ApiResearchOfflineEvaluation | null;
}

export interface ResearchTopicRecapEvidenceSummary {
  changedFieldCount: number;
  evidenceBackedFieldCount: number;
  baselineEvidenceCount: number;
  currentEvidenceCount: number;
  officialEvidenceCount: number;
  mediaEvidenceCount: number;
  aggregateEvidenceCount: number;
  fieldsWithoutEvidence: string[];
}

export interface ResearchTopicSectionDiagnosticsSummary {
  baselineWeakSectionCount: number;
  currentWeakSectionCount: number;
  newlyWeakSections: string[];
  resolvedSections: string[];
  quotaRiskSectionCount: number;
  contradictionSectionCount: number;
  highlightedSections: string[];
}

type ResearchTopicWeakSection = {
  title: string;
  status: string;
  insufficiencySummary: string;
  insufficiencyReasons: string[];
  nextVerificationSteps: string[];
  evidenceQuota: number;
  meetsEvidenceQuota: boolean;
  quotaGap: number;
  contradictionDetected: boolean;
};

function normalizeText(value: unknown): string {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function uniqueTake(values: string[], limit = 6): string[] {
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

function qualityLabel(value: string | null | undefined): string {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  if (value === "low") return "低";
  return "—";
}

function formatInlineList(values: string[], fallback = "无", limit = 4): string {
  const next = uniqueTake(values, limit);
  return next.length ? next.join("；") : fallback;
}

function trimText(value: string, limit = 96): string {
  const normalized = normalizeText(value);
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, limit - 1)).trim()}…`;
}

function markdownLink(title: string, url: string): string {
  const normalizedTitle = normalizeText(title) || "参考来源";
  const normalizedUrl = normalizeText(url);
  if (!normalizedUrl) {
    return normalizedTitle;
  }
  return `[${normalizedTitle}](${normalizedUrl})`;
}

function formatEvidenceLinks(
  links: ResearchTopicRecapEvidenceLink[],
  fallback = "无",
  markdown = true,
): string {
  if (!links.length) {
    return fallback;
  }
  return links
    .slice(0, 3)
    .map((link) => {
      const details = [normalizeText(link.meta), normalizeText(link.tierLabel)].filter(Boolean).join(" / ");
      const label = markdown
        ? markdownLink(link.title, link.url)
        : `${normalizeText(link.title) || "参考来源"}${link.url ? ` | ${normalizeText(link.url)}` : ""}`;
      return `${label}${details ? `（${details}）` : ""}`;
    })
    .join("；");
}

function formatVersionSummary(version: ApiResearchTrackingTopicVersionDetail | null): string {
  if (!version) {
    return "—";
  }
  const segments = [
    version.title,
    formatDateTime(version.refreshed_at),
    `来源数 ${version.source_count}`,
    `证据密度 ${qualityLabel(version.evidence_density)}`,
    `来源质量 ${qualityLabel(version.source_quality)}`,
  ];
  return segments.join("｜");
}

function formatEntityRows(entities: ApiResearchRankedEntity[]): string {
  if (!entities.length) {
    return "无";
  }
  return entities
    .slice(0, 3)
    .map((entity) => {
      const reasoning = trimText(entity.reasoning || "", 72);
      return `${entity.name} ${Math.round(entity.score)}分${reasoning ? `（${reasoning}）` : ""}`;
    })
    .join("；");
}

function formatContributionRows(rows: ResearchTopicRecapSourceContributionRow[]): string {
  if (!rows.length) {
    return "无";
  }
  return rows
    .slice(0, 3)
    .map((row) => `${row.label} ${row.percent}%`)
    .join(" / ");
}

function buildResearchTopicFilenameBase(topicName: string, prefix: string, generatedAt: Date = new Date()): string {
  const segments = [
    prefix,
    sanitizeFilenamePart(topicName),
    formatDateStamp(generatedAt),
  ].filter(Boolean);
  return segments.join("-");
}

function classifyEvidenceTierLabel(tierLabel: string): "official" | "media" | "aggregate" {
  const normalized = normalizeText(tierLabel);
  if (normalized.includes("官方")) return "official";
  if (normalized.includes("聚合")) return "aggregate";
  return "media";
}

function buildTopicEvidenceSummary(fieldDiffRows: ResearchTopicRecapFieldDiffRow[]): ResearchTopicRecapEvidenceSummary {
  const evidenceLinks = new Map<string, ResearchTopicRecapEvidenceLink>();
  fieldDiffRows.forEach((row) => {
    [...row.baselineEvidenceLinks, ...row.currentEvidenceLinks].forEach((link) => {
      const url = normalizeText(link.url);
      if (!url || evidenceLinks.has(url)) {
        return;
      }
      evidenceLinks.set(url, link);
    });
  });
  const evidenceValues = [...evidenceLinks.values()];
  return {
    changedFieldCount: fieldDiffRows.length,
    evidenceBackedFieldCount: fieldDiffRows.filter((row) => row.baselineEvidenceLinks.length || row.currentEvidenceLinks.length).length,
    baselineEvidenceCount: evidenceValues.filter((link) => fieldDiffRows.some((row) => row.baselineEvidenceLinks.some((item) => item.url === link.url))).length,
    currentEvidenceCount: evidenceValues.filter((link) => fieldDiffRows.some((row) => row.currentEvidenceLinks.some((item) => item.url === link.url))).length,
    officialEvidenceCount: evidenceValues.filter((link) => classifyEvidenceTierLabel(link.tierLabel) === "official").length,
    mediaEvidenceCount: evidenceValues.filter((link) => classifyEvidenceTierLabel(link.tierLabel) === "media").length,
    aggregateEvidenceCount: evidenceValues.filter((link) => classifyEvidenceTierLabel(link.tierLabel) === "aggregate").length,
    fieldsWithoutEvidence: uniqueTake(
      fieldDiffRows
        .filter((row) => !row.baselineEvidenceLinks.length && !row.currentEvidenceLinks.length)
        .map((row) => row.title),
      10,
    ),
  };
}

function extractTopicWeakSections(version: ApiResearchTrackingTopicVersionDetail | null): ResearchTopicWeakSection[] {
  return (version?.report?.sections || [])
    .map((section) => ({
      title: normalizeText(section.title || ""),
      status: normalizeText(section.status || ""),
      insufficiencySummary: normalizeText(section.insufficiency_summary || ""),
      insufficiencyReasons: uniqueTake(section.insufficiency_reasons || [], 3),
      nextVerificationSteps: uniqueTake(section.next_verification_steps || [], 3),
      evidenceQuota: Math.max(0, Number(section.evidence_quota || 0)),
      meetsEvidenceQuota: Boolean(section.meets_evidence_quota),
      quotaGap: Math.max(0, Number(section.quota_gap || 0)),
      contradictionDetected: Boolean(section.contradiction_detected),
    }))
    .filter((section) => {
      if (!section.title) {
        return false;
      }
      return (
        section.status === "needs_evidence" ||
        section.status === "degraded" ||
        Boolean(section.insufficiencySummary) ||
        (section.evidenceQuota > 0 && !section.meetsEvidenceQuota) ||
        section.contradictionDetected
      );
    })
    .slice(0, 4);
}

function buildTopicWeakSectionSummary(
  baselineVersion: ApiResearchTrackingTopicVersionDetail | null,
  currentVersion: ApiResearchTrackingTopicVersionDetail | null,
) {
  const baselineSections = extractTopicWeakSections(baselineVersion);
  const currentSections = extractTopicWeakSections(currentVersion);
  const baselineTitles = new Set(baselineSections.map((section) => section.title));
  const currentTitles = new Set(currentSections.map((section) => section.title));
  return {
    baselineSections,
    currentSections,
    newlyWeakSections: currentSections.filter((section) => !baselineTitles.has(section.title)).map((section) => section.title),
    resolvedSections: baselineSections.filter((section) => !currentTitles.has(section.title)).map((section) => section.title),
  };
}

function buildTopicSectionDiagnosticsSummary(
  baselineVersion: ApiResearchTrackingTopicVersionDetail | null,
  currentVersion: ApiResearchTrackingTopicVersionDetail | null,
): ResearchTopicSectionDiagnosticsSummary {
  const weakSummary = buildTopicWeakSectionSummary(baselineVersion, currentVersion);
  return {
    baselineWeakSectionCount: weakSummary.baselineSections.length,
    currentWeakSectionCount: weakSummary.currentSections.length,
    newlyWeakSections: weakSummary.newlyWeakSections,
    resolvedSections: weakSummary.resolvedSections,
    quotaRiskSectionCount: weakSummary.currentSections.filter(
      (section) => (section.evidenceQuota > 0 && !section.meetsEvidenceQuota) || section.quotaGap > 0,
    ).length,
    contradictionSectionCount: weakSummary.currentSections.filter((section) => section.contradictionDetected).length,
    highlightedSections: uniqueTake(
      weakSummary.currentSections.map((section) =>
        section.quotaGap > 0 ? `${section.title}（待补 ${section.quotaGap}）` : section.title,
      ),
      8,
    ),
  };
}

function buildVersionConclusionRows(options: ResearchTopicRecapMarkdownOptions): string[] {
  return options.compareSummary.length
    ? options.compareSummary
    : ["最近两次版本在关键指标上基本稳定。"];
}

function buildDiffHighlightRows(options: ResearchTopicRecapMarkdownOptions): string[] {
  return options.diffHighlights.flatMap((group) => group.items.map((item) => `${group.title}: ${item}`)).slice(0, 6);
}

function buildFieldEvidenceAppendixLines(
  fieldDiffRows: ResearchTopicRecapFieldDiffRow[],
  markdown = true,
): string[] {
  const lines: string[] = [];
  fieldDiffRows.forEach((row) => {
    lines.push(markdown ? `### ${row.title}` : row.title);
    lines.push("");
    lines.push(markdown ? `- 基线证据: ${formatEvidenceLinks(row.baselineEvidenceLinks)}` : `基线证据: ${formatEvidenceLinks(row.baselineEvidenceLinks, "无", false)}`);
    lines.push(markdown ? `- 对照证据: ${formatEvidenceLinks(row.currentEvidenceLinks)}` : `对照证据: ${formatEvidenceLinks(row.currentEvidenceLinks, "无", false)}`);
    lines.push(markdown ? `- 变化摘要: 新增 ${formatInlineList(row.added, "无")}；减少 ${formatInlineList(row.removed, "无")}；改写 ${formatInlineList(row.rewritten, "无", 3)}` : `变化摘要: 新增 ${formatInlineList(row.added, "无")}；减少 ${formatInlineList(row.removed, "无")}；改写 ${formatInlineList(row.rewritten, "无", 3)}`);
    lines.push("");
  });
  return lines;
}

export function summarizeResearchTopicRecapEvidence(
  fieldDiffRows: ResearchTopicRecapFieldDiffRow[],
): ResearchTopicRecapEvidenceSummary {
  return buildTopicEvidenceSummary(fieldDiffRows);
}

export function summarizeResearchTopicSectionDiagnostics(
  baselineVersion: ApiResearchTrackingTopicVersionDetail | null,
  currentVersion: ApiResearchTrackingTopicVersionDetail | null,
): ResearchTopicSectionDiagnosticsSummary {
  return buildTopicSectionDiagnosticsSummary(baselineVersion, currentVersion);
}

function offlineStatusLabel(status: string): string {
  if (status === "good") return "达标";
  if (status === "watch") return "观察";
  return "偏弱";
}

function buildOfflineEvaluationLines(
  offlineEvaluation: ApiResearchOfflineEvaluation | null | undefined,
): string[] {
  if (!offlineEvaluation?.metrics?.length) {
    return [];
  }
  const lines = offlineEvaluation.metrics.map((metric) => {
    const benchmark = Math.round(Number(metric.benchmark || 0) * 100);
    return `${metric.label} ${metric.percent}%（${offlineStatusLabel(metric.status)}；当前 ${metric.numerator}/${metric.denominator}；基准 ${benchmark}%）`;
  });
  if (offlineEvaluation.summary_lines?.length) {
    lines.push(...offlineEvaluation.summary_lines.slice(0, 2));
  }
  return uniqueTake(lines, 5);
}

export function buildResearchTopicRecapExportFilename(topicName: string, generatedAt: Date = new Date()): string {
  return `${buildResearchTopicFilenameBase(topicName, "research-topic-recap", generatedAt)}.md`;
}

export function buildResearchTopicRecapPdfFilename(topicName: string, generatedAt: Date = new Date()): string {
  return `${buildResearchTopicFilenameBase(topicName, "research-topic-recap", generatedAt)}.pdf`;
}

export function buildResearchTopicRecapExecBriefFilename(topicName: string, generatedAt: Date = new Date()): string {
  return `${buildResearchTopicFilenameBase(topicName, "research-topic-exec-brief", generatedAt)}.md`;
}

export function buildResearchTopicRecapMarkdown(options: ResearchTopicRecapMarkdownOptions): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const baselineVersion = options.baselineVersion;
  const currentVersion = options.currentVersion;
  const evidenceSummary = buildTopicEvidenceSummary(options.fieldDiffRows);
  const weakSectionSummary = buildTopicWeakSectionSummary(baselineVersion, currentVersion);
  const sectionDiagnostics = buildTopicSectionDiagnosticsSummary(baselineVersion, currentVersion);
  const offlineEvaluationLines = buildOfflineEvaluationLines(options.offlineEvaluation);
  const lines = [
    "# 专题版本复盘报告",
    "",
    `- 导出时间: ${formatDateTimeStamp(generatedAt)}`,
    `- 专题名称: ${options.topic.name}`,
    `- 关键词: ${normalizeText(options.topic.keyword) || "—"}`,
    `- 研究焦点: ${normalizeText(options.topic.research_focus) || "—"}`,
    `- 区域筛选: ${normalizeText(options.topic.region_filter) || "全部"}`,
    `- 行业筛选: ${normalizeText(options.topic.industry_filter) || "全部"}`,
    `- 基线版本: ${formatVersionSummary(baselineVersion)}`,
    `- 对照版本: ${formatVersionSummary(currentVersion)}`,
  ];

  lines.push("", "## 版本结论", "");
  buildVersionConclusionRows(options).forEach((row) => {
    lines.push(`- ${row}`);
  });

  const baselineSummary = trimText(baselineVersion?.report?.executive_summary || "", 160);
  const currentSummary = trimText(currentVersion?.report?.executive_summary || "", 160);
  if (baselineSummary || currentSummary) {
    lines.push("", "## 执行摘要对照", "");
    lines.push(`- 基线版本摘要: ${baselineSummary || "无"}`);
    lines.push(`- 对照版本摘要: ${currentSummary || "无"}`);
  }

  if (options.diffHighlights.length) {
    lines.push("", "## 关键差异高亮", "");
    options.diffHighlights.forEach((group) => {
      lines.push(`### ${group.title}`);
      lines.push("");
      group.items.forEach((item) => {
        lines.push(`- ${item}`);
      });
      lines.push("");
    });
  }

  if (weakSectionSummary.baselineSections.length || weakSectionSummary.currentSections.length) {
    lines.push("", "## 待补证章节变化", "");
    lines.push(`- 基线版本待补证章节: ${formatInlineList(weakSectionSummary.baselineSections.map((section) => section.title), "无", 4)}`);
    lines.push(`- 对照版本待补证章节: ${formatInlineList(weakSectionSummary.currentSections.map((section) => section.title), "无", 4)}`);
    if (weakSectionSummary.newlyWeakSections.length) {
      lines.push(`- 新增待补证章节: ${formatInlineList(weakSectionSummary.newlyWeakSections, "无", 3)}`);
    }
    if (weakSectionSummary.resolvedSections.length) {
      lines.push(`- 已脱离待补证章节: ${formatInlineList(weakSectionSummary.resolvedSections, "无", 3)}`);
    }
    lines.push("");
    weakSectionSummary.currentSections.slice(0, 3).forEach((section) => {
      lines.push(`### ${section.title}`);
      lines.push("");
      lines.push(`- 不足原因: ${section.insufficiencySummary || formatInlineList(section.insufficiencyReasons, "仍需补证", 3)}`);
      if (section.nextVerificationSteps.length) {
        lines.push(`- 建议补证: ${formatInlineList(section.nextVerificationSteps, "无", 3)}`);
      }
      lines.push("");
    });
  }

  if (sectionDiagnostics.currentWeakSectionCount || sectionDiagnostics.baselineWeakSectionCount) {
    lines.push("", "## Section Diagnostics Summary", "");
    lines.push(`- 基线待补证章节: ${sectionDiagnostics.baselineWeakSectionCount}`);
    lines.push(`- 对照待补证章节: ${sectionDiagnostics.currentWeakSectionCount}`);
    lines.push(`- 新增待补证章节: ${formatInlineList(sectionDiagnostics.newlyWeakSections, "无", 4)}`);
    lines.push(`- 已解决章节: ${formatInlineList(sectionDiagnostics.resolvedSections, "无", 4)}`);
    lines.push(`- 配额未达标章节: ${sectionDiagnostics.quotaRiskSectionCount}`);
    lines.push(`- 矛盾章节: ${sectionDiagnostics.contradictionSectionCount}`);
    lines.push(`- 重点章节: ${formatInlineList(sectionDiagnostics.highlightedSections, "无", 5)}`);
  }

  if (options.fieldDiffRows.length) {
    lines.push("## 字段级 Diff", "");
    options.fieldDiffRows.forEach((row) => {
      lines.push(`### ${row.title}`);
      lines.push("");
      lines.push(`- 基线版本: ${formatInlineList(row.baseline, "暂无明确线索")}`);
      lines.push(`- 对照版本: ${formatInlineList(row.current, "暂无明确线索")}`);
      lines.push(`- 新增: ${formatInlineList(row.added, "无")}`);
      lines.push(`- 减少: ${formatInlineList(row.removed, "无")}`);
      lines.push(`- 改写: ${formatInlineList(row.rewritten, "无", 3)}`);
      lines.push(`- 基线证据: ${formatEvidenceLinks(row.baselineEvidenceLinks)}`);
      lines.push(`- 对照证据: ${formatEvidenceLinks(row.currentEvidenceLinks)}`);
      lines.push("");
    });
  }

  if (options.fieldDiffRows.length) {
    lines.push("## Evidence Appendix Summary", "");
    lines.push(`- 变更字段数: ${evidenceSummary.changedFieldCount}`);
    lines.push(`- 已有证据支撑字段: ${evidenceSummary.evidenceBackedFieldCount}`);
    lines.push(`- 基线证据链接: ${evidenceSummary.baselineEvidenceCount}`);
    lines.push(`- 对照证据链接: ${evidenceSummary.currentEvidenceCount}`);
    lines.push(`- 证据结构: 官方源 ${evidenceSummary.officialEvidenceCount} / 媒体源 ${evidenceSummary.mediaEvidenceCount} / 聚合源 ${evidenceSummary.aggregateEvidenceCount}`);
    lines.push(`- 待补证字段: ${formatInlineList(evidenceSummary.fieldsWithoutEvidence, "无", 5)}`);
    lines.push("");
    lines.push("## 证据附录", "");
    buildFieldEvidenceAppendixLines(options.fieldDiffRows).forEach((line) => {
      lines.push(line);
    });
  }

  if (options.scorePanels.length) {
    lines.push("## Top 3 评分变化", "");
    options.scorePanels.forEach((panel) => {
      lines.push(`### ${panel.title}`);
      lines.push("");
      lines.push(`- 基线版本: ${formatEntityRows(panel.baselineEntities)}`);
      lines.push(`- 对照版本: ${formatEntityRows(panel.currentEntities)}`);
      lines.push("");
    });
  }

  if (options.sourceContributionPanels.length) {
    lines.push("## 来源贡献结构", "");
    options.sourceContributionPanels.forEach((panel) => {
      lines.push(`### ${panel.title}`);
      lines.push("");
      lines.push(`- 基线版本: ${formatContributionRows(panel.baselineRows)}`);
      lines.push(`- 对照版本: ${formatContributionRows(panel.currentRows)}`);
      lines.push("");
    });
  }

  if (offlineEvaluationLines.length) {
    lines.push("## Offline Regression Snapshot", "");
    offlineEvaluationLines.forEach((line) => {
      lines.push(`- ${line}`);
    });
    lines.push("");
  }

  if (options.timelineEvents.length) {
    lines.push("## 时间线摘录", "");
    options.timelineEvents.slice(0, 8).forEach((event) => {
      lines.push(
        `### ${formatDateTime(event.occurred_at)}｜${
          event.event_type === "report_version" ? "研报版本" : "Compare 快照"
        }｜${event.title}`,
      );
      lines.push("");
      lines.push(`- 摘要: ${normalizeText(event.summary) || "无"}`);
      if (event.event_type === "report_version") {
        lines.push(`- 指标: 来源数 ${event.source_count}；证据密度 ${qualityLabel(event.evidence_density)}；来源质量 ${qualityLabel(event.source_quality)}`);
        if (event.new_targets.length || event.new_competitors.length || event.new_budget_signals.length) {
          lines.push(`- 新增变化: 甲方 ${formatInlineList(event.new_targets, "无", 3)}；竞品 ${formatInlineList(event.new_competitors, "无", 3)}；预算 ${formatInlineList(event.new_budget_signals, "无", 2)}`);
        }
      } else {
        lines.push(`- 快照概览: 实体 ${event.row_count}；来源研报 ${event.source_entry_count}；角色 ${formatInlineList(event.roles, "无", 4)}`);
        if (event.linked_report_version_title) {
          lines.push(
            `- 关联版本: ${event.linked_report_version_title}${
              event.linked_report_version_refreshed_at ? `（${formatDateTime(event.linked_report_version_refreshed_at)}）` : ""
            }`,
          );
        }
        if (event.preview_names.length) {
          lines.push(`- 快照预览: ${formatInlineList(event.preview_names, "无", 5)}`);
        }
        if (event.linked_report_diff_summary.length) {
          lines.push(`- 快照 vs 关联版本: ${formatInlineList(event.linked_report_diff_summary, "无", 3)}`);
        }
      }
      lines.push("");
    });
  }

  return sanitizeExternalDisplayText(lines.join("\n"));
}

export function buildResearchTopicRecapExecBrief(options: ResearchTopicRecapMarkdownOptions): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const evidenceSummary = buildTopicEvidenceSummary(options.fieldDiffRows);
  const weakSectionSummary = buildTopicWeakSectionSummary(options.baselineVersion, options.currentVersion);
  const sectionDiagnostics = buildTopicSectionDiagnosticsSummary(options.baselineVersion, options.currentVersion);
  const offlineEvaluationLines = buildOfflineEvaluationLines(options.offlineEvaluation);
  const lines = [
    "# Topic Exec Brief",
    "",
    `- 导出时间: ${formatDateTimeStamp(generatedAt)}`,
    `- 专题名称: ${options.topic.name}`,
    `- 关键词: ${normalizeText(options.topic.keyword) || "—"}`,
    `- 基线版本: ${formatVersionSummary(options.baselineVersion)}`,
    `- 对照版本: ${formatVersionSummary(options.currentVersion)}`,
    `- 证据结构: 官方源 ${evidenceSummary.officialEvidenceCount} / 媒体源 ${evidenceSummary.mediaEvidenceCount} / 聚合源 ${evidenceSummary.aggregateEvidenceCount}`,
    `- 待补证字段: ${formatInlineList(evidenceSummary.fieldsWithoutEvidence, "无", 4)}`,
    `- Section 诊断: 待补证章节 ${sectionDiagnostics.currentWeakSectionCount} / 配额风险 ${sectionDiagnostics.quotaRiskSectionCount} / 矛盾 ${sectionDiagnostics.contradictionSectionCount}`,
  ];

  lines.push("", "## 版本判断", "");
  buildVersionConclusionRows(options).forEach((row) => {
    lines.push(`- ${row}`);
  });

  lines.push("", "## 关键变化", "");
  const diffRows = buildDiffHighlightRows(options);
  (diffRows.length ? diffRows : ["当前版本尚未形成明显新增变化。"]).forEach((row) => {
    lines.push(`- ${row}`);
  });

  lines.push("", "## 高优先级字段", "");
  (options.fieldDiffRows.slice(0, 4).length
    ? options.fieldDiffRows.slice(0, 4).map((row) => `${row.title}: 新增 ${formatInlineList(row.added, "无")}；减少 ${formatInlineList(row.removed, "无")}；改写 ${formatInlineList(row.rewritten, "无", 2)}`)
    : ["当前暂无可导出的字段级 diff。"]).forEach((row) => {
    lines.push(`- ${row}`);
  });

  if (weakSectionSummary.currentSections.length) {
    lines.push("", "## 待补证章节", "");
    weakSectionSummary.currentSections.slice(0, 3).forEach((section) => {
      lines.push(`- ${section.title}: ${section.insufficiencySummary || formatInlineList(section.insufficiencyReasons, "仍需补证", 3)}`);
    });
  }

  if (offlineEvaluationLines.length) {
    lines.push("", "## 离线回归", "");
    offlineEvaluationLines.slice(0, 3).forEach((line) => {
      lines.push(`- ${line}`);
    });
  }

  lines.push("", "## 后续动作", "");
  lines.push(`- 优先补证 ${formatInlineList(evidenceSummary.fieldsWithoutEvidence, "暂无", 3)} 这类还没有直接证据的变化字段。`);
  if (options.sourceContributionPanels.length) {
    lines.push(
      `- 重点关注 ${options.sourceContributionPanels
        .slice(0, 2)
        .map((panel) => `${panel.title}（当前 ${formatContributionRows(panel.currentRows)}）`)
        .join("；") || "当前来源贡献结构"} 的来源层级变化。`,
    );
  }
  return sanitizeExternalDisplayText(lines.join("\n"));
}

export function buildResearchTopicRecapPlainText(options: ResearchTopicRecapMarkdownOptions): string {
  const generatedAt = options.generatedAt instanceof Date ? options.generatedAt : new Date();
  const evidenceSummary = buildTopicEvidenceSummary(options.fieldDiffRows);
  const weakSectionSummary = buildTopicWeakSectionSummary(options.baselineVersion, options.currentVersion);
  const sectionDiagnostics = buildTopicSectionDiagnosticsSummary(options.baselineVersion, options.currentVersion);
  const offlineEvaluationLines = buildOfflineEvaluationLines(options.offlineEvaluation);
  const lines = [
    "专题版本复盘报告",
    `导出时间: ${formatDateTimeStamp(generatedAt)}`,
    `专题名称: ${options.topic.name}`,
    `关键词: ${normalizeText(options.topic.keyword) || "—"}`,
    `研究焦点: ${normalizeText(options.topic.research_focus) || "—"}`,
    `区域筛选: ${normalizeText(options.topic.region_filter) || "全部"}`,
    `行业筛选: ${normalizeText(options.topic.industry_filter) || "全部"}`,
    `基线版本: ${formatVersionSummary(options.baselineVersion)}`,
    `对照版本: ${formatVersionSummary(options.currentVersion)}`,
    `Section 诊断: 待补证章节 ${sectionDiagnostics.currentWeakSectionCount} / 配额风险 ${sectionDiagnostics.quotaRiskSectionCount} / 矛盾 ${sectionDiagnostics.contradictionSectionCount}`,
    "",
    "版本结论",
  ];
  buildVersionConclusionRows(options).forEach((row) => {
    lines.push(row);
  });

  const diffRows = buildDiffHighlightRows(options);
  if (diffRows.length) {
    lines.push("", "关键变化");
    diffRows.forEach((row) => {
      lines.push(row);
    });
  }

  if (weakSectionSummary.baselineSections.length || weakSectionSummary.currentSections.length) {
    lines.push("", "待补证章节变化");
    lines.push(`基线版本待补证章节: ${formatInlineList(weakSectionSummary.baselineSections.map((section) => section.title), "无", 4)}`);
    lines.push(`对照版本待补证章节: ${formatInlineList(weakSectionSummary.currentSections.map((section) => section.title), "无", 4)}`);
    weakSectionSummary.currentSections.slice(0, 3).forEach((section) => {
      lines.push(`${section.title}: ${section.insufficiencySummary || formatInlineList(section.insufficiencyReasons, "仍需补证", 3)}`);
      if (section.nextVerificationSteps.length) {
        lines.push(`建议补证: ${formatInlineList(section.nextVerificationSteps, "无", 3)}`);
      }
    });
  }

  if (offlineEvaluationLines.length) {
    lines.push("", "Offline Regression Snapshot");
    offlineEvaluationLines.forEach((line) => {
      lines.push(line);
    });
  }

  if (options.fieldDiffRows.length) {
    lines.push("", "字段级 Diff");
    options.fieldDiffRows.forEach((row) => {
      lines.push(`${row.title}`);
      lines.push(`基线版本: ${formatInlineList(row.baseline, "暂无明确线索")}`);
      lines.push(`对照版本: ${formatInlineList(row.current, "暂无明确线索")}`);
      lines.push(`新增: ${formatInlineList(row.added, "无")}`);
      lines.push(`减少: ${formatInlineList(row.removed, "无")}`);
      lines.push(`改写: ${formatInlineList(row.rewritten, "无", 3)}`);
      lines.push("");
    });

    lines.push("Evidence Appendix Summary");
    lines.push(`变更字段数: ${evidenceSummary.changedFieldCount}`);
    lines.push(`已有证据支撑字段: ${evidenceSummary.evidenceBackedFieldCount}`);
    lines.push(`基线证据链接: ${evidenceSummary.baselineEvidenceCount}`);
    lines.push(`对照证据链接: ${evidenceSummary.currentEvidenceCount}`);
    lines.push(`证据结构: 官方源 ${evidenceSummary.officialEvidenceCount} / 媒体源 ${evidenceSummary.mediaEvidenceCount} / 聚合源 ${evidenceSummary.aggregateEvidenceCount}`);
    lines.push(`待补证字段: ${formatInlineList(evidenceSummary.fieldsWithoutEvidence, "无", 5)}`);
    lines.push("");
    lines.push("证据附录");
    buildFieldEvidenceAppendixLines(options.fieldDiffRows, false).forEach((line) => {
      lines.push(line);
    });
  }

  if (options.sourceContributionPanels.length) {
    lines.push("来源贡献结构");
    options.sourceContributionPanels.forEach((panel) => {
      lines.push(`${panel.title}`);
      lines.push(`基线版本: ${formatContributionRows(panel.baselineRows)}`);
      lines.push(`对照版本: ${formatContributionRows(panel.currentRows)}`);
      lines.push("");
    });
  }

  if (options.timelineEvents.length) {
    lines.push("时间线摘录");
    options.timelineEvents.slice(0, 6).forEach((event) => {
      lines.push(`${formatDateTime(event.occurred_at)} | ${event.title}`);
      lines.push(`摘要: ${normalizeText(event.summary) || "无"}`);
      lines.push("");
    });
  }

  return sanitizeExternalDisplayText(lines.join("\n"));
}
