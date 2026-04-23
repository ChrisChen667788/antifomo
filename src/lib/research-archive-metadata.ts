import type { ApiResearchMarkdownArchive } from "@/lib/api";

type ArchiveMetadataRecord = Record<string, unknown>;

type CompareArchiveEvidenceSummary = {
  mode: "compare";
  sourceEntryCount: number;
  directEvidenceCount: number;
  officialEvidenceCount: number;
  mediaEvidenceCount: number;
  aggregateEvidenceCount: number;
  uncoveredEntities: string[];
  officialCoverageLeaders: string[];
};

type TopicArchiveEvidenceSummary = {
  mode: "topic";
  changedFieldCount: number;
  evidenceBackedFieldCount: number;
  baselineEvidenceCount: number;
  currentEvidenceCount: number;
  officialEvidenceCount: number;
  mediaEvidenceCount: number;
  aggregateEvidenceCount: number;
  fieldsWithoutEvidence: string[];
};

export type ArchiveEvidenceSummary = CompareArchiveEvidenceSummary | TopicArchiveEvidenceSummary;

type CompareArchiveSectionDiagnosticsSummary = {
  mode: "compare";
  sourceReportCount: number;
  weakSectionCount: number;
  quotaRiskSectionCount: number;
  contradictionSectionCount: number;
  highlightedSections: string[];
};

type TopicArchiveSectionDiagnosticsSummary = {
  mode: "topic";
  baselineWeakSectionCount: number;
  currentWeakSectionCount: number;
  newlyWeakSections: string[];
  resolvedSections: string[];
  quotaRiskSectionCount: number;
  contradictionSectionCount: number;
  highlightedSections: string[];
};

export type ArchiveSectionDiagnosticsSummary =
  | CompareArchiveSectionDiagnosticsSummary
  | TopicArchiveSectionDiagnosticsSummary;

export type ArchiveOfflineEvaluationMetric = {
  key: string;
  label: string;
  percent: number;
  status: string;
  benchmark: number;
  numerator: number;
  denominator: number;
};

export type ArchiveOfflineEvaluationSnapshot = {
  totalReports: number;
  evaluatedReports: number;
  invalidPayloads: number;
  generatedAt: string;
  metrics: ArchiveOfflineEvaluationMetric[];
  summaryLines: string[];
  weakestReports: string[];
};

export type ArchiveDeliveryMetricTone = "neutral" | "sky" | "emerald" | "amber" | "rose";

export type ArchiveDeliveryMetric = {
  label: string;
  value: string;
  tone: ArchiveDeliveryMetricTone;
};

export type ArchiveDeliveryDigest = {
  title: string;
  metrics: ArchiveDeliveryMetric[];
  notes: string[];
  outstandingLabel: string;
  outstandingItems: string[];
};

export type ArchiveDeliveryScore = {
  evidenceStrength: number;
  outstandingCount: number;
  officialRatio: number;
  officialCount: number;
  totalEvidence: number;
  hasEvidenceSignal: boolean;
};

function asRecord(value: unknown): ArchiveMetadataRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as ArchiveMetadataRecord)
    : {};
}

function asPositiveNumber(value: unknown): number {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed) : 0;
}

function asStringList(value: unknown, limit = 6): string[] {
  return Array.isArray(value)
    ? value
        .map((item) => String(item || "").trim())
        .filter(Boolean)
        .filter((item, index, list) => list.indexOf(item) === index)
        .slice(0, limit)
    : [];
}

