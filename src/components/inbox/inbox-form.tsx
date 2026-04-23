"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiResearchJob,
  ApiKnowledgeEntry,
  ApiResearchReport,
  createItem,
  createItemsBatch,
  createResearchActionPlan,
  createResearchConversation,
  createResearchJob,
  createTask,
  getResearchJob,
  listKnowledgeEntries,
  saveResearchActionCards,
  saveResearchReport,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { LegacyResearchProgressCard } from "@/components/inbox/legacy-research-progress-card";
import { ResearchHistoryList } from "@/components/inbox/research-history-list";
import { ResearchReportCard } from "@/components/inbox/research-report-card";
import { MultiFormatImportPanel } from "@/components/inbox/multiformat-import-panel";
import { ResearchActionCardsPanel } from "@/components/research/research-action-cards-panel";
import { dedupeByKey, dedupeTextList } from "@/lib/display-list";
import { getGuardedRewriteReasonLabels, isGuardedBacklog } from "@/lib/research-diagnostics";
import { normalizeResearchActionCards, type UiResearchActionCard } from "@/lib/research-action-cards";

type ResearchMode = "fast" | "deep";
type ResearchPipelineKey = "fetch" | "clean" | "analyze";
type ResearchPipelineStatus = "done" | "active" | "pending";
type ResearchFormalExportFormat =
  | ""
  | "feasibility_word"
  | "feasibility_pdf"
  | "proposal_word"
  | "proposal_pdf";
type ResearchDeliverySupplement = {
  project_name: string;
  project_owner: string;
  project_region: string;
  implementation_window: string;
  investment_estimate: string;
  construction_basis: string;
  scope_statement: string;
  expected_benefits: string;
  cross_validation_notes: string;
  supplemental_context: string;
  supplemental_evidence: string;
  supplemental_requirements: string;
};

function buildResearchDeliverySupplement(report: ApiResearchReport): ResearchDeliverySupplement {
  return {
    project_name: report.report_title || report.keyword,
    project_owner: report.top_target_accounts?.[0]?.name || report.target_accounts?.[0] || "",
    project_region: report.source_diagnostics?.scope_regions?.join(" / ") || "",
    implementation_window: report.tender_timeline?.[0] || "",
    investment_estimate: report.budget_signals?.[0] || "",
    construction_basis: "",
    scope_statement: report.strategic_directions?.[0] || report.project_distribution?.[0] || "",
    expected_benefits: report.five_year_outlook?.[0] || report.competition_analysis?.[0] || "",
    cross_validation_notes: report.followup_context?.supplemental_evidence || "",
    supplemental_context: report.followup_context?.supplemental_context || "",
    supplemental_evidence: report.followup_context?.supplemental_evidence || "",
    supplemental_requirements: report.followup_context?.supplemental_requirements || report.research_focus || "",
  };
}

