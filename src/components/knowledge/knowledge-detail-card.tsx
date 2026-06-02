"use client";

import { useEffect, useMemo, useState } from "react";
import type { ApiKnowledgeEntry, ApiResearchActionCard } from "@/lib/api/types";
import { dedupeTextList } from "@/lib/display-list";
import {
  createResearchActionPlan,
  createTask,
  getKnowledgeMarkdown,
  listRelatedKnowledgeEntries,
  resolveKnowledgeReviewQueueItem,
  saveResearchActionCards,
  sendWorkBuddyWebhook,
  updateKnowledgeEntry,
} from "@/lib/api";
import { ResearchActionCardsPanel } from "@/components/research/research-action-cards-panel";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { getGuardedRewriteReasonLabels, isGuardedBacklog } from "@/lib/research-diagnostics";
import { normalizeResearchActionCards } from "@/lib/research-action-cards";
import { KnowledgeDetailContentEditor } from "@/components/knowledge/knowledge-detail-content-editor";
import { KnowledgeDetailHeaderSection } from "@/components/knowledge/knowledge-detail-header-section";
import {
  buildDiagnosticCards,
  buildGroupedResearchSources,
  buildMarkdownContent,
  buildRankedPanels,
  buildReportSurfaceCopy,
  evidenceModeMeta,
  extractCommercialIntelligence,
  extractResearchReport,
  followupResolutionMeta,
} from "@/components/knowledge/knowledge-detail-card-model";
import { KnowledgeDetailRelatedSection } from "@/components/knowledge/knowledge-detail-related-section";
import { KnowledgeResearchReportAppendixSection } from "@/components/knowledge/knowledge-research-report-appendix-section";
import { KnowledgeResearchReportBriefSection } from "@/components/knowledge/knowledge-research-report-brief-section";
import { KnowledgeResearchReportCommercialSection } from "@/components/knowledge/knowledge-research-report-commercial-section";
import { KnowledgeResearchReportInsightsSection } from "@/components/knowledge/knowledge-research-report-insights-section";
import { KnowledgeResearchReportMethodologySection } from "@/components/knowledge/knowledge-research-report-methodology-section";
import { KnowledgeResearchReportReadinessSection } from "@/components/knowledge/knowledge-research-report-readiness-section";
import { KnowledgeResearchReportReviewQueueSection } from "@/components/knowledge/knowledge-research-report-review-queue-section";
import { KnowledgeResearchReportSourceEvidenceSection } from "@/components/knowledge/knowledge-research-report-source-evidence-section";

