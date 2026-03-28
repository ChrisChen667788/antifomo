"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiItem,
  ApiResearchJob,
  ApiKnowledgeEntry,
  ApiResearchActionCard,
  ApiResearchReport,
  createItem,
  createItemsBatch,
  createResearchActionPlan,
  createResearchConversation,
  createResearchJob,
  createTask,
  getResearchJob,
  listKnowledgeEntries,
  listItems,
  reprocessItem,
  saveResearchActionCards,
  saveResearchReport,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { ResearchHistoryList } from "@/components/inbox/research-history-list";
import { ResearchReportCard } from "@/components/inbox/research-report-card";
import { MultiFormatImportPanel } from "@/components/inbox/multiformat-import-panel";
import { ResearchActionCardsPanel } from "@/components/research/research-action-cards-panel";
import { normalizeResearchActionCards, type UiResearchActionCard } from "@/lib/research-action-cards";

type ProcessStatus = "pending" | "processing" | "ready" | "failed";
type ResearchMode = "fast" | "deep";

function statusColor(status: ProcessStatus): string {
  if (status === "ready") return "text-emerald-700 bg-emerald-50/85 border-emerald-200/80";
  if (status === "failed") return "text-rose-700 bg-rose-50/85 border-rose-200/80";
  if (status === "pending") return "text-slate-600 bg-slate-100/90 border-slate-200/80";
  return "text-blue-700 bg-blue-50/85 border-blue-200/80";
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

export function InboxForm() {
  const { preferences, t } = useAppPreferences();
  const [url, setUrl] = useState("");
  const [batchUrls, setBatchUrls] = useState("");
  const [rawText, setRawText] = useState("");
  const [researchKeyword, setResearchKeyword] = useState("");
  const [researchFocus, setResearchFocus] = useState("");
  const [researchMode, setResearchMode] = useState<ResearchMode>("deep");
  const [recentItems, setRecentItems] = useState<ApiItem[]>([]);
  const [researchHistory, setResearchHistory] = useState<ApiKnowledgeEntry[]>([]);
  const [researchReport, setResearchReport] = useState<ApiResearchReport | null>(null);
  const [researchJob, setResearchJob] = useState<ApiResearchJob | null>(null);
  const [researchActionCards, setResearchActionCards] = useState<UiResearchActionCard[]>([]);
  const [savedResearchEntryId, setSavedResearchEntryId] = useState<string | null>(null);
  const [status, setStatus] = useState<ProcessStatus>("pending");
  const [error, setError] = useState("");
  const [researchError, setResearchError] = useState("");
  const [researchMessage, setResearchMessage] = useState("");
  const [batchMessage, setBatchMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [researching, setResearching] = useState(false);
  const [savingResearch, setSavingResearch] = useState(false);
  const [savingResearchAsFocus, setSavingResearchAsFocus] = useState(false);
  const [exportingResearchFormat, setExportingResearchFormat] = useState<"" | "markdown" | "word" | "pdf">("");
  const [planningResearchActions, setPlanningResearchActions] = useState(false);
  const [savingResearchActions, setSavingResearchActions] = useState(false);
  const [lastSubmitTime, setLastSubmitTime] = useState<string>("");
  const [seededConversationJobId, setSeededConversationJobId] = useState("");

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

  const statusText: Record<ProcessStatus, string> = {
    pending: t("status.pending", "等待处理"),
    processing: t("status.processing", "处理中"),
    ready: t("status.ready", "已完成"),
    failed: t("status.failed", "处理失败"),
  };

  useEffect(() => {
    const refresh = async () => {
      try {
        const response = await listItems(10);
        setRecentItems(response.items);
        if (response.items.length > 0) {
          const latest = response.items[0];
          if (
            latest.status === "pending" ||
            latest.status === "processing" ||
            latest.status === "ready" ||
            latest.status === "failed"
          ) {
            setStatus(latest.status);
          }
        }
      } catch {
        // 保持本地 UI 可用，API 未就绪时不抛错
      }
    };

    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, 2200);

    return () => {
      window.clearInterval(timer);
    };
  }, []);

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
      const item = await createItem({
        source_type: "url",
        source_url: url.trim(),
        output_language: preferences.language,
      });
      setRecentItems((prev) => [item, ...prev].slice(0, 10));
      setStatus(item.status as ProcessStatus);
      setUrl("");
      setLastSubmitTime(new Date().toLocaleTimeString(preferences.language, { hour12: false }));
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
      const item = await createItem({
        source_type: "text",
        raw_content: rawText.trim(),
        title: rawText.trim().slice(0, 24),
        output_language: preferences.language,
      });
      setRecentItems((prev) => [item, ...prev].slice(0, 10));
      setStatus(item.status as ProcessStatus);
      setRawText("");
      setLastSubmitTime(new Date().toLocaleTimeString(preferences.language, { hour12: false }));
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

      const refreshed = await listItems(10);
      setRecentItems(refreshed.items);
      const latest = refreshed.items[0];
      if (latest?.status === "pending" || latest?.status === "processing" || latest?.status === "ready" || latest?.status === "failed") {
        setStatus(latest.status);
      }

      setBatchMessage(
        `${t("inbox.batchResult", "批量提交完成")}：${t("inbox.batchTotal", "总计")} ${
          result.total
        }，${t("inbox.batchCreated", "创建")} ${result.created}，${t(
          "inbox.batchSkipped",
          "跳过",
        )} ${result.skipped}，${t("inbox.batchInvalid", "无效")} ${result.invalid}。`,
      );
      setBatchUrls("");
      setLastSubmitTime(new Date().toLocaleTimeString(preferences.language, { hour12: false }));
    } catch {
      setError(t("inbox.error.batchFailed", "批量提交失败，请检查后端服务是否启动。"));
    } finally {
      setSubmitting(false);
    }
  };

  const retryItem = async (itemId: string) => {
    try {
      await reprocessItem(itemId, { output_language: preferences.language });
      setRecentItems((prev) =>
        prev.map((item) =>
          item.id === itemId
            ? {
                ...item,
                status: "processing",
              }
            : item,
        ),
      );
      setStatus("processing");
    } catch {
      setError(t("inbox.error.retryFailed", "重试失败，请检查后端服务。"));
    }
  };

  const submitResearch = async () => {
    if (!researchKeyword.trim()) {
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
        keyword: researchKeyword.trim(),
        research_focus: researchFocus.trim() || undefined,
        output_language: preferences.language,
        include_wechat: true,
        max_sources: modeConfig.max_sources,
        deep_research: modeConfig.deep_research,
        research_mode: modeConfig.research_mode,
      });
      setResearchJob(job);
      setResearchMessage(
        researchMode === "deep"
          ? t("inbox.researchQueuedDeep", "已启动深度研究任务，正在持续汇总多源信息。")
          : t("inbox.researchQueuedFast", "已启动极速研究任务，优先汇总高信号来源。"),
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
  const researchProgressDegrees = Math.max(researchProgress, 4) * 3.6;
  const researchRingStyle = {
    backgroundImage: `conic-gradient(from -90deg, #5b7cf7 0deg, #6aa1ff ${Math.max(
      48,
      researchProgressDegrees * 0.58,
    )}deg, #7fb9ff ${researchProgressDegrees}deg, rgba(226, 232, 240, 0.92) ${researchProgressDegrees}deg 360deg)`,
    WebkitMask:
      "radial-gradient(farthest-side, transparent calc(100% - 13px), #000 calc(100% - 12px))",
    mask: "radial-gradient(farthest-side, transparent calc(100% - 13px), #000 calc(100% - 12px))",
  } as const;

  return (
    <>
      <div className="grid gap-5 md:grid-cols-[1.75fr_1fr]">
        <div className="af-glass rounded-[30px] p-5 md:p-7">
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
              {batchMessage ? (
                <p className="mt-2 text-xs text-emerald-700">{batchMessage}</p>
              ) : null}
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

            <section className="rounded-2xl border border-sky-100 bg-sky-50/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <label className="block text-sm font-semibold text-slate-700">
                    {t("inbox.keywordInput", "关键词研究")}
                  </label>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    {t(
                      "inbox.keywordDesc",
                      "系统会搜索公开网页与公众号相关文章，自动生成偏咨询顾问风格的专题研报。",
                    )}
                  </p>
                </div>
                <span className="rounded-full border border-sky-200 bg-white/80 px-3 py-1 text-xs font-semibold text-sky-600">
                  {t("inbox.keywordBadge", "Research")}
                </span>
              </div>
              <input
                type="text"
                value={researchKeyword}
                onChange={(event) => setResearchKeyword(event.target.value)}
                placeholder={t("inbox.keywordPlaceholder", "例如：政务云 AI 中标 预算")}
                className="af-input mt-3"
              />
              <textarea
                rows={3}
                value={researchFocus}
                onChange={(event) => setResearchFocus(event.target.value)}
                placeholder={t(
                  "inbox.keywordFocusPlaceholder",
                  "补充关注点，例如：领导发言、项目二期、销售切入、投标策略",
                )}
                className="af-input mt-3 resize-none leading-6"
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setResearchMode("fast")}
                  disabled={researching}
                  className={`af-btn px-4 py-2 text-sm ${
                    researchMode === "fast" ? "af-btn-primary" : "af-btn-secondary"
                  } disabled:cursor-not-allowed disabled:opacity-60`}
                >
                  {t("inbox.mode.fast", "极速调研")}
                </button>
                <button
                  type="button"
                  onClick={() => setResearchMode("deep")}
                  disabled={researching}
                  className={`af-btn px-4 py-2 text-sm ${
                    researchMode === "deep" ? "af-btn-primary" : "af-btn-secondary"
                  } disabled:cursor-not-allowed disabled:opacity-60`}
                >
                  {t("inbox.mode.deep", "深度调研")}
                </button>
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">
                    {t(
                      "inbox.keywordHelper",
                      "建议输入“行业 + 场景 + 项目阶段/预算/中标”等组合关键词，输出更稳。",
                    )}
                  </p>
                  <p className="text-xs text-slate-400">{researchModeHint}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    void submitResearch();
                  }}
                  disabled={researching}
                  className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {researching
                    ? t("inbox.generatingResearch", "生成中...")
                    : t("inbox.submitKeywordResearch", "生成研报")}
                </button>
              </div>
              {researchError ? <p className="mt-3 text-sm text-rose-600">{researchError}</p> : null}
            </section>
          </div>

          {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
        </div>

        <aside className="af-glass rounded-[30px] p-5 md:p-6">
          <p className="af-kicker">{t("inbox.processingKicker", "Processing")}</p>
          <p
            className={`mt-3 inline-flex rounded-full border px-3 py-1 text-sm font-semibold ${statusColor(
              status,
            )}`}
          >
            {statusText[status] ?? t("status.processing", "处理中")}
          </p>
          {lastSubmitTime ? (
            <p className="mt-3 text-sm text-slate-500">
              {t("common.recentSubmit", "最近提交")}：{lastSubmitTime}
            </p>
          ) : null}

          <div className="mt-5 space-y-2.5">
            {recentItems.length === 0 ? (
              <p className="text-sm text-slate-500">{t("inbox.noRecent", "暂无最近添加。")}</p>
            ) : null}
            {recentItems.map((item) => {
              const itemStatus =
                item.status === "pending" ||
                item.status === "processing" ||
                item.status === "ready" ||
                item.status === "failed"
                  ? item.status
                  : "pending";

              return (
                <div
                  key={item.id}
                  className="rounded-2xl border border-white/80 bg-white/55 p-3"
                >
                  <p className="line-clamp-1 text-sm font-semibold text-slate-800">
                    {item.title || item.source_url || t("common.untitled", "未命名内容")}
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${statusColor(
                        itemStatus,
                      )}`}
                    >
                      {statusText[itemStatus]}
                    </span>
                    {itemStatus === "failed" ? (
                      <button
                        type="button"
                        onClick={() => {
                          void retryItem(item.id);
                        }}
                        className="af-btn af-btn-secondary px-2.5 py-1 text-xs"
                      >
                        {t("common.retry", "重试")}
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>
      </div>

      {researching ? (
        <section className="mt-5 rounded-[30px] border border-white/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(248,250,252,0.88))] p-5 shadow-[0_28px_90px_-64px_rgba(15,23,42,0.32)] md:p-6">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex items-center gap-4 md:gap-5">
              <div className="relative h-[108px] w-[108px] shrink-0">
                <div className="absolute inset-0 rounded-full border border-slate-200/90 bg-[radial-gradient(circle_at_50%_20%,rgba(255,255,255,0.98),rgba(241,245,249,0.9)_68%,rgba(226,232,240,0.92))] shadow-[0_18px_40px_-28px_rgba(15,23,42,0.2)]" />
                <div className="absolute inset-[7px] rounded-full opacity-95" style={researchRingStyle} />
                <div className="absolute inset-[20px] rounded-full border border-slate-200/80 bg-white/95 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]" />
                <div className="absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
                  <span className="text-[26px] font-semibold leading-none tracking-[-0.05em] text-slate-900">
                    {researchProgress}%
                  </span>
                  <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    {t("inbox.researchProgress", "研究进度")}
                  </span>
                </div>
              </div>
              <div className="min-w-0">
                <p className="af-kicker">{t("inbox.researchingKicker", "Research in Progress")}</p>
                <h3 className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-slate-900">
                  {researchStageLabel}
                </h3>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{researchStageMessage}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2.5 text-xs">
                  <span className="rounded-full bg-slate-900 px-3 py-1 text-white">{researchModeLabel}</span>
                  <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-500">
                    {t("inbox.researchEstimated", "预计耗时")} · {researchEstimatedMinutes} min
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {researchKeywordGroups.map((group) => (
                    <span
                      key={group}
                      className="rounded-full border border-slate-200 bg-slate-50/90 px-3 py-1 text-xs font-medium text-slate-600"
                    >
                      {group}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <div className="max-w-sm rounded-[24px] border border-slate-200/80 bg-white/82 px-4 py-3 text-sm text-slate-500">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                {researchModeLabel}
              </p>
              <p className="mt-1.5 leading-6 text-slate-700">{researchModeHint}</p>
            </div>
          </div>
        </section>
      ) : null}

      {researchReport ? (
        <div className="mt-5 space-y-5">
          <ResearchReportCard
            report={researchReport}
            titleLabel={t("inbox.researchTitle", "关键词研究报告")}
            summaryLabel={t("inbox.researchSummary", "执行摘要")}
            angleLabel={t("inbox.researchAngle", "咨询价值")}
            queryPlanLabel={t("inbox.researchQueries", "检索路径")}
            sourcesLabel={t("inbox.researchSources", "来源样本")}
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
                title={t("research.actionCardsTitle", "把研报拆成可执行建议")}
                subtitle={t("research.actionCardsHint", "自动沉淀为销售、投标、陌拜与生态合作行动卡。")}
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
                <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                    {t("inbox.researchDiagnosticsEnabled", "启用源")} {researchReport.source_diagnostics.enabled_source_labels.length}
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
                    {researchReport.entity_graph.entities.slice(0, 6).map((entity) => (
                      <span
                        key={`entity-graph-${entity.canonical_name}`}
                        className="rounded-full border border-fuchsia-200 bg-fuchsia-50 px-2.5 py-1 text-xs text-fuchsia-700"
                      >
                        {entity.canonical_name}
                      </span>
                    ))}
                  </div>
                ) : null}
                {researchReport.source_diagnostics.enabled_source_labels.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {researchReport.source_diagnostics.enabled_source_labels.map((label) => (
                      <span key={label} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600">
                        {label}
                      </span>
                    ))}
                  </div>
                ) : null}
                {researchReport.source_diagnostics.matched_source_labels.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {researchReport.source_diagnostics.matched_source_labels.map((label) => (
                      <span key={label} className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs text-sky-700">
                        {label}
                      </span>
                    ))}
                  </div>
                ) : null}
                {researchReport.source_diagnostics.topic_anchor_terms.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {researchReport.source_diagnostics.topic_anchor_terms.map((label) => (
                      <span key={label} className="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs text-violet-700">
                        {label}
                      </span>
                    ))}
                  </div>
                ) : null}
                {researchReport.source_diagnostics.matched_theme_labels.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {researchReport.source_diagnostics.matched_theme_labels.map((label) => (
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
            {t("research.centerOpen", "打开研报中心")}
          </Link>
        </div>
      </div>
    </>
  );
}