function buildResearchKeywordGroups(keyword: string, researchFocus?: string | null): string[] {
  const groups = [String(keyword || "").trim()]
    .concat(
      String(researchFocus || "")
        .split(/[，,、/｜|；;\n\s]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    )
    .filter(Boolean);
  return Array.from(new Set(groups)).slice(0, 4);
}

function buildResearchModeConfig(mode: ResearchMode) {
  if (mode === "fast") {
    return {
      research_mode: "fast" as const,
      deep_research: false,
      max_sources: 8,
      estimatedMinutes: 3,
    };
  }
  return {
    research_mode: "deep" as const,
    deep_research: true,
    max_sources: 18,
    estimatedMinutes: 6,
  };
}

function qualityLabel(value: string) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

function classifyResearchSourceTier(source: ApiResearchReport["sources"][number]): "official" | "media" | "aggregate" {
  const domain = String(source.domain || "").toLowerCase();
  const sourceType = String(source.source_type || "").toLowerCase();
  const sourceTier = String(source.source_tier || "").toLowerCase();
  if (sourceTier === "official" || sourceTier === "media" || sourceTier === "aggregate") {
    return sourceTier;
  }
  if (
    sourceType === "policy" ||
    sourceType === "procurement" ||
    sourceType === "filing" ||
    domain.endsWith(".gov.cn") ||
    domain.includes("gov.cn") ||
    domain.includes("ggzy.gov.cn") ||
    domain.includes("cninfo.com.cn") ||
    domain.includes("sec.gov") ||
    domain.includes("hkexnews.hk")
  ) {
    return "official";
  }
  if (
    sourceType === "tender_feed" ||
    domain.includes("jianyu") ||
    domain.includes("cecbid") ||
    domain.includes("cebpubservice") ||
    domain.includes("china-cpp") ||
    domain.includes("chinabidding")
  ) {
    return "aggregate";
  }
  return "media";
}

function sourceTierLabel(value: string) {
  if (value === "official") return "官方源";
  if (value === "aggregate") return "聚合源";
  return "媒体源";
}

function mapResearchStageToPipelineKey(stageKey?: string | null): ResearchPipelineKey {
  const normalized = String(stageKey || "").toLowerCase();
  if (
    normalized === "extracting" ||
    normalized === "scoping" ||
    normalized === "company_contacts" ||
    normalized === "expanding" ||
    normalized === "corrective"
  ) {
    return "clean";
  }
  if (
    normalized === "synthesizing" ||
    normalized === "ranking" ||
    normalized === "packaging" ||
    normalized === "completed"
  ) {
    return "analyze";
  }
  return "fetch";
}

function defaultResearchPipelineSummary(key: ResearchPipelineKey) {
  if (key === "fetch") {
    return "汇总定向源、公开网页和公众号候选结果。";
  }
  if (key === "clean") {
    return "抽取正文、去重、筛掉越界来源并做纠错补证。";
  }
  return "综合证据、排序公司与伙伴，并整理结构化结论。";
}

export function InboxForm() {
  const { preferences, t } = useAppPreferences();
  const [url, setUrl] = useState("");
  const [batchUrls, setBatchUrls] = useState("");
  const [rawText, setRawText] = useState("");
  const [researchKeyword, setResearchKeyword] = useState("");
  const [researchFocus, setResearchFocus] = useState("");
  const [researchMode, setResearchMode] = useState<ResearchMode>("deep");
  const [researchHistory, setResearchHistory] = useState<ApiKnowledgeEntry[]>([]);
  const [researchReport, setResearchReport] = useState<ApiResearchReport | null>(null);
  const [researchJob, setResearchJob] = useState<ApiResearchJob | null>(null);
  const [researchActionCards, setResearchActionCards] = useState<UiResearchActionCard[]>([]);
  const [savedResearchEntryId, setSavedResearchEntryId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [researchError, setResearchError] = useState("");
  const [researchMessage, setResearchMessage] = useState("");
  const [batchMessage, setBatchMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [researching, setResearching] = useState(false);
  const [savingResearch, setSavingResearch] = useState(false);
  const [savingResearchAsFocus, setSavingResearchAsFocus] = useState(false);
  const [exportingResearchFormat, setExportingResearchFormat] = useState<"" | "markdown" | "word" | "pdf">("");
  const [followupResearchFocus, setFollowupResearchFocus] = useState("");
  const [deliverySupplement, setDeliverySupplement] = useState<ResearchDeliverySupplement>({
    project_name: "",
    project_owner: "",
    project_region: "",
    implementation_window: "",
    investment_estimate: "",
    construction_basis: "",
    scope_statement: "",
    expected_benefits: "",
    cross_validation_notes: "",
    supplemental_context: "",
    supplemental_evidence: "",
    supplemental_requirements: "",
  });
  const [exportingFormalDocument, setExportingFormalDocument] = useState<ResearchFormalExportFormat>("");
  const [planningResearchActions, setPlanningResearchActions] = useState(false);
  const [savingResearchActions, setSavingResearchActions] = useState(false);
  const [seededConversationJobId, setSeededConversationJobId] = useState("");
  const researchDiagnostics = researchReport?.source_diagnostics || null;
  const guardedReasonLabels = dedupeTextList(
    researchDiagnostics ? getGuardedRewriteReasonLabels(researchDiagnostics) : [],
  );
  const followupDiagnostics = researchReport?.followup_diagnostics || null;
  const followupFilters = dedupeTextList([
    ...(followupDiagnostics?.rebuilt_regions || []),
    ...(followupDiagnostics?.rebuilt_industries || []),
    ...(followupDiagnostics?.rebuilt_clients || []),
  ]);
  const supportedTargetAccounts = dedupeTextList(researchDiagnostics?.supported_target_accounts || []);
  const unsupportedTargetAccounts = dedupeTextList(researchDiagnostics?.unsupported_target_accounts || []);
  const enabledSourceLabels = dedupeTextList(researchDiagnostics?.enabled_source_labels || []);
  const matchedSourceLabels = dedupeTextList(researchDiagnostics?.matched_source_labels || []);
  const topicAnchorTerms = dedupeTextList(researchDiagnostics?.topic_anchor_terms || []);
  const matchedThemeLabels = dedupeTextList(researchDiagnostics?.matched_theme_labels || []);
  const coreEntities = dedupeByKey(
    researchReport?.entity_graph?.entities || [],
    (entity) => String(entity?.canonical_name || "").trim(),
    6,
  );

  useEffect(() => {
    if (!researchJob?.id || !researching) {
      return undefined;
    }

    let cancelled = false;
    let failureCount = 0;
    const poll = async () => {
      try {
        const job = await getResearchJob(researchJob.id);
        if (cancelled) return;
        failureCount = 0;
        setResearchJob(job);
        if (job.report) {
          setResearchReport(job.report);
        }
        if (job.status === "succeeded" && job.report) {
          setResearching(false);
          setResearchMessage(t("inbox.researchCompleted", "研报已生成，可继续保存、导出或生成行动卡。"));
          return;
        }
        if (job.status === "failed") {
          setResearching(false);
          setResearchError(job.error || t("inbox.error.researchFailed", "关键词研究失败，请稍后重试。"));
          return;
        }
        window.setTimeout(() => {
          void poll();
        }, 1800);
      } catch {
        if (cancelled) return;
        failureCount += 1;
        if (failureCount < 4) {
          window.setTimeout(() => {
            void poll();
          }, 2200);
          return;
        }
        setResearching(false);
        setResearchError(
          t(
            "inbox.error.researchBackendUnavailable",
            "后端研究服务暂不可用：当前前端无法继续轮询研报任务，请检查 API 是否运行。",
          ),
        );
      }
    };

    void poll();
    return () => {
      cancelled = true;
    };
  }, [researchJob?.id, researching, t]);

  useEffect(() => {
    if (!researchJob?.id || !researchJob.report || researchJob.status !== "succeeded") {
      return undefined;
    }
    if (seededConversationJobId === researchJob.id) {
      return undefined;
    }
    let cancelled = false;
    createResearchConversation({
      title: `${researchJob.keyword}${t("research.consoleConversationSuffix", " 继续追问")}`,
      job_id: researchJob.id,
    })
      .then(() => {
        if (!cancelled) {
          setSeededConversationJobId(researchJob.id);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSeededConversationJobId(researchJob.id);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [researchJob, seededConversationJobId, t]);

  useEffect(() => {
    if (!researchReport) {
      return;
    }
    setFollowupResearchFocus(researchReport.research_focus || researchReport.followup_context?.supplemental_requirements || "");
    setDeliverySupplement(buildResearchDeliverySupplement(researchReport));
  }, [researchReport]);

  useEffect(() => {
    const refreshResearchHistory = async () => {
      try {
        const response = await listKnowledgeEntries(6, {
          sourceDomain: "research.report",
        });
        setResearchHistory(response.items);
      } catch {
        setResearchHistory([]);
      }
    };

    void refreshResearchHistory();
  }, []);

  const submitUrl = async () => {
    if (!url.trim()) {
      setError(t("inbox.error.enterUrl", "请先输入 URL。"));
      return;
    }

    setError("");
    setSubmitting(true);
    try {
      await createItem({
        source_type: "url",
        source_url: url.trim(),
        output_language: preferences.language,
      });
      setUrl("");
    } catch {
      setError(t("inbox.error.submitFailed", "提交失败，请检查后端服务是否启动。"));
    } finally {
      setSubmitting(false);
    }
  };

  const submitText = async () => {
    if (!rawText.trim()) {
      setError(t("inbox.error.enterText", "请先输入文本内容。"));
      return;
    }

    setError("");
    setSubmitting(true);
    try {
      await createItem({
        source_type: "text",
        raw_content: rawText.trim(),
        title: rawText.trim().slice(0, 24),
        output_language: preferences.language,
      });
      setRawText("");
    } catch {
      setError(t("inbox.error.submitFailed", "提交失败，请检查后端服务是否启动。"));
    } finally {
      setSubmitting(false);
    }
  };

  const submitBatchUrls = async () => {
    const urls = batchUrls
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    if (urls.length === 0) {
      setError(t("inbox.error.enterBatch", "请先输入批量 URL（每行一个）。"));
      return;
    }

    setError("");
    setBatchMessage("");
    setSubmitting(true);
    try {
      const result = await createItemsBatch({
        source_type: "url",
        urls,
        deduplicate: true,
        output_language: preferences.language,
      });

      setBatchMessage(
        `${t("inbox.batchResult", "批量提交完成")}：${t("inbox.batchTotal", "总计")} ${
          result.total
        }，${t("inbox.batchCreated", "创建")} ${result.created}，${t(
          "inbox.batchSkipped",
          "跳过",
        )} ${result.skipped}，${t("inbox.batchInvalid", "无效")} ${result.invalid}。`,
      );
      setBatchUrls("");
    } catch {
      setError(t("inbox.error.batchFailed", "批量提交失败，请检查后端服务是否启动。"));
    } finally {
      setSubmitting(false);
    }
  };

  const updateDeliverySupplementField = <K extends keyof ResearchDeliverySupplement>(
    key: K,
    value: ResearchDeliverySupplement[K],
  ) => {
    setDeliverySupplement((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const submitResearch = async (options?: {
    keyword?: string;
    researchFocus?: string;
    followupReportTitle?: string;
    followupReportSummary?: string;
    supplementalContext?: string;
    supplementalEvidence?: string;
    supplementalRequirements?: string;
    queuedMessage?: string;
  }) => {
    const nextKeyword = String(options?.keyword ?? researchKeyword).trim();
    const nextResearchFocus = String(options?.researchFocus ?? researchFocus).trim();
    const nextSupplementalContext = String(options?.supplementalContext ?? "").trim();
    const nextSupplementalEvidence = String(options?.supplementalEvidence ?? "").trim();
    const nextSupplementalRequirements = String(options?.supplementalRequirements ?? "").trim();
    if (!nextKeyword) {
      setResearchError(t("inbox.error.enterKeyword", "请先输入关键词。"));
      return;
    }

    setResearchError("");
    setResearchMessage("");
    setSavedResearchEntryId(null);
    setResearchActionCards([]);
    setResearchReport(null);
    setSeededConversationJobId("");
    setResearching(true);
    const modeConfig = buildResearchModeConfig(researchMode);
    try {
      const job = await createResearchJob({
        keyword: nextKeyword,
        research_focus: nextResearchFocus || undefined,
        followup_report_title: String(options?.followupReportTitle || "").trim() || undefined,
        followup_report_summary: String(options?.followupReportSummary || "").trim() || undefined,
        supplemental_context: nextSupplementalContext || undefined,
        supplemental_evidence: nextSupplementalEvidence || undefined,
        supplemental_requirements: nextSupplementalRequirements || undefined,
        output_language: preferences.language,
        include_wechat: true,
        max_sources: modeConfig.max_sources,
        deep_research: modeConfig.deep_research,
        research_mode: modeConfig.research_mode,
      });
      setResearchJob(job);
      setResearchMessage(
        options?.queuedMessage ||
          (researchMode === "deep"
            ? t("inbox.researchQueuedDeep", "已启动深度研究任务，正在持续汇总多源信息。")
            : t("inbox.researchQueuedFast", "已启动极速研究任务，优先汇总高信号来源。")),
      );
    } catch {
      setResearching(false);
      setResearchError(
        t(
          "inbox.error.researchBackendUnavailable",
          "后端研究服务暂不可用：当前前端无法创建研报任务，请检查 API 是否运行。",
        ),
      );
    } finally {
      // 进入轮询后由 job 状态结束 researching。
    }
  };

  const triggerFileDownload = (filename: string, content: BlobPart, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const downloadResearchTask = (task: Awaited<ReturnType<typeof createTask>>) => {
    const filename =
      typeof task.output_payload?.filename === "string"
        ? task.output_payload.filename
        : `${researchReport?.report_title || researchReport?.keyword || "research-report"}.md`;
    const mimeType =
      typeof task.output_payload?.mime_type === "string"
        ? task.output_payload.mime_type
        : String(task.output_payload?.format || "") === "word"
          ? "application/msword"
          : String(task.output_payload?.format || "") === "pdf"
            ? "application/pdf"
            : "text/markdown;charset=utf-8";
    const base64 = typeof task.output_payload?.content_base64 === "string" ? task.output_payload.content_base64 : "";
    const content = String(task.output_payload?.content || "");
    if (base64) {
      const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
      triggerFileDownload(filename, bytes, mimeType);
      return;
    }
    if (!content) {
      throw new Error("empty export content");
    }
    triggerFileDownload(filename, content, mimeType);
  };

  const saveCurrentResearch = async (asFocusReference = false) => {
    if (!researchReport) return;
    if (asFocusReference) {
      setSavingResearchAsFocus(true);
    } else {
      setSavingResearch(true);
    }
    setResearchMessage("");
    try {
      const result = await saveResearchReport({
        report: researchReport,
        collection_name: "关键词研报",
        is_focus_reference: asFocusReference,
      });
      setSavedResearchEntryId(result.entry_id);
      try {
        const response = await listKnowledgeEntries(6, {
          sourceDomain: "research.report",
        });
        setResearchHistory(response.items);
      } catch {
        // 保持当前页面可用
      }
      setResearchMessage(
        asFocusReference
          ? t("inbox.researchSavedToFocus", "研究报告已加入 Focus 参考")
          : t("inbox.researchSaved", "研究报告已加入知识库"),
      );
    } catch {
      setResearchMessage(
        asFocusReference
          ? t("inbox.researchSaveFocusFailed", "加入 Focus 参考失败，请稍后重试")
          : t("inbox.researchSaveFailed", "保存到知识库失败，请稍后重试"),
      );
    } finally {
      if (asFocusReference) {
        setSavingResearchAsFocus(false);
      } else {
        setSavingResearch(false);
      }
    }
  };

  const exportCurrentResearch = async (format: "markdown" | "word" | "pdf") => {
    if (!researchReport) return;
    setExportingResearchFormat(format);
    setResearchMessage("");
    try {
      const taskType =
        format === "word"
          ? "export_research_report_word"
          : format === "pdf"
            ? "export_research_report_pdf"
            : "export_research_report_markdown";
      const task = await createTask({
        task_type: taskType,
        input_payload: {
          report: researchReport,
          output_language: preferences.language,
        },
      });
      downloadResearchTask(task);
      setResearchMessage(
        format === "word"
          ? t("inbox.researchExportedWord", "研究报告 Word 已导出")
          : format === "pdf"
            ? t("inbox.researchExportedPdf", "研究报告 PDF 已导出")
            : t("inbox.researchExported", "研究报告 Markdown 已导出"),
      );
    } catch {
      setResearchMessage(
        format === "word"
          ? t("inbox.researchExportWordFailed", "导出 Word 失败，请稍后重试")
          : format === "pdf"
            ? t("inbox.researchExportPdfFailed", "导出 PDF 失败，请稍后重试")
            : t("inbox.researchExportFailed", "导出 Markdown 失败，请稍后重试"),
      );
    } finally {
      setExportingResearchFormat("");
    }
  };

  const exportFormalResearchDocument = async (format: Exclude<ResearchFormalExportFormat, "">) => {
    if (!researchReport) return;
    setExportingFormalDocument(format);
    setResearchMessage("");
    const taskType =
      format === "feasibility_word"
        ? "export_feasibility_study_word"
        : format === "feasibility_pdf"
          ? "export_feasibility_study_pdf"
          : format === "proposal_word"
            ? "export_project_proposal_word"
            : "export_project_proposal_pdf";
    try {
      const task = await createTask({
        task_type: taskType,
        input_payload: {
          report: researchReport,
          output_language: preferences.language,
          delivery_supplement: deliverySupplement,
        },
      });
      downloadResearchTask(task);
      setResearchMessage(
        format === "feasibility_word"
          ? "可行性研究报告 Word 已导出"
          : format === "feasibility_pdf"
            ? "可行性研究报告 PDF 已导出"
            : format === "proposal_word"
              ? "项目建议书 Word 已导出"
              : "项目建议书 PDF 已导出",
      );
    } catch {
      setResearchMessage(
        format === "feasibility_word"
          ? "导出可行性研究报告 Word 失败，请稍后重试"
          : format === "feasibility_pdf"
            ? "导出可行性研究报告 PDF 失败，请稍后重试"
            : format === "proposal_word"
              ? "导出项目建议书 Word 失败，请稍后重试"
              : "导出项目建议书 PDF 失败，请稍后重试",
      );
    } finally {
      setExportingFormalDocument("");
    }
  };

  const planResearchActions = async () => {
    if (!researchReport) return;
    setPlanningResearchActions(true);
    setResearchMessage("");
    try {
      const result = await createResearchActionPlan({
        report: researchReport,
      });
      setResearchActionCards(normalizeResearchActionCards(result.cards || [], t));
      setResearchMessage(
        result.cards?.length
          ? t("research.actionsPlanned", "已生成研报行动卡")
          : t("research.actionsEmpty", "当前研报暂未生成可执行行动卡"),
      );
    } catch {
      setResearchMessage(t("research.actionsPlanFailed", "生成行动卡失败，请稍后重试"));
    } finally {
      setPlanningResearchActions(false);
    }
  };

  const saveCurrentResearchActions = async (asFocusReference = false) => {
    if (!researchReport || researchActionCards.length === 0) return;
    setSavingResearchActions(true);
    setResearchMessage("");
    try {
      const result = await saveResearchActionCards({
        keyword: researchReport.keyword,
        cards: researchActionCards,
        collection_name: `${researchReport.keyword} 行动卡`,
        is_focus_reference: asFocusReference,
      });
      setResearchMessage(
        asFocusReference
          ? t("research.actionsSavedToFocus", "行动卡已加入 Focus 参考")
          : t("research.actionsSaved", `已保存 ${result.created_count} 张行动卡`),
      );
    } catch {
      setResearchMessage(t("research.actionsSaveFailed", "保存行动卡失败，请稍后重试"));
    } finally {
      setSavingResearchActions(false);
    }
  };

  const researchProgress = Math.max(0, Math.min(100, Number(researchJob?.progress_percent || 0)));
  const researchStageLabel =
    researchJob?.stage_label || t("inbox.researchingTitle", "正在汇总多源内容并生成研报");
  const researchStageMessage =
    researchJob?.message ||
    t(
      "inbox.researchingDesc",
      "系统会先检索公开网页和公众号结果，再提炼政策、预算、项目分期和销售/投标建议。",
    );
  const researchKeywordGroups = buildResearchKeywordGroups(
    researchJob?.keyword || researchKeyword,
    researchJob?.research_focus ?? researchFocus,
  );
  const activeResearchMode = (researchJob?.research_mode as ResearchMode | undefined) || researchMode;
  const researchModeLabel =
    activeResearchMode === "deep"
      ? t("inbox.mode.deep", "深度调研")
      : t("inbox.mode.fast", "极速调研");
  const researchModeHint =
    activeResearchMode === "deep"
      ? t("inbox.mode.deepHint", "多轮扩搜 + 定向信息源 + 更长综合研判，通常 5 分钟以上。")
      : t("inbox.mode.fastHint", "优先官方与高信号来源，3 分钟内给出可执行初版。");
  const researchEstimatedMinutes =
    researchJob?.estimated_seconds && researchJob.estimated_seconds > 0
      ? Math.max(1, Math.round(researchJob.estimated_seconds / 60))
      : buildResearchModeConfig(activeResearchMode).estimatedMinutes;
  const pipelineOrder: ResearchPipelineKey[] = ["fetch", "clean", "analyze"];
  const activePipelineKey = mapResearchStageToPipelineKey(researchJob?.stage_key);
  const researchPipelineStages = pipelineOrder.map((key, index) => {
    const diagnosticStage = researchReport?.source_diagnostics?.pipeline_stages?.find((stage) => stage.key === key);
    const activeIndex = pipelineOrder.indexOf(activePipelineKey);
    let statusValue: ResearchPipelineStatus = "pending";
    if (researchJob?.status === "succeeded") {
      statusValue = "done";
    } else if (index < activeIndex) {
      statusValue = "done";
    } else if (index === activeIndex) {
      statusValue = "active";
    }
    return {
      key,
      label:
        diagnosticStage?.label ||
        (key === "fetch" ? "取数" : key === "clean" ? "清洗" : "分析"),
      value: Number(diagnosticStage?.value || 0),
      summary: diagnosticStage?.summary || defaultResearchPipelineSummary(key),
      status: statusValue,
    };
  });
  const activePipelineStage =
    researchPipelineStages.find((stage) => stage.status === "active") ||
    researchPipelineStages[researchPipelineStages.length - 1];

  return (
    <>
      <section className="af-glass rounded-[30px] p-5 md:p-7">
        <div className="mb-5">
          <p className="af-kicker">{t("inbox.intakeKicker", "Content Intake")}</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
            {t("inbox.intakeTitle", "添加新内容")}
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            {t("inbox.intakeDesc", "粘贴链接、文本，或输入关键词生成多源研究报告。")}
          </p>
        </div>

        <div className="space-y-4">
          <section className="rounded-2xl border border-white/80 bg-white/55 p-4">
            <label className="block text-sm font-semibold text-slate-700">
              {t("inbox.urlInput", "URL 输入")}
            </label>
            <input
              type="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder={t("inbox.urlPlaceholder", "https://...")}
              className="af-input mt-2"
            />
            <button
              type="button"
              onClick={() => {
                void submitUrl();
              }}
              disabled={submitting}
              className="af-btn af-btn-primary mt-3 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {t("inbox.submitUrl", "提交 URL")}
            </button>
          </section>

          <section className="rounded-2xl border border-white/80 bg-white/55 p-4">
            <label className="block text-sm font-semibold text-slate-700">
              {t("inbox.batchInput", "批量 URL 输入（每行一个，适合 30 篇公众号测试）")}
            </label>
            <textarea
              rows={6}
              value={batchUrls}
              onChange={(event) => setBatchUrls(event.target.value)}
              placeholder={`${t("inbox.batchPlaceholder", "https://mp.weixin.qq.com/s?...")} \n${t(
                "inbox.batchPlaceholder",
                "https://mp.weixin.qq.com/s?...",
              )}`}
              className="af-input mt-2 resize-y leading-6"
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-slate-500">
                {t("inbox.batchRecognized", "已识别 URL")}：
                {
                  batchUrls
                    .split(/\r?\n/)
                    .map((line) => line.trim())
                    .filter(Boolean).length
                }
              </p>
              <button
                type="button"
                onClick={() => {
                  void submitBatchUrls();
                }}
                disabled={submitting}
                className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
              >
                {t("inbox.submitBatch", "批量提交 URL")}
              </button>
            </div>
            {batchMessage ? <p className="mt-2 text-xs text-emerald-700">{batchMessage}</p> : null}
          </section>

          <section className="rounded-2xl border border-white/80 bg-white/55 p-4">
            <label className="block text-sm font-semibold text-slate-700">
              {t("inbox.textInput", "纯文本输入")}
            </label>
            <textarea
              rows={8}
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              placeholder={t("inbox.textPlaceholder", "粘贴你想处理的文本...")}
              className="af-input mt-2 resize-none leading-6"
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-slate-500">
                {t("inbox.charCount", "字数")}：{rawText.trim().length}
              </p>
              <button
                type="button"
                onClick={() => {
                  void submitText();
                }}
                disabled={submitting}
                className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
              >
                {t("inbox.submitText", "提交文本")}
              </button>
            </div>
          </section>

          <MultiFormatImportPanel />
        </div>

        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
      </section>

      <section className="mt-5 rounded-[24px] border border-sky-100/90 bg-[linear-gradient(180deg,rgba(245,250,255,0.98),rgba(239,246,255,0.94))] px-4 py-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.86)] md:px-5 md:py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <label className="block text-[13px] font-semibold tracking-[-0.01em] text-slate-700">
              {t("inbox.keywordInput", "关键词研究")}
            </label>
            <p className="mt-1.5 max-w-[560px] text-[10px] leading-[1.7] text-slate-500">
              {t(
                "inbox.keywordDesc",
                "系统会搜索公开网页与公众号相关文章，自动生成偏咨询顾问风格、关注未来五年预算/招标/生态的专题研报。",
              )}
            </p>
          </div>
          <span
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-sky-200 bg-white/92 text-[10px] font-semibold leading-none text-sky-600 shadow-[0_6px_14px_-12px_rgba(59,130,246,0.45)]"
            style={{ writingMode: "vertical-rl", textOrientation: "upright" }}
          >
            {t("inbox.keywordBadgeCn", "研究")}
          </span>
        </div>

        <input
          type="text"
          value={researchKeyword}
          onChange={(event) => setResearchKeyword(event.target.value)}
          placeholder={t(
            "inbox.keywordPlaceholderDetailed",
            "例如：长三角地区政企行业和医疗行业 AI 大模型及应用落地",
          )}
          className="mt-3 h-[42px] w-full rounded-[14px] border border-slate-200/85 bg-white/96 px-4 text-[13px] text-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] outline-none transition placeholder:text-slate-400 focus:border-sky-200 focus:ring-2 focus:ring-sky-100/70"
        />

        <textarea
          rows={4}
          value={researchFocus}
          onChange={(event) => setResearchFocus(event.target.value)}
          placeholder={t(
            "inbox.keywordPromptPlaceholder",
            "例如：围绕某行业/区域/项目方向，研究甲方需求、预算口径、竞品厂商、已落地案例、行业名单和可能招投标时间。",
          )}
          className="mt-3 min-h-[104px] w-full resize-none rounded-[16px] border border-slate-200/90 bg-white/96 px-4 py-3 text-[13px] leading-6 text-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] outline-none transition placeholder:text-slate-400 focus:border-sky-200 focus:ring-2 focus:ring-sky-100/60"
        />

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setResearchMode("fast")}
            disabled={researching}
            className={`inline-flex items-center justify-center rounded-full border px-4 py-2 text-[12px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
              researchMode === "fast"
                ? "border-sky-200 bg-[linear-gradient(180deg,#3c91ff,#1f73f0)] text-white shadow-[0_12px_20px_-16px_rgba(31,115,240,0.72)]"
                : "border-slate-200 bg-white/94 text-slate-700 shadow-[0_8px_18px_-18px_rgba(15,23,42,0.35)]"
            }`}
          >
            {t("inbox.mode.fast", "极速调研")}
          </button>
          <button
            type="button"
            onClick={() => setResearchMode("deep")}
            disabled={researching}
            className={`inline-flex items-center justify-center rounded-full border px-4 py-2 text-[12px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
              researchMode === "deep"
                ? "border-sky-200 bg-[linear-gradient(180deg,#3c91ff,#1f73f0)] text-white shadow-[0_12px_20px_-16px_rgba(31,115,240,0.72)]"
                : "border-slate-200 bg-white/94 text-slate-700 shadow-[0_8px_18px_-18px_rgba(15,23,42,0.35)]"
            }`}
          >
            {t("inbox.mode.deep", "深度调研")}
          </button>
        </div>

        <div className="mt-3 space-y-1">
          <p className="text-[10px] leading-[1.7] text-slate-500">
            {t(
              "inbox.keywordHelper",
              "建议输入“行业 + 场景 + 项目阶段/预算/中标/招标”等组合关键词，系统会更关注未来五年的刚需场景与预算节奏。",
            )}
          </p>
          <p className="text-[10px] leading-[1.7] text-slate-400">{researchModeHint}</p>
        </div>

        <div className="mt-3">
          <button
            type="button"
            onClick={() => {
              void submitResearch();
            }}
            disabled={researching}
            className="inline-flex min-w-[98px] items-center justify-center rounded-full bg-[linear-gradient(180deg,#3c91ff,#1f73f0)] px-5 py-2 text-[12px] font-semibold text-white shadow-[0_14px_24px_-18px_rgba(31,115,240,0.72)] transition hover:brightness-[1.02] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {researching ? t("inbox.generatingResearch", "生成中...") : t("inbox.submitKeywordResearch", "生成研报")}
          </button>
        </div>

        {researchError ? <p className="mt-3 text-sm text-rose-600">{researchError}</p> : null}
      </section>

      {researching ? (
        <LegacyResearchProgressCard
          progress={researchProgress}
          stateLabel={t("inbox.researchingState", "研究中")}
          stageLabel={researchStageLabel}
          stageMessage={researchStageMessage}
          modeLabel={researchModeLabel}
          estimatedMinutes={researchEstimatedMinutes}
          keywordGroups={researchKeywordGroups}
          modeHint={researchModeHint}
          activePipelineLabel={activePipelineStage?.label || "取数"}
          pipelineStages={researchPipelineStages}
        />
      ) : null}

      {researchReport ? (
        <div className="mt-5 space-y-5">
          <ResearchReportCard
            report={researchReport}
            titleLabel={t("inbox.researchTitle", "关键词情报简报")}
            summaryLabel={t("inbox.researchSummary", "执行摘要")}
            angleLabel={t("inbox.researchAngle", "咨询价值")}
            queryPlanLabel={t("inbox.researchQueries", "检索路径")}
            sourcesLabel={t("inbox.researchSources", "来源与证据")}
            sourceCountLabel={t("inbox.researchSourceCount", "来源数")}
            generatedAtLabel={t("inbox.researchGeneratedAt", "生成于")}
            saveLabel={t("inbox.researchSave", "加入知识库")}
            focusSaveLabel={t("inbox.researchSaveToFocus", "加入 Focus 参考")}
            exportLabel={t("inbox.researchExport", "导出 Markdown")}
            exportWordLabel={t("inbox.researchExportWord", "导出 Word")}
            exportPdfLabel={t("inbox.researchExportPdf", "导出 PDF")}
            savedLabel={t("inbox.researchOpenKnowledge", "查看知识卡片")}
            actionMessage={researchMessage}
            knowledgeHref={savedResearchEntryId ? `/knowledge/${savedResearchEntryId}` : null}
            saving={savingResearch}
            savingAsFocus={savingResearchAsFocus}
            exporting={exportingResearchFormat === "markdown"}
            exportingWord={exportingResearchFormat === "word"}
            exportingPdf={exportingResearchFormat === "pdf"}
            onSave={() => {
              void saveCurrentResearch(false);
            }}
            onSaveAsFocus={() => {
              void saveCurrentResearch(true);
            }}
            onExport={() => {
              void exportCurrentResearch("markdown");
            }}
            onExportWord={() => {
              void exportCurrentResearch("word");
            }}
            onExportPdf={() => {
              void exportCurrentResearch("pdf");
            }}
            hideSources
            actionCardSlot={
              <ResearchActionCardsPanel
                t={t}
                title={t("research.actionCardsTitle", "下一步推进剧本")}
                subtitle={t("research.actionCardsHint", "把账户、销售、投标与生态判断拆成可执行动作。")}
                cards={researchActionCards}
                planning={planningResearchActions}
                saving={savingResearchActions}
                onPlan={() => {
                  void planResearchActions();
                }}
                onSave={() => {
                  void saveCurrentResearchActions(false);
                }}
                onSaveToFocus={() => {
                  void saveCurrentResearchActions(true);
                }}
              />
            }
          />
          <section className="af-glass rounded-[30px] p-5 md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="af-kicker">Research Follow-up</p>
                <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
                  追问补证与正式文档输出
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  在当前研报基础上补充新信息、新证据和新需求，可继续生成新版研报，或直接导出可行性研究报告与项目建议书。
                </p>
              </div>
              <span className="rounded-full border border-slate-200 bg-white/70 px-3 py-1 text-xs text-slate-500">
                当前研报 · {researchReport.report_title}
              </span>
            </div>
            <div className="mt-4 grid gap-4">
              <div className="rounded-[24px] border border-white/80 bg-white/68 p-4">
                <p className="text-sm font-semibold text-slate-900">研报追问 / 补证后二次生成</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  这一步会把当前研报结论和你补充的新信息一起送回研究链路，重新检索、交叉验证并生成新版研报。
                </p>
                {followupDiagnostics?.enabled ? (
                  <div className="mt-4 rounded-[20px] border border-amber-200/80 bg-amber-50/80 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">
                      二次检索诊断
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      {followupDiagnostics.summary || "当前补证输入已接入二次检索。"}
                    </p>
                    {followupDiagnostics.planning_focus ? (
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        规划焦点：{followupDiagnostics.planning_focus}
                      </p>
                    ) : null}
                    {followupDiagnostics.input_sections?.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {followupDiagnostics.input_sections.map((label) => (
                          <span key={`followup-input-${label}`} className="rounded-full bg-white px-2.5 py-1 text-[11px] text-slate-600">
                            {label}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {followupFilters.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {followupFilters.map((label) => (
                          <span
                            key={`followup-filter-${label}`}
                            className="rounded-full border border-amber-200 bg-white px-2.5 py-1 text-[11px] text-amber-700"
                          >
                            {label}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {followupDiagnostics.decomposition_queries?.length ? (
                      <div className="mt-3 space-y-2">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">优先补证子查询</p>
                        <div className="space-y-2">
                          {followupDiagnostics.decomposition_queries.slice(0, 4).map((query) => (
                            <div key={`followup-query-${query}`} className="rounded-2xl border border-white/90 bg-white/75 px-3 py-2 text-xs leading-5 text-slate-600">
                              {query}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  追问重点
                </label>
                <textarea
                  rows={3}
                  value={followupResearchFocus}
                  onChange={(event) => setFollowupResearchFocus(event.target.value)}
                  placeholder="例如：补甲方组织入口、预算来源、二期节奏和竞品中标情况"
                  className="af-input mt-2 resize-none leading-6"
                />
                <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  新信息 / 新背景
                </label>
                <textarea
                  rows={4}
                  value={deliverySupplement.supplemental_context}
                  onChange={(event) => updateDeliverySupplementField("supplemental_context", event.target.value)}
                  placeholder="补充你人工掌握的新背景、新约束、新判断，作为待交叉验证输入。"
                  className="af-input mt-2 resize-none leading-6"
                />
                <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  新证据 / 待核验线索
                </label>
                <textarea
                  rows={4}
                  value={deliverySupplement.supplemental_evidence}
                  onChange={(event) => updateDeliverySupplementField("supplemental_evidence", event.target.value)}
                  placeholder="可粘贴新来源摘要、口径说明、会议纪要片段或待核验线索。"
                  className="af-input mt-2 resize-none leading-6"
                />
                <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  新需求 / 输出要求
                </label>
                <textarea
                  rows={4}
                  value={deliverySupplement.supplemental_requirements}
                  onChange={(event) => updateDeliverySupplementField("supplemental_requirements", event.target.value)}
                  placeholder="例如：优先补业主单位、预算口径、项目边界、落地节奏与实施约束。"
                  className="af-input mt-2 resize-none leading-6"
                />
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs text-slate-500">
                    当前会带入上一版标题、执行摘要，以及上面三块补充信息后重新生成。
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      void submitResearch({
                        keyword: researchReport.keyword,
                        researchFocus: followupResearchFocus,
                        followupReportTitle: researchReport.report_title,
                        followupReportSummary: researchReport.executive_summary,
                        supplementalContext: deliverySupplement.supplemental_context,
                        supplementalEvidence: deliverySupplement.supplemental_evidence,
                        supplementalRequirements: deliverySupplement.supplemental_requirements,
                        queuedMessage:
                          researchMode === "deep"
                            ? "已启动补证后二次深度研究，正在结合上一版结论与新增输入重新检索。"
                            : "已启动补证后二次极速研究，正在优先校验新增输入与高信号来源。",
                      });
                    }}
                    disabled={researching}
                    className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {researching ? "生成中..." : "结合补充信息重新生成研报"}
                  </button>
                </div>
              </div>

              <div className="rounded-[24px] border border-white/80 bg-white/68 p-4">
                <p className="text-sm font-semibold text-slate-900">正式文档输出</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  输出前可补充项目名称、建设单位、区域、投资口径和交叉验证说明，导出时会自动套用正式模板。
                </p>
                <div className="mt-4 grid gap-3">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      项目名称
                    </label>
                    <input
                      type="text"
                      value={deliverySupplement.project_name}
                      onChange={(event) => updateDeliverySupplementField("project_name", event.target.value)}
                      placeholder="例如：XX 项目可研"
                      className="af-input mt-2"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      建设单位 / 业主
                    </label>
                    <input
                      type="text"
                      value={deliverySupplement.project_owner}
                      onChange={(event) => updateDeliverySupplementField("project_owner", event.target.value)}
                      placeholder="例如：某数据局 / 某集团"
                      className="af-input mt-2"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      区域 / 范围
                    </label>
                    <input
                      type="text"
                      value={deliverySupplement.project_region}
                      onChange={(event) => updateDeliverySupplementField("project_region", event.target.value)}
                      placeholder="例如：上海市 / 华东区域"
                      className="af-input mt-2"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      实施窗口
                    </label>
                    <input
                      type="text"
                      value={deliverySupplement.implementation_window}
                      onChange={(event) => updateDeliverySupplementField("implementation_window", event.target.value)}
                      placeholder="例如：2026 Q2-Q4"
                      className="af-input mt-2"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      投资估算 / 预算口径
                    </label>
                    <input
                      type="text"
                      value={deliverySupplement.investment_estimate}
                      onChange={(event) => updateDeliverySupplementField("investment_estimate", event.target.value)}
                      placeholder="例如：一期预算 500-800 万，分年度拨付"
                      className="af-input mt-2"
                    />
                  </div>
                </div>
                <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  建设依据 / 报告引用口径
                </label>
                <textarea
                  rows={3}
                  value={deliverySupplement.construction_basis}
                  onChange={(event) => updateDeliverySupplementField("construction_basis", event.target.value)}
                  placeholder="补充立项依据、政策依据、会议纪要或内部口径。"
                  className="af-input mt-2 resize-none leading-6"
                />
                <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  建设范围 / 建议方案边界
                </label>
                <textarea
                  rows={3}
                  value={deliverySupplement.scope_statement}
                  onChange={(event) => updateDeliverySupplementField("scope_statement", event.target.value)}
                  placeholder="补充建设范围、边界约束、项目拆分口径。"
                  className="af-input mt-2 resize-none leading-6"
                />
                <div className="mt-4 grid gap-3">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      预期效益
                    </label>
                    <textarea
                      rows={3}
                      value={deliverySupplement.expected_benefits}
                      onChange={(event) => updateDeliverySupplementField("expected_benefits", event.target.value)}
                      placeholder="补充业务收益、管理收益或项目目标。"
                      className="af-input mt-2 resize-none leading-6"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      交叉验证说明
                    </label>
                    <textarea
                      rows={3}
                      value={deliverySupplement.cross_validation_notes}
                      onChange={(event) => updateDeliverySupplementField("cross_validation_notes", event.target.value)}
                      placeholder="说明哪些输入来自人工补充，哪些需要后续继续核验。"
                      className="af-input mt-2 resize-none leading-6"
                    />
                  </div>
                </div>
                <div className="mt-4 grid gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      void exportFormalResearchDocument("feasibility_word");
                    }}
                    disabled={!!exportingFormalDocument}
                    className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {exportingFormalDocument === "feasibility_word" ? "导出中..." : "导出可研 Word"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void exportFormalResearchDocument("feasibility_pdf");
                    }}
                    disabled={!!exportingFormalDocument}
                    className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {exportingFormalDocument === "feasibility_pdf" ? "导出中..." : "导出可研 PDF"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void exportFormalResearchDocument("proposal_word");
                    }}
                    disabled={!!exportingFormalDocument}
                    className="af-btn af-btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {exportingFormalDocument === "proposal_word" ? "导出中..." : "导出项目建议书 Word"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void exportFormalResearchDocument("proposal_pdf");
                    }}
                    disabled={!!exportingFormalDocument}
                    className="af-btn af-btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {exportingFormalDocument === "proposal_pdf" ? "导出中..." : "导出项目建议书 PDF"}
                  </button>
                </div>
              </div>
            </div>
          </section>
          <section className="af-glass rounded-[30px] p-5 md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="af-kicker">{t("inbox.researchSources", "来源样本")}</p>
                <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
                  {t("inbox.researchSourceTitle", "参考来源与采集诊断")}
                </h3>
                <p className="mt-2 text-sm text-slate-500">
                  {t("inbox.researchSourceHint", "仅保留近 7 年内可验证来源；优先显示官方、招采与高信号聚合源。")}
                </p>
              </div>
              <span className="rounded-full border border-slate-200 bg-white/70 px-3 py-1 text-xs text-slate-500">
                {t("inbox.researchSourceCount", "来源数")} · {researchReport.source_count}
              </span>
            </div>
            {researchReport.source_diagnostics ? (
              <div className="mt-4 rounded-2xl border border-slate-200/80 bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  {t("inbox.researchDiagnostics", "采集诊断")}
                </p>
                {isGuardedBacklog(researchReport.source_diagnostics) ? (
                  <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                    <span className="rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                      已降级为 guarded backlog
                    </span>
                    {guardedReasonLabels.map((label) => (
                      <span key={label} className="rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                        {label}
                      </span>
                    ))}
                  </div>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                    {t("inbox.researchDiagnosticsEnabled", "启用源")} {enabledSourceLabels.length}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                    {t("inbox.researchDiagnosticsAdapters", "命中爬虫源")} {researchReport.source_diagnostics.adapter_hit_count}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                    {t("inbox.researchDiagnosticsSearch", "命中搜索源")} {researchReport.source_diagnostics.search_hit_count}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                    近 {researchReport.source_diagnostics.recency_window_years} 年窗口
                  </span>
                  {researchReport.source_diagnostics.filtered_old_source_count ? (
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                      剔除过旧来源 {researchReport.source_diagnostics.filtered_old_source_count}
                    </span>
                  ) : null}
                  {researchReport.source_diagnostics.filtered_region_conflict_count ? (
                    <span className="rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                      拦截越界区域 {researchReport.source_diagnostics.filtered_region_conflict_count}
                    </span>
                  ) : null}
                  {researchReport.source_diagnostics.strict_topic_source_count ? (
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                      严格主题保留 {researchReport.source_diagnostics.strict_topic_source_count}
                    </span>
                  ) : null}
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                    检索质量 {qualityLabel(researchReport.source_diagnostics.retrieval_quality)}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                    严格命中 {Math.round(researchReport.source_diagnostics.strict_match_ratio * 100)}%
                  </span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                    官方源 {Math.round(researchReport.source_diagnostics.official_source_ratio * 100)}%
                  </span>
                  {researchReport.source_diagnostics.unique_domain_count ? (
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                      覆盖域名 {researchReport.source_diagnostics.unique_domain_count}
                    </span>
                  ) : null}
                  {researchReport.source_diagnostics.expansion_triggered ? (
                    <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                      已触发扩搜补证
                    </span>
                  ) : null}
                </div>
                {supportedTargetAccounts.length || unsupportedTargetAccounts.length ? (
                  <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                    {supportedTargetAccounts.map((label) => (
                      <span key={`supported-${label}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                        已支撑账户 {label}
                      </span>
                    ))}
                    {unsupportedTargetAccounts.map((label) => (
                      <span key={`unsupported-${label}`} className="rounded-full bg-rose-50 px-2.5 py-1 text-rose-700">
                        未支撑账户 {label}
                      </span>
                    ))}
                  </div>
                ) : null}
                {researchReport.source_diagnostics.normalized_entity_count ? (
                  <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                    <span className="rounded-full bg-violet-50 px-2.5 py-1 text-violet-700">
                      实体归一化 {researchReport.source_diagnostics.normalized_entity_count}
                    </span>
                    <span className="rounded-full bg-violet-50 px-2.5 py-1 text-violet-700">
                      甲方 {researchReport.source_diagnostics.normalized_target_count}
                    </span>
                    <span className="rounded-full bg-violet-50 px-2.5 py-1 text-violet-700">
                      竞品 {researchReport.source_diagnostics.normalized_competitor_count}
                    </span>
                    <span className="rounded-full bg-violet-50 px-2.5 py-1 text-violet-700">
                      伙伴 {researchReport.source_diagnostics.normalized_partner_count}
                    </span>
                  </div>
                ) : null}
                {researchReport.entity_graph?.entities?.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {coreEntities.map((entity) => (
                      <span
                        key={`entity-graph-${entity.canonical_name}`}
                        className="rounded-full border border-fuchsia-200 bg-fuchsia-50 px-2.5 py-1 text-xs text-fuchsia-700"
                      >
                        {entity.canonical_name}
                      </span>
                    ))}
                  </div>
                ) : null}
                {enabledSourceLabels.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {enabledSourceLabels.map((label) => (
                      <span key={label} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600">
                        {label}
                      </span>
                    ))}
                  </div>
                ) : null}
                {matchedSourceLabels.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {matchedSourceLabels.map((label) => (
                      <span key={label} className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700">
                        {label}
                      </span>
                    ))}
                  </div>
                ) : null}
                {topicAnchorTerms.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {topicAnchorTerms.map((label) => (
                      <span key={label} className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-700">
                        {label}
                      </span>
                    ))}
                  </div>
                ) : null}
                {matchedThemeLabels.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {matchedThemeLabels.map((label) => (
                      <span key={label} className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">
                        {label}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="mt-4 space-y-4">
              {[
                {
                  key: "official",
                  title: "官方源",
                  items: researchReport.sources.filter((source) => classifyResearchSourceTier(source) === "official"),
                },
                {
                  key: "aggregate",
                  title: "聚合源",
                  items: researchReport.sources.filter((source) => classifyResearchSourceTier(source) === "aggregate"),
                },
                {
                  key: "media",
                  title: "媒体源",
                  items: researchReport.sources.filter((source) => classifyResearchSourceTier(source) === "media"),
                },
              ]
                .filter((group) => group.items.length)
                .map((group) => (
                  <div key={group.key} className="rounded-2xl border border-white/80 bg-white/60 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{group.title}</p>
                      <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-500">
                        {group.items.length}
                      </span>
                    </div>
                    <div className="mt-3 space-y-3">
                      {group.items.map((source) => {
                        const tier = classifyResearchSourceTier(source);
                        return (
                          <a
                            key={`${group.key}-${source.url}-${source.search_query}`}
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="block rounded-2xl border border-slate-200/80 bg-slate-50/70 px-3 py-3 transition hover:border-slate-300 hover:bg-white"
                          >
                            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                              <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                                {sourceTierLabel(tier)}
                              </span>
                              {source.source_label ? (
                                <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                                  {source.source_label}
                                </span>
                              ) : null}
                              <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                                {source.domain || "web"}
                              </span>
                              <span>{source.search_query}</span>
                            </div>
                            <p className="mt-2 text-sm font-semibold leading-6 text-slate-900">{source.title}</p>
                            <p className="mt-1 text-sm leading-6 text-slate-600">{source.snippet}</p>
                          </a>
                        );
                      })}
                    </div>
                  </div>
                ))}
              {!researchReport.sources.length ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-white/60 p-4 text-sm text-slate-500">
                  {t("inbox.researchSourceEmpty", "当前未获取到可展示来源，显示的是本地演示研报结构。")}
                </div>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}

      <div className="mt-5">
        <ResearchHistoryList items={researchHistory} />
        <div className="mt-3 flex justify-end">
          <Link href="/research" className="af-btn af-btn-secondary border px-4 py-2">
            {t("research.centerOpen", "打开商机情报中心")}
          </Link>
        </div>
      </div>
    </>
  );
}