export function KnowledgeDetailCard({ item }: { item: ApiKnowledgeEntry }) {
  const { t } = useAppPreferences();
  const [entry, setEntry] = useState(item);
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(item.title);
  const [draftContent, setDraftContent] = useState(item.content);
  const [draftCollection, setDraftCollection] = useState(item.collection_name || "");
  const [saving, setSaving] = useState(false);
  const [pinning, setPinning] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [workBuddyExporting, setWorkBuddyExporting] = useState(false);
  const [message, setMessage] = useState("");
  const [reviewQueueActionId, setReviewQueueActionId] = useState("");
  const [relatedEntries, setRelatedEntries] = useState<ApiKnowledgeEntry[]>([]);
  const [researchActionCards, setResearchActionCards] = useState<ApiResearchActionCard[]>([]);
  const [planningResearchActions, setPlanningResearchActions] = useState(false);
  const [savingResearchActions, setSavingResearchActions] = useState(false);
  const uiResearchActionCards = useMemo(
    () => normalizeResearchActionCards(researchActionCards, t),
    [researchActionCards, t],
  );

  const researchReport = useMemo(() => extractResearchReport(entry), [entry]);
  const commercialIntelligence = useMemo(() => extractCommercialIntelligence(entry), [entry]);
  const groupedResearchSources = useMemo(
    () => buildGroupedResearchSources(researchReport, t),
    [researchReport, t],
  );
  const researchDiagnostics = researchReport?.source_diagnostics;
  const followupDiagnostics = researchReport?.followup_diagnostics;
  const reportReadiness = researchReport?.report_readiness;
  const commercialSummary = researchReport?.commercial_summary;
  const technicalAppendix = researchReport?.technical_appendix;
  const reviewQueue = researchReport?.review_queue || [];
  const guardedBacklog = isGuardedBacklog(researchDiagnostics);
  const guardedReasonLabels = dedupeTextList(getGuardedRewriteReasonLabels(researchDiagnostics));
  const supportedTargetAccounts = dedupeTextList(researchDiagnostics?.supported_target_accounts || []);
  const unsupportedTargetAccounts = dedupeTextList(researchDiagnostics?.unsupported_target_accounts || []);
  const followupFilters = dedupeTextList([
    ...(followupDiagnostics?.rebuilt_regions || []),
    ...(followupDiagnostics?.rebuilt_industries || []),
    ...(followupDiagnostics?.rebuilt_clients || []),
  ]);
  const followupImpactedSections = (followupDiagnostics?.impacted_sections || []).slice(0, 4);
  const followupTitleResolution = followupResolutionMeta(followupDiagnostics?.title_resolution);
  const followupSummaryResolution = followupResolutionMeta(followupDiagnostics?.summary_resolution);
  const candidateProfileCompanies = dedupeTextList(researchDiagnostics?.candidate_profile_companies || []);
  const candidateProfileSourceLabels = dedupeTextList(researchDiagnostics?.candidate_profile_source_labels || []);
  const reportSurfaceCopy = useMemo(() => buildReportSurfaceCopy(t), [t]);
  const pipelineStages = researchDiagnostics?.pipeline_stages || [];
  const evidenceMode = evidenceModeMeta(researchDiagnostics?.evidence_mode || "fallback", t);
  const diagnosticScopeLabels = dedupeTextList([
    ...(((researchDiagnostics?.scope_regions || []) as string[])),
    ...(((researchDiagnostics?.scope_industries || []) as string[])),
    ...(((researchDiagnostics?.scope_clients || []) as string[])),
  ]);
  const diagnosticCards = buildDiagnosticCards({
    researchDiagnostics,
    followupDiagnostics,
    followupFilters,
    diagnosticScopeLabels,
    unsupportedTargetAccounts,
    supportedTargetAccounts,
    guardedBacklog,
    reportReadiness,
    reviewQueue,
    guardedReasonLabels,
  });
  const rankedPanels = useMemo(() => buildRankedPanels(researchReport, t), [researchReport, t]);

  const triggerMarkdownDownload = (filename: string, content: string) => {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    let active = true;
    void listRelatedKnowledgeEntries(item.id, 4)
      .then((response) => {
        if (!active) return;
        setRelatedEntries(response.items || []);
      })
      .catch(() => {
        if (!active) return;
        setRelatedEntries([]);
      });
    return () => {
      active = false;
    };
  }, [item.id]);

  const markdownContent = useMemo(() => buildMarkdownContent(entry, t), [entry, t]);

  const handlePlanResearchActions = async () => {
    if (!researchReport) return;
    setPlanningResearchActions(true);
    setMessage("");
    try {
      const result = await createResearchActionPlan({ report: researchReport });
      setResearchActionCards(result.cards || []);
      setMessage(
        result.cards?.length
          ? t("research.actionsPlanned", "已生成研报行动卡")
          : t("research.actionsEmpty", "当前研报暂未生成可执行行动卡"),
      );
    } catch {
      setMessage(t("research.actionsPlanFailed", "生成行动卡失败，请稍后重试"));
    } finally {
      setPlanningResearchActions(false);
    }
  };

  const handleSaveResearchActions = async (asFocusReference = false) => {
    if (!researchReport || researchActionCards.length === 0) return;
    setSavingResearchActions(true);
    setMessage("");
    try {
      const result = await saveResearchActionCards({
        keyword: researchReport.keyword,
        cards: researchActionCards,
        collection_name: `${researchReport.keyword} 行动卡`,
        is_focus_reference: asFocusReference,
      });
      setMessage(
        asFocusReference
          ? t("research.actionsSavedToFocus", "行动卡已加入 Focus 参考")
          : t("research.actionsSaved", `已保存 ${result.created_count} 张行动卡`),
      );
    } catch {
      setMessage(t("research.actionsSaveFailed", "保存行动卡失败，请稍后重试"));
    } finally {
      setSavingResearchActions(false);
    }
  };

  const handleCopyMarkdown = async () => {
    setMessage("");
    try {
      await navigator.clipboard.writeText(markdownContent);
      setMessage(t("knowledge.copyMarkdownDone", "Markdown 已复制"));
    } catch {
      setMessage(t("knowledge.copyMarkdownFailed", "复制失败，请稍后重试"));
    }
  };

  const handleSave = async () => {
    if (!draftTitle.trim() || !draftContent.trim()) return;
    setSaving(true);
    setMessage("");
    try {
      const updated = await updateKnowledgeEntry(entry.id, {
        title: draftTitle.trim(),
        content: draftContent.trim(),
        collection_name: draftCollection.trim() || null,
      });
      setEntry(updated);
      setDraftTitle(updated.title);
      setDraftContent(updated.content);
      setDraftCollection(updated.collection_name || "");
      setEditing(false);
      setMessage(t("knowledge.editSaved", "知识卡片已保存"));
    } catch {
      setMessage(t("knowledge.editSaveFailed", "保存失败，请稍后重试"));
    } finally {
      setSaving(false);
    }
  };

  const handleTogglePinned = async () => {
    setPinning(true);
    setMessage("");
    try {
      const updated = await updateKnowledgeEntry(entry.id, {
        is_pinned: !entry.is_pinned,
      });
      setEntry(updated);
      setDraftCollection(updated.collection_name || "");
      setMessage(
        updated.is_pinned
          ? t("knowledge.pinEnabled", "已置顶这张知识卡片")
          : t("knowledge.pinDisabled", "已取消置顶"),
      );
    } catch {
      setMessage(t("knowledge.pinFailed", "置顶更新失败，请稍后重试"));
    } finally {
      setPinning(false);
    }
  };

  const handleReviewQueueAction = async (
    reviewId: string,
    action: "open" | "resolved" | "deferred",
  ) => {
    setReviewQueueActionId(reviewId);
    setMessage("");
    try {
      const updated = await resolveKnowledgeReviewQueueItem(entry.id, reviewId, { action });
      setEntry(updated);
      setMessage(
        action === "resolved"
          ? "已标记为已核验"
          : action === "deferred"
            ? "已延后处理"
            : "已重新打开审查项",
      );
    } catch {
      setMessage("审查队列更新失败，请稍后重试");
    } finally {
      setReviewQueueActionId("");
    }
  };

  const handleDownloadMarkdown = async () => {
    setExporting(true);
    setMessage("");
    try {
      const result = await getKnowledgeMarkdown(entry.id);
      triggerMarkdownDownload(result.filename, result.content);
      setMessage(t("knowledge.downloadDone", "Markdown 文件已下载"));
    } catch {
      triggerMarkdownDownload(`${entry.title || "knowledge-card"}.md`, markdownContent);
      setMessage(t("knowledge.downloadFallback", "已使用本地内容导出 Markdown"));
    } finally {
      setExporting(false);
    }
  };

  const handleWorkBuddyExport = async () => {
    setWorkBuddyExporting(true);
    setMessage("");
    try {
      const response = await sendWorkBuddyWebhook({
        event_type: "create_task",
        request_id: `knowledge_${entry.id}`,
        task_type: "export_knowledge_markdown",
        input_payload: {
          entry_id: entry.id,
        },
      });
      const content = response.task?.output_payload?.content;
      const filename =
        typeof response.task?.output_payload?.filename === "string"
          ? response.task.output_payload.filename
          : `${entry.title || "knowledge-card"}.md`;
      if (content) {
        triggerMarkdownDownload(filename, content);
      }
      setMessage(t("knowledge.workbuddyDone", "Markdown 已导出"));
    } catch {
      try {
        const task = await createTask({
          task_type: "export_knowledge_markdown",
          input_payload: {
            entry_id: entry.id,
          },
        });
        const content = String(task.output_payload?.content || markdownContent);
        const filename =
          typeof task.output_payload?.filename === "string"
            ? task.output_payload.filename
            : `${entry.title || "knowledge-card"}.md`;
        triggerMarkdownDownload(filename, content);
        setMessage(t("knowledge.workbuddyFallback", "已完成 Markdown 导出"));
      } catch {
        setMessage(t("knowledge.workbuddyFailed", "导出失败，请稍后重试"));
      }
    } finally {
      setWorkBuddyExporting(false);
    }
  };

  return (
    <div data-testid="knowledge-detail-card" className="af-knowledge-detail space-y-5">
      <KnowledgeDetailHeaderSection
        entry={entry}
        editing={editing}
        draftTitle={draftTitle}
        pinning={pinning}
        exporting={exporting}
        workBuddyExporting={workBuddyExporting}
        t={t}
        onDraftTitleChange={setDraftTitle}
        onTogglePinned={() => {
          void handleTogglePinned();
        }}
        onCopyMarkdown={() => {
          void handleCopyMarkdown();
        }}
        onDownloadMarkdown={() => {
          void handleDownloadMarkdown();
        }}
        onWorkBuddyExport={() => {
          void handleWorkBuddyExport();
        }}
      />

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("knowledge.content", "卡片内容")}</p>
        {researchReport ? (
          <div data-testid="knowledge-research-card" className="mt-3 space-y-4">
            <KnowledgeResearchReportBriefSection
              report={researchReport}
              diagnostics={researchDiagnostics}
              followupDiagnostics={followupDiagnostics}
              evidenceMode={evidenceMode}
              diagnosticCards={diagnosticCards}
              pipelineStages={pipelineStages}
              guardedBacklog={guardedBacklog}
              guardedReasonLabels={guardedReasonLabels}
              supportedTargetAccounts={supportedTargetAccounts}
              unsupportedTargetAccounts={unsupportedTargetAccounts}
              candidateProfileCompanies={candidateProfileCompanies}
              candidateProfileSourceLabels={candidateProfileSourceLabels}
              followupTitleResolution={followupTitleResolution}
              followupSummaryResolution={followupSummaryResolution}
              followupImpactedSections={followupImpactedSections}
              copy={reportSurfaceCopy}
              t={t}
            />

            <KnowledgeResearchReportReadinessSection
              reportReadiness={reportReadiness}
              commercialSummary={commercialSummary}
              copy={reportSurfaceCopy}
            />

            <ResearchActionCardsPanel
              t={t}
              title={t("research.actionCardsTitle", "下一步推进剧本")}
              subtitle={t("research.actionCardsHint", "把账户、销售、投标与生态判断拆成可执行动作。")}
              cards={uiResearchActionCards}
              planning={planningResearchActions}
              saving={savingResearchActions}
              onPlan={() => {
                void handlePlanResearchActions();
              }}
              onSave={() => {
                void handleSaveResearchActions(false);
              }}
              onSaveToFocus={() => {
                void handleSaveResearchActions(true);
              }}
            />

            <KnowledgeResearchReportMethodologySection commercialIntelligence={commercialIntelligence} />

            <KnowledgeResearchReportCommercialSection commercialIntelligence={commercialIntelligence} t={t} />

            <KnowledgeResearchReportInsightsSection
              report={researchReport}
              rankedPanels={rankedPanels}
              copy={reportSurfaceCopy}
              t={t}
            />

            <KnowledgeResearchReportReviewQueueSection
              reviewQueue={reviewQueue}
              reviewQueueActionId={reviewQueueActionId}
              copy={reportSurfaceCopy}
              onReviewQueueAction={(reviewId, action) => {
                void handleReviewQueueAction(reviewId, action);
              }}
            />

            <KnowledgeResearchReportSourceEvidenceSection
              groupedResearchSources={groupedResearchSources}
              copy={reportSurfaceCopy}
            />

            <KnowledgeResearchReportAppendixSection
              technicalAppendix={technicalAppendix}
              copy={reportSurfaceCopy}
            />
          </div>
        ) : null}
        <KnowledgeDetailContentEditor
          entry={entry}
          editing={editing}
          draftCollection={draftCollection}
          draftContent={draftContent}
          draftTitle={draftTitle}
          saving={saving}
          message={message}
          t={t}
          onDraftCollectionChange={setDraftCollection}
          onDraftContentChange={setDraftContent}
          onSave={() => {
            void handleSave();
          }}
        />
      </section>

      <KnowledgeDetailRelatedSection entry={entry} relatedEntries={relatedEntries} t={t} />

      <style jsx>{`
        .af-knowledge-detail :global(.af-glass) {
          background: var(--af-surface);
          border-color: var(--af-border-subtle);
          box-shadow: var(--af-shadow-soft);
          backdrop-filter: saturate(155%) blur(12px);
          -webkit-backdrop-filter: saturate(155%) blur(12px);
        }

        .af-knowledge-stage-grid {
          display: grid;
          gap: 0.625rem;
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .af-knowledge-stage-card {
          border-radius: 18px;
          border: 1px solid var(--af-border-subtle);
          background: var(--af-surface-elevated);
          padding: 0.7rem 0.75rem;
          box-shadow: var(--af-shadow-soft);
        }

        .af-knowledge-stage-value {
          margin-top: 0.2rem;
          font-size: 1.15rem;
          font-weight: 600;
          letter-spacing: -0.04em;
          color: var(--af-text-primary);
        }

        .af-knowledge-stage-summary {
          margin-top: 0.18rem;
          font-size: 0.7rem;
          line-height: 1.4;
          color: var(--af-text-tertiary);
        }

        @media (max-width: 720px) {
          .af-knowledge-stage-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}