function normalizeText(value: unknown): string {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function getRecordValue(record: ArchiveMetadataRecord, ...keys: string[]): unknown {
  for (const key of keys) {
    if (key in record) {
      return record[key];
    }
  }
  return undefined;
}

function formatInlineList(values: string[], fallback = "无", limit = 4): string {
  const next = asStringList(values, limit);
  return next.length ? next.join("；") : fallback;
}

export function archiveLinkedDiffStatusLabel(status: string | null | undefined): string {
  if (status === "aligned") return "主线一致";
  if (status === "expanded") return "快照扩展";
  if (status === "trimmed") return "快照收敛";
  if (status === "mixed") return "双向差异";
  return "无法比较";
}

export function archiveDeliveryMetricToneClassName(tone: ArchiveDeliveryMetricTone): string {
  if (tone === "sky") return "bg-sky-50 text-sky-700";
  if (tone === "emerald") return "bg-emerald-50 text-emerald-700";
  if (tone === "amber") return "bg-amber-50 text-amber-700";
  if (tone === "rose") return "bg-rose-50 text-rose-700";
  return "bg-slate-100 text-slate-600";
}

export function getArchiveMetadata(archive: Pick<ApiResearchMarkdownArchive, "metadata_payload"> | null | undefined): ArchiveMetadataRecord {
  return asRecord(archive?.metadata_payload);
}

function parseOfflineMetric(value: unknown): ArchiveOfflineEvaluationMetric | null {
  const metric = asRecord(value);
  const key = normalizeText(getRecordValue(metric, "key"));
  const label = normalizeText(getRecordValue(metric, "label"));
  if (!key && !label) {
    return null;
  }
  const numerator = asPositiveNumber(getRecordValue(metric, "numerator"));
  const denominator = asPositiveNumber(getRecordValue(metric, "denominator"));
  return {
    key: key || label,
    label: label || key || "离线指标",
    percent: asPositiveNumber(getRecordValue(metric, "percent")),
    status: normalizeText(getRecordValue(metric, "status")),
    benchmark: Math.max(0, Number(getRecordValue(metric, "benchmark") || 0)),
    numerator,
    denominator,
  };
}

export function extractArchiveEvidenceSummary(
  metadataValue: unknown,
  key = "evidence_appendix_summary",
): ArchiveEvidenceSummary | null {
  const metadata = asRecord(metadataValue);
  const summary = asRecord(metadata[key]);
  if (!Object.keys(summary).length) {
    return null;
  }

  if ("changedFieldCount" in summary || "evidenceBackedFieldCount" in summary || "fieldsWithoutEvidence" in summary) {
    return {
      mode: "topic",
      changedFieldCount: asPositiveNumber(summary.changedFieldCount),
      evidenceBackedFieldCount: asPositiveNumber(summary.evidenceBackedFieldCount),
      baselineEvidenceCount: asPositiveNumber(summary.baselineEvidenceCount),
      currentEvidenceCount: asPositiveNumber(summary.currentEvidenceCount),
      officialEvidenceCount: asPositiveNumber(summary.officialEvidenceCount),
      mediaEvidenceCount: asPositiveNumber(summary.mediaEvidenceCount),
      aggregateEvidenceCount: asPositiveNumber(summary.aggregateEvidenceCount),
      fieldsWithoutEvidence: asStringList(summary.fieldsWithoutEvidence, 8),
    };
  }

  if ("directEvidenceCount" in summary || "sourceEntryCount" in summary || "uncoveredEntities" in summary) {
    return {
      mode: "compare",
      sourceEntryCount: asPositiveNumber(summary.sourceEntryCount),
      directEvidenceCount: asPositiveNumber(summary.directEvidenceCount),
      officialEvidenceCount: asPositiveNumber(summary.officialEvidenceCount),
      mediaEvidenceCount: asPositiveNumber(summary.mediaEvidenceCount),
      aggregateEvidenceCount: asPositiveNumber(summary.aggregateEvidenceCount),
      uncoveredEntities: asStringList(summary.uncoveredEntities, 8),
      officialCoverageLeaders: asStringList(summary.officialCoverageLeaders, 6),
    };
  }

  return null;
}

export function extractArchiveSectionDiagnosticsSummary(
  metadataValue: unknown,
  key = "section_diagnostics_summary",
): ArchiveSectionDiagnosticsSummary | null {
  const metadata = asRecord(metadataValue);
  const summary = asRecord(metadata[key]);
  if (!Object.keys(summary).length) {
    return null;
  }

  if ("sourceReportCount" in summary || "weakSectionCount" in summary || "source_report_count" in summary) {
    return {
      mode: "compare",
      sourceReportCount: asPositiveNumber(getRecordValue(summary, "sourceReportCount", "source_report_count")),
      weakSectionCount: asPositiveNumber(getRecordValue(summary, "weakSectionCount", "weak_section_count")),
      quotaRiskSectionCount: asPositiveNumber(getRecordValue(summary, "quotaRiskSectionCount", "quota_risk_section_count")),
      contradictionSectionCount: asPositiveNumber(
        getRecordValue(summary, "contradictionSectionCount", "contradiction_section_count"),
      ),
      highlightedSections: asStringList(getRecordValue(summary, "highlightedSections", "highlighted_sections"), 8),
    };
  }

  if (
    "currentWeakSectionCount" in summary ||
    "baselineWeakSectionCount" in summary ||
    "current_weak_section_count" in summary ||
    "baseline_weak_section_count" in summary
  ) {
    return {
      mode: "topic",
      baselineWeakSectionCount: asPositiveNumber(
        getRecordValue(summary, "baselineWeakSectionCount", "baseline_weak_section_count"),
      ),
      currentWeakSectionCount: asPositiveNumber(
        getRecordValue(summary, "currentWeakSectionCount", "current_weak_section_count"),
      ),
      newlyWeakSections: asStringList(getRecordValue(summary, "newlyWeakSections", "newly_weak_sections"), 8),
      resolvedSections: asStringList(getRecordValue(summary, "resolvedSections", "resolved_sections"), 8),
      quotaRiskSectionCount: asPositiveNumber(getRecordValue(summary, "quotaRiskSectionCount", "quota_risk_section_count")),
      contradictionSectionCount: asPositiveNumber(
        getRecordValue(summary, "contradictionSectionCount", "contradiction_section_count"),
      ),
      highlightedSections: asStringList(getRecordValue(summary, "highlightedSections", "highlighted_sections"), 8),
    };
  }

  return null;
}

export function extractArchiveOfflineEvaluationSnapshot(
  metadataValue: unknown,
  key = "offline_evaluation_snapshot",
): ArchiveOfflineEvaluationSnapshot | null {
  const metadata = asRecord(metadataValue);
  const summary = asRecord(metadata[key]);
  if (!Object.keys(summary).length) {
    return null;
  }
  const metrics = Array.isArray(getRecordValue(summary, "metrics"))
    ? (getRecordValue(summary, "metrics") as unknown[])
        .map((metric) => parseOfflineMetric(metric))
        .filter((metric): metric is ArchiveOfflineEvaluationMetric => Boolean(metric))
        .slice(0, 6)
    : [];
  const weakestReports = Array.isArray(getRecordValue(summary, "weakest_reports", "weakestReports"))
    ? (getRecordValue(summary, "weakest_reports", "weakestReports") as unknown[])
        .map((item) => {
          const record = asRecord(item);
          return normalizeText(
            getRecordValue(record, "report_title", "reportTitle", "entry_title", "entryTitle", "keyword"),
          );
        })
        .filter(Boolean)
        .slice(0, 4)
    : [];
  return {
    totalReports: asPositiveNumber(getRecordValue(summary, "total_reports", "totalReports")),
    evaluatedReports: asPositiveNumber(getRecordValue(summary, "evaluated_reports", "evaluatedReports")),
    invalidPayloads: asPositiveNumber(getRecordValue(summary, "invalid_payloads", "invalidPayloads")),
    generatedAt: normalizeText(getRecordValue(summary, "generated_at", "generatedAt")),
    metrics,
    summaryLines: asStringList(getRecordValue(summary, "summary_lines", "summaryLines"), 6),
    weakestReports,
  };
}

function buildCompareEvidenceDeltaLines(
  currentSummary: CompareArchiveEvidenceSummary,
  compareSummary: CompareArchiveEvidenceSummary,
): string[] {
  const lines: string[] = [];
  if (currentSummary.directEvidenceCount || compareSummary.directEvidenceCount) {
    lines.push(`当前直接证据 ${currentSummary.directEvidenceCount}，对照 ${compareSummary.directEvidenceCount}。`);
  }
  if (currentSummary.officialEvidenceCount || compareSummary.officialEvidenceCount) {
    lines.push(`当前官方源 ${currentSummary.officialEvidenceCount}，对照 ${compareSummary.officialEvidenceCount}。`);
  }
  if (currentSummary.uncoveredEntities.length || compareSummary.uncoveredEntities.length) {
    lines.push(
      `待补证实体：当前 ${currentSummary.uncoveredEntities.length} 个，对照 ${compareSummary.uncoveredEntities.length} 个。`,
    );
  }
  return lines;
}

function buildCompareArchiveScore(summary: CompareArchiveEvidenceSummary): ArchiveDeliveryScore {
  const totalEvidence = Math.max(summary.directEvidenceCount, summary.officialEvidenceCount + summary.mediaEvidenceCount + summary.aggregateEvidenceCount);
  return {
    evidenceStrength: summary.officialEvidenceCount * 3 + summary.directEvidenceCount + summary.sourceEntryCount * 2,
    outstandingCount: summary.uncoveredEntities.length,
    officialRatio: totalEvidence ? summary.officialEvidenceCount / totalEvidence : 0,
    officialCount: summary.officialEvidenceCount,
    totalEvidence,
    hasEvidenceSignal: totalEvidence > 0,
  };
}

function buildTopicArchiveScore(summary: TopicArchiveEvidenceSummary): ArchiveDeliveryScore {
  const totalEvidence = summary.officialEvidenceCount + summary.mediaEvidenceCount + summary.aggregateEvidenceCount;
  return {
    evidenceStrength:
      summary.evidenceBackedFieldCount * 5 +
      summary.officialEvidenceCount * 3 +
      summary.currentEvidenceCount +
      summary.baselineEvidenceCount,
    outstandingCount: summary.fieldsWithoutEvidence.length,
    officialRatio: totalEvidence ? summary.officialEvidenceCount / totalEvidence : 0,
    officialCount: summary.officialEvidenceCount,
    totalEvidence,
    hasEvidenceSignal: summary.changedFieldCount > 0 || totalEvidence > 0,
  };
}

function mergeArchiveScores(scores: ArchiveDeliveryScore[]): ArchiveDeliveryScore {
  const valid = scores.filter((score) => score.hasEvidenceSignal);
  if (!valid.length) {
    return {
      evidenceStrength: 0,
      outstandingCount: 0,
      officialRatio: 0,
      officialCount: 0,
      totalEvidence: 0,
      hasEvidenceSignal: false,
    };
  }
  const totalStrength = valid.reduce((sum, score) => sum + score.evidenceStrength, 0);
  const totalOfficialRatio = valid.reduce((sum, score) => sum + score.officialRatio, 0);
  const totalOfficialCount = valid.reduce((sum, score) => sum + score.officialCount, 0);
  const totalEvidence = valid.reduce((sum, score) => sum + score.totalEvidence, 0);
  return {
    evidenceStrength: Math.round(totalStrength / valid.length),
    outstandingCount: Math.max(...valid.map((score) => score.outstandingCount)),
    officialRatio: totalOfficialRatio / valid.length,
    officialCount: totalOfficialCount,
    totalEvidence,
    hasEvidenceSignal: true,
  };
}

function buildTopicEvidenceDeltaLines(
  currentSummary: TopicArchiveEvidenceSummary,
  compareSummary: TopicArchiveEvidenceSummary,
): string[] {
  const lines: string[] = [];
  if (currentSummary.changedFieldCount || compareSummary.changedFieldCount) {
    lines.push(
      `当前证据支撑字段 ${currentSummary.evidenceBackedFieldCount}/${Math.max(currentSummary.changedFieldCount, 1)}，对照 ${compareSummary.evidenceBackedFieldCount}/${Math.max(compareSummary.changedFieldCount, 1)}。`,
    );
  }
  if (currentSummary.officialEvidenceCount || compareSummary.officialEvidenceCount) {
    lines.push(`当前官方源 ${currentSummary.officialEvidenceCount}，对照 ${compareSummary.officialEvidenceCount}。`);
  }
  if (currentSummary.fieldsWithoutEvidence.length || compareSummary.fieldsWithoutEvidence.length) {
    lines.push(
      `待补证字段：当前 ${currentSummary.fieldsWithoutEvidence.length} 个，对照 ${compareSummary.fieldsWithoutEvidence.length} 个。`,
    );
  }
  return lines;
}

function buildCompareSectionDiagnosticsDeltaLines(
  currentSummary: CompareArchiveSectionDiagnosticsSummary,
  compareSummary: CompareArchiveSectionDiagnosticsSummary,
): string[] {
  const lines: string[] = [];
  if (currentSummary.weakSectionCount || compareSummary.weakSectionCount) {
    lines.push(`待补证章节：当前 ${currentSummary.weakSectionCount} 个，对照 ${compareSummary.weakSectionCount} 个。`);
  }
  if (currentSummary.quotaRiskSectionCount || compareSummary.quotaRiskSectionCount) {
    lines.push(
      `配额未达标章节：当前 ${currentSummary.quotaRiskSectionCount} 个，对照 ${compareSummary.quotaRiskSectionCount} 个。`,
    );
  }
  if (currentSummary.contradictionSectionCount || compareSummary.contradictionSectionCount) {
    lines.push(
      `章节矛盾信号：当前 ${currentSummary.contradictionSectionCount} 个，对照 ${compareSummary.contradictionSectionCount} 个。`,
    );
  }
  return lines;
}

function buildTopicSectionDiagnosticsDeltaLines(
  currentSummary: TopicArchiveSectionDiagnosticsSummary,
  compareSummary: TopicArchiveSectionDiagnosticsSummary,
): string[] {
  const lines: string[] = [];
  if (currentSummary.currentWeakSectionCount || compareSummary.currentWeakSectionCount) {
    lines.push(
      `当前版本待补证章节：当前 ${currentSummary.currentWeakSectionCount} 个，对照 ${compareSummary.currentWeakSectionCount} 个。`,
    );
  }
  if (currentSummary.quotaRiskSectionCount || compareSummary.quotaRiskSectionCount) {
    lines.push(
      `配额未达标章节：当前 ${currentSummary.quotaRiskSectionCount} 个，对照 ${compareSummary.quotaRiskSectionCount} 个。`,
    );
  }
  if (currentSummary.contradictionSectionCount || compareSummary.contradictionSectionCount) {
    lines.push(
      `章节矛盾信号：当前 ${currentSummary.contradictionSectionCount} 个，对照 ${compareSummary.contradictionSectionCount} 个。`,
    );
  }
  return lines;
}

function offlineStatusLabel(status: string): string {
  if (status === "good") return "达标";
  if (status === "watch") return "观察";
  return "偏弱";
}

function buildOfflineEvaluationDeltaLines(
  currentSnapshot: ArchiveOfflineEvaluationSnapshot,
  compareSnapshot: ArchiveOfflineEvaluationSnapshot,
): string[] {
  const lines: string[] = [];
  const compareMetricMap = new Map(compareSnapshot.metrics.map((metric) => [metric.key, metric]));
  currentSnapshot.metrics.forEach((metric) => {
    const compareMetric = compareMetricMap.get(metric.key);
    if (!compareMetric) {
      return;
    }
    lines.push(
      `${metric.label}：当前 ${metric.percent}%（${offlineStatusLabel(metric.status)}），对照 ${compareMetric.percent}%（${offlineStatusLabel(compareMetric.status)}）。`,
    );
  });
  if (currentSnapshot.invalidPayloads || compareSnapshot.invalidPayloads) {
    lines.push(`schema 异常：当前 ${currentSnapshot.invalidPayloads} 份，对照 ${compareSnapshot.invalidPayloads} 份。`);
  }
  return lines.slice(0, 4);
}

export function buildArchiveEvidenceDeltaLines(
  currentArchive: Pick<ApiResearchMarkdownArchive, "metadata_payload"> | null | undefined,
  compareArchive: Pick<ApiResearchMarkdownArchive, "metadata_payload"> | null | undefined,
): string[] {
  const currentSummary = extractArchiveEvidenceSummary(getArchiveMetadata(currentArchive));
  const compareSummary = extractArchiveEvidenceSummary(getArchiveMetadata(compareArchive));
  if (!currentSummary || !compareSummary || currentSummary.mode !== compareSummary.mode) {
    return [];
  }
  if (currentSummary.mode === "compare" && compareSummary.mode === "compare") {
    return buildCompareEvidenceDeltaLines(currentSummary, compareSummary);
  }
  if (currentSummary.mode === "topic" && compareSummary.mode === "topic") {
    return buildTopicEvidenceDeltaLines(currentSummary, compareSummary);
  }
  return [];
}

export function buildArchiveSectionDiagnosticsDeltaLines(
  currentArchive: Pick<ApiResearchMarkdownArchive, "metadata_payload"> | null | undefined,
  compareArchive: Pick<ApiResearchMarkdownArchive, "metadata_payload"> | null | undefined,
): string[] {
  const currentSummary = extractArchiveSectionDiagnosticsSummary(getArchiveMetadata(currentArchive));
  const compareSummary = extractArchiveSectionDiagnosticsSummary(getArchiveMetadata(compareArchive));
  if (!currentSummary || !compareSummary || currentSummary.mode !== compareSummary.mode) {
    return [];
  }
  if (currentSummary.mode === "compare" && compareSummary.mode === "compare") {
    return buildCompareSectionDiagnosticsDeltaLines(currentSummary, compareSummary);
  }
  if (currentSummary.mode === "topic" && compareSummary.mode === "topic") {
    return buildTopicSectionDiagnosticsDeltaLines(currentSummary, compareSummary);
  }
  return [];
}

export function buildArchiveOfflineEvaluationDeltaLines(
  currentArchive: Pick<ApiResearchMarkdownArchive, "metadata_payload"> | null | undefined,
  compareArchive: Pick<ApiResearchMarkdownArchive, "metadata_payload"> | null | undefined,
): string[] {
  const currentSnapshot = extractArchiveOfflineEvaluationSnapshot(getArchiveMetadata(currentArchive));
  const compareSnapshot = extractArchiveOfflineEvaluationSnapshot(getArchiveMetadata(compareArchive));
  if (!currentSnapshot || !compareSnapshot) {
    return [];
  }
  return buildOfflineEvaluationDeltaLines(currentSnapshot, compareSnapshot);
}

export function buildArchiveDeliveryDigest(
  archive: Pick<ApiResearchMarkdownArchive, "archive_kind" | "metadata_payload">,
  sourcePrefix?: "current" | "compare",
): ArchiveDeliveryDigest | null {
  const metadata = getArchiveMetadata(archive);
  const evidenceKey = sourcePrefix ? `${sourcePrefix}_evidence_appendix_summary` : "evidence_appendix_summary";
  const summary = extractArchiveEvidenceSummary(metadata, evidenceKey);
  const sectionKey = sourcePrefix ? `${sourcePrefix}_section_diagnostics_summary` : "section_diagnostics_summary";
  const sectionSummary = extractArchiveSectionDiagnosticsSummary(metadata, sectionKey);
  const offlineKey = sourcePrefix ? `${sourcePrefix}_offline_evaluation_snapshot` : "offline_evaluation_snapshot";
  const offlineSnapshot = extractArchiveOfflineEvaluationSnapshot(metadata, offlineKey);

  if (summary?.mode === "compare") {
    const linkedDiffStatus = normalizeText(
      metadata[sourcePrefix ? `${sourcePrefix}_linked_report_diff_status` : "linked_report_diff_status"],
    );
    return {
      title: sourcePrefix === "compare" ? "对照归档证据" : sourcePrefix === "current" ? "当前归档证据" : "Evidence Appendix",
      metrics: [
        { label: "直接证据", value: String(summary.directEvidenceCount), tone: "sky" },
        { label: "官方源", value: String(summary.officialEvidenceCount), tone: "emerald" },
        { label: "来源研报", value: String(summary.sourceEntryCount), tone: "neutral" },
        ...(sectionSummary?.mode === "compare"
          ? [{ label: "待补证章节", value: String(sectionSummary.weakSectionCount), tone: "amber" as const }]
          : []),
      ],
      notes: [
        linkedDiffStatus ? `关联版本差异: ${archiveLinkedDiffStatusLabel(linkedDiffStatus)}` : "",
        summary.officialCoverageLeaders.length
          ? `官方补证命中最高: ${formatInlineList(summary.officialCoverageLeaders, "无", 3)}`
          : "",
        sectionSummary?.mode === "compare"
          ? `章节诊断: 配额风险 ${sectionSummary.quotaRiskSectionCount} / 矛盾 ${sectionSummary.contradictionSectionCount}`
          : "",
        offlineSnapshot?.metrics.length
          ? `离线回归: ${offlineSnapshot.metrics
              .slice(0, 3)
              .map((metric) => `${metric.label} ${metric.percent}%`)
              .join(" / ")}`
          : "",
      ].filter(Boolean),
      outstandingLabel: "待补证实体",
      outstandingItems: summary.uncoveredEntities,
    };
  }

  if (summary?.mode === "topic") {
    return {
      title: sourcePrefix === "compare" ? "对照归档证据" : sourcePrefix === "current" ? "当前归档证据" : "Evidence Appendix",
      metrics: [
        { label: "变更字段", value: String(summary.changedFieldCount), tone: "amber" },
        {
          label: "证据支撑",
          value: `${summary.evidenceBackedFieldCount}/${Math.max(summary.changedFieldCount, 1)}`,
          tone: "emerald",
        },
        { label: "官方源", value: String(summary.officialEvidenceCount), tone: "sky" },
        ...(sectionSummary?.mode === "topic"
          ? [{ label: "待补证章节", value: String(sectionSummary.currentWeakSectionCount), tone: "amber" as const }]
          : []),
      ],
      notes: [
        `基线证据 ${summary.baselineEvidenceCount} / 对照证据 ${summary.currentEvidenceCount}`,
        `证据结构: 媒体源 ${summary.mediaEvidenceCount} / 聚合源 ${summary.aggregateEvidenceCount}`,
        sectionSummary?.mode === "topic"
          ? `章节诊断: 新增待补证 ${sectionSummary.newlyWeakSections.length} / 已解决 ${sectionSummary.resolvedSections.length}`
          : "",
        offlineSnapshot?.metrics.length
          ? `离线回归: ${offlineSnapshot.metrics
              .slice(0, 3)
              .map((metric) => `${metric.label} ${metric.percent}%`)
              .join(" / ")}`
          : "",
      ],
      outstandingLabel: "待补证字段",
      outstandingItems: summary.fieldsWithoutEvidence,
    };
  }

  if (archive.archive_kind === "archive_diff_recap") {
    const currentSummary = extractArchiveEvidenceSummary(metadata, "current_evidence_appendix_summary");
    const compareSummary = extractArchiveEvidenceSummary(metadata, "compare_evidence_appendix_summary");
    const currentSectionSummary = extractArchiveSectionDiagnosticsSummary(metadata, "current_section_diagnostics_summary");
    const compareSectionSummary = extractArchiveSectionDiagnosticsSummary(metadata, "compare_section_diagnostics_summary");
    const currentOfflineSnapshot = extractArchiveOfflineEvaluationSnapshot(metadata, "current_offline_evaluation_snapshot");
    const compareOfflineSnapshot = extractArchiveOfflineEvaluationSnapshot(metadata, "compare_offline_evaluation_snapshot");
    const changedSectionCount = asPositiveNumber(metadata.changed_section_count);
    const addedSectionCount = asPositiveNumber(metadata.added_section_count);
    const removedSectionCount = asPositiveNumber(metadata.removed_section_count);
    return {
      title: "Archive Diff Signals",
      metrics: [
        { label: "变更 section", value: String(changedSectionCount), tone: "amber" },
        { label: "当前新增", value: String(addedSectionCount), tone: "emerald" },
        { label: "对照独有", value: String(removedSectionCount), tone: "rose" },
      ],
      notes: [
        ...(
          currentSummary && compareSummary
            ? currentSummary.mode === "compare" && compareSummary.mode === "compare"
              ? buildCompareEvidenceDeltaLines(currentSummary, compareSummary)
              : currentSummary.mode === "topic" && compareSummary.mode === "topic"
                ? buildTopicEvidenceDeltaLines(currentSummary, compareSummary)
                : []
            : []
        ),
        ...(
          currentSectionSummary && compareSectionSummary
            ? currentSectionSummary.mode === "compare" && compareSectionSummary.mode === "compare"
              ? buildCompareSectionDiagnosticsDeltaLines(currentSectionSummary, compareSectionSummary)
              : currentSectionSummary.mode === "topic" && compareSectionSummary.mode === "topic"
                ? buildTopicSectionDiagnosticsDeltaLines(currentSectionSummary, compareSectionSummary)
                : []
            : []
        ),
        ...(
          currentOfflineSnapshot && compareOfflineSnapshot
            ? buildOfflineEvaluationDeltaLines(currentOfflineSnapshot, compareOfflineSnapshot)
            : []
        ),
      ],
      outstandingLabel: "",
      outstandingItems: [],
    };
  }

  return null;
}

export function buildArchiveDeliveryScore(
  archive: Pick<ApiResearchMarkdownArchive, "archive_kind" | "metadata_payload">,
): ArchiveDeliveryScore {
  const metadata = getArchiveMetadata(archive);
  const summary = extractArchiveEvidenceSummary(metadata);

  if (summary?.mode === "compare") {
    return buildCompareArchiveScore(summary);
  }
  if (summary?.mode === "topic") {
    return buildTopicArchiveScore(summary);
  }
  if (archive.archive_kind === "archive_diff_recap") {
    const currentSummary = extractArchiveEvidenceSummary(metadata, "current_evidence_appendix_summary");
    const compareSummary = extractArchiveEvidenceSummary(metadata, "compare_evidence_appendix_summary");
    const scores = [
      currentSummary?.mode === "compare"
        ? buildCompareArchiveScore(currentSummary)
        : currentSummary?.mode === "topic"
          ? buildTopicArchiveScore(currentSummary)
          : null,
      compareSummary?.mode === "compare"
        ? buildCompareArchiveScore(compareSummary)
        : compareSummary?.mode === "topic"
          ? buildTopicArchiveScore(compareSummary)
          : null,
    ].filter((score): score is ArchiveDeliveryScore => Boolean(score));
    return mergeArchiveScores(scores);
  }
  return {
    evidenceStrength: 0,
    outstandingCount: 0,
    officialRatio: 0,
    officialCount: 0,
    totalEvidence: 0,
    hasEvidenceSignal: false,
  };
}
