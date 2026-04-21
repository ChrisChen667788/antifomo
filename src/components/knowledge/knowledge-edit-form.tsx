"use client";

import Link from "next/link";
import { useState } from "react";
import type { ApiKnowledgeEntry, ApiResearchActionCard } from "@/lib/api";
import { updateKnowledgeEntry } from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";

type ActionCardDraft = {
  action_type: string;
  priority: string;
  summary: string;
  recommended_steps_text: string;
  evidence_text: string;
  target_persona: string;
  execution_window: string;
  deliverable: string;
};

function isResearchActionEntry(entry: ApiKnowledgeEntry): boolean {
  return entry.metadata_payload?.kind === "research_action_card";
}

function toMultilineText(items: string[] | undefined): string {
  return Array.isArray(items) ? items.filter(Boolean).join("\n") : "";
}

function normalizeLines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 8);
}

function getActionCard(entry: ApiKnowledgeEntry): ApiResearchActionCard {
  const payload = (entry.metadata_payload as { card?: ApiResearchActionCard } | null)?.card;
  return {
    action_type: payload?.action_type || "sales_strategy",
    priority: payload?.priority || "medium",
    title: payload?.title || entry.title,
    summary: payload?.summary || entry.content,
    recommended_steps: payload?.recommended_steps || [],
    evidence: payload?.evidence || [],
    target_persona: payload?.target_persona || "",
    execution_window: payload?.execution_window || "",
    deliverable: payload?.deliverable || "",
  };
}

function buildActionDraft(entry: ApiKnowledgeEntry): ActionCardDraft {
  const card = getActionCard(entry);
  return {
    action_type: card.action_type,
    priority: card.priority,
    summary: card.summary,
    recommended_steps_text: toMultilineText(card.recommended_steps),
    evidence_text: toMultilineText(card.evidence),
    target_persona: card.target_persona || "",
    execution_window: card.execution_window || "",
    deliverable: card.deliverable || "",
  };
}

function buildActionCardContent(card: ApiResearchActionCard): string {
  const lines = [
    `行动摘要：${card.summary}`,
    "",
    `优先级：${card.priority}`,
  ];
  if (card.target_persona) {
    lines.push(`目标对象：${card.target_persona}`);
  }
  if (card.execution_window) {
    lines.push(`执行窗口：${card.execution_window}`);
  }
  if (card.deliverable) {
    lines.push(`交付物：${card.deliverable}`);
  }
  lines.push("", "建议步骤：");
  lines.push(...(card.recommended_steps.length ? card.recommended_steps.map((step) => `- ${step}`) : ["- 暂无补充步骤"]));
  if (card.evidence.length) {
    lines.push("", "参考依据：");
    lines.push(...card.evidence.map((item) => `- ${item}`));
  }
  return lines.join("\n").trim();
}

function buildActionMetadata(
  entry: ApiKnowledgeEntry,
  title: string,
  draft: ActionCardDraft,
): Record<string, unknown> {
  const previous = (entry.metadata_payload as Record<string, unknown> | null) || {};
  return {
    ...previous,
    kind: "research_action_card",
    card: {
      action_type: draft.action_type,
      priority: draft.priority,
      title,
      summary: draft.summary.trim(),
      recommended_steps: normalizeLines(draft.recommended_steps_text),
      evidence: normalizeLines(draft.evidence_text),
      target_persona: draft.target_persona.trim(),
      execution_window: draft.execution_window.trim(),
      deliverable: draft.deliverable.trim(),
    },
  };
}

export function KnowledgeEditForm({ item }: { item: ApiKnowledgeEntry }) {
  const { t } = useAppPreferences();
  const [entry, setEntry] = useState(item);
  const [draftTitle, setDraftTitle] = useState(item.title);
  const [draftContent, setDraftContent] = useState(item.content);
  const [draftCollection, setDraftCollection] = useState(item.collection_name || "");
  const [draftPinned, setDraftPinned] = useState(!!item.is_pinned);
  const [draftFocusRef, setDraftFocusRef] = useState(!!item.is_focus_reference);
  const [actionDraft, setActionDraft] = useState<ActionCardDraft>(() => buildActionDraft(item));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const actionEntry = isResearchActionEntry(entry);
  const actionTypeOptions = [
    { value: "industry_intelligence", label: t("research.actionTypeIndustry", "行业情报") },
    { value: "solution_design", label: t("research.actionTypeSolution", "方案设计") },
    { value: "sales_strategy", label: t("research.actionTypeSales", "销售推进") },
    { value: "bidding_strategy", label: t("research.actionTypeBidding", "投标规划") },
    { value: "outreach_strategy", label: t("research.actionTypeOutreach", "陌生拜访") },
    { value: "ecosystem_strategy", label: t("research.actionTypeEcosystem", "生态合作") },
  ];
  const priorityOptions = [
    { value: "high", label: t("research.priorityHigh", "高优先级") },
    { value: "medium", label: t("research.priorityMedium", "中优先级") },
    { value: "low", label: t("research.priorityLow", "低优先级") },
  ];

  const previewCard: ApiResearchActionCard = {
    action_type: actionDraft.action_type,
    priority: actionDraft.priority,
    title: draftTitle.trim() || entry.title,
    summary: actionDraft.summary.trim(),
    recommended_steps: normalizeLines(actionDraft.recommended_steps_text),
    evidence: normalizeLines(actionDraft.evidence_text),
    target_persona: actionDraft.target_persona.trim(),
    execution_window: actionDraft.execution_window.trim(),
    deliverable: actionDraft.deliverable.trim(),
  };
  const previewContent = actionEntry ? buildActionCardContent(previewCard) : draftContent;

  const handleSave = async () => {
    if (!draftTitle.trim()) {
      setMessage(t("knowledge.editValidation", "标题和内容都需要保留，避免生成空卡片。"));
      return;
    }

    if (actionEntry) {
      if (!actionDraft.summary.trim()) {
        setMessage(t("research.actionSummaryRequired", "行动摘要不能为空。"));
        return;
      }
    } else if (!draftContent.trim()) {
      setMessage(t("knowledge.editValidation", "标题和内容都需要保留，避免生成空卡片。"));
      return;
    }

    const nextMetadata = actionEntry
      ? buildActionMetadata(entry, draftTitle.trim(), actionDraft)
      : entry.metadata_payload ?? null;
    const nextContent = actionEntry ? previewContent : draftContent.trim();

    setSaving(true);
    setMessage("");
    try {
      const updated = await updateKnowledgeEntry(entry.id, {
        title: draftTitle.trim(),
        content: nextContent,
        collection_name: draftCollection.trim() || null,
        is_pinned: draftPinned,
        is_focus_reference: draftFocusRef,
        metadata_payload: nextMetadata,
      });
      setEntry(updated);
      setDraftTitle(updated.title);
      setDraftContent(updated.content);
      setDraftCollection(updated.collection_name || "");
      setDraftPinned(!!updated.is_pinned);
      setDraftFocusRef(!!updated.is_focus_reference);
      if (isResearchActionEntry(updated)) {
        setActionDraft(buildActionDraft(updated));
      }
      setMessage(
        actionEntry
          ? t("research.actionEditSaved", "行动卡模板已保存")
          : t("knowledge.editSaved", "知识卡片已保存"),
      );
    } catch {
      setMessage(t("knowledge.editSaveFailed", "保存失败，请稍后重试"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">
          {actionEntry ? t("research.actionCards", "行动卡") : t("knowledge.title", "知识卡片")}
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
          {actionEntry ? t("research.actionEdit", "编辑行动卡") : t("knowledge.edit", "编辑")}
        </h2>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          {actionEntry
            ? t("research.actionEditHint", "直接调整行动对象、执行窗口、步骤与证据，系统会自动重建行动卡正文。")
            : t("knowledge.subtitle", "将沉淀下来的结构化理解整理成可复用记录。")}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setDraftPinned((value) => !value)}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${
              draftPinned ? "border-sky-200 bg-sky-100 text-sky-700" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            <AppIcon name="flag" className="h-4 w-4" />
            {t("knowledge.pin", "置顶")}
          </button>
          <button
            type="button"
            onClick={() => setDraftFocusRef((value) => !value)}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${
              draftFocusRef
                ? "border-indigo-200 bg-indigo-100 text-indigo-700"
                : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            <AppIcon name="focus" className="h-4 w-4" />
            {t("knowledge.focusRef", "Focus 参考")}
          </button>
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <div className="grid gap-4 lg:grid-cols-2">
          <label className="block lg:col-span-2">
            <span className="af-kicker">
              {actionEntry ? t("research.actionTitle", "行动卡标题") : t("knowledge.title", "知识卡片")}
            </span>
            <input
              value={draftTitle}
              onChange={(event) => setDraftTitle(event.target.value)}
              className="af-input mt-2 w-full bg-white/80 text-slate-900"
            />
          </label>
          <label className="block">
            <span className="af-kicker">{t("knowledge.group", "分组")}</span>
            <input
              value={draftCollection}
              onChange={(event) => setDraftCollection(event.target.value)}
              placeholder={t("knowledge.groupPlaceholder", "输入分组名称，例如：AI 制药")}
              className="af-input mt-2 w-full bg-white/80 text-slate-700"
            />
          </label>
          {actionEntry ? (
            <label className="block">
              <span className="af-kicker">{t("research.centerActionTypeLabel", "动作类型")}</span>
              <select
                value={actionDraft.action_type}
                onChange={(event) =>
                  setActionDraft((current) => ({ ...current, action_type: event.target.value }))
                }
                className="af-input mt-2 w-full bg-white/80 text-slate-700"
              >
                {actionTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {actionEntry ? (
            <>
              <label className="block">
                <span className="af-kicker">{t("research.actionPriority", "优先级")}</span>
                <select
                  value={actionDraft.priority}
                  onChange={(event) =>
                    setActionDraft((current) => ({ ...current, priority: event.target.value }))
                  }
                  className="af-input mt-2 w-full bg-white/80 text-slate-700"
                >
                  {priorityOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="af-kicker">{t("research.actionTargetPersona", "目标对象")}</span>
                <input
                  value={actionDraft.target_persona}
                  onChange={(event) =>
                    setActionDraft((current) => ({ ...current, target_persona: event.target.value }))
                  }
                  className="af-input mt-2 w-full bg-white/80 text-slate-700"
                />
              </label>
              <label className="block">
                <span className="af-kicker">{t("research.actionWindow", "执行窗口")}</span>
                <input
                  value={actionDraft.execution_window}
                  onChange={(event) =>
                    setActionDraft((current) => ({ ...current, execution_window: event.target.value }))
                  }
                  className="af-input mt-2 w-full bg-white/80 text-slate-700"
                />
              </label>
              <label className="block">
                <span className="af-kicker">{t("research.actionDeliverable", "交付物")}</span>
                <input
                  value={actionDraft.deliverable}
                  onChange={(event) =>
                    setActionDraft((current) => ({ ...current, deliverable: event.target.value }))
                  }
                  className="af-input mt-2 w-full bg-white/80 text-slate-700"
                />
              </label>
              <label className="block lg:col-span-2">
                <span className="af-kicker">{t("research.actionSummary", "行动摘要")}</span>
                <textarea
                  value={actionDraft.summary}
                  onChange={(event) =>
                    setActionDraft((current) => ({ ...current, summary: event.target.value }))
                  }
                  rows={4}
                  className="af-input mt-2 w-full bg-white/80 text-sm leading-7 text-slate-700"
                />
              </label>
              <label className="block">
                <span className="af-kicker">{t("research.actionSteps", "建议步骤")}</span>
                <textarea
                  value={actionDraft.recommended_steps_text}
                  onChange={(event) =>
                    setActionDraft((current) => ({
                      ...current,
                      recommended_steps_text: event.target.value,
                    }))
                  }
                  rows={8}
                  className="af-input mt-2 w-full bg-white/80 text-sm leading-7 text-slate-700"
                />
                <p className="mt-2 text-xs text-slate-500">
                  {t("research.actionLineHint", "每行一条，保存时会自动整理成列表。")}
                </p>
              </label>
              <label className="block">
                <span className="af-kicker">{t("research.actionEvidence", "参考依据")}</span>
                <textarea
                  value={actionDraft.evidence_text}
                  onChange={(event) =>
                    setActionDraft((current) => ({ ...current, evidence_text: event.target.value }))
                  }
                  rows={8}
                  className="af-input mt-2 w-full bg-white/80 text-sm leading-7 text-slate-700"
                />
                <p className="mt-2 text-xs text-slate-500">
                  {t("research.actionEvidenceHint", "每行一条，保留关键证据或竞争线索。")}
                </p>
              </label>
              <div className="rounded-[26px] border border-white/80 bg-white/70 p-4 lg:col-span-2">
                <p className="af-kicker">{t("research.actionPreview", "正文预览")}</p>
                <pre className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">
                  {previewContent}
                </pre>
              </div>
            </>
          ) : (
            <label className="block lg:col-span-2">
              <span className="af-kicker">{t("knowledge.content", "卡片内容")}</span>
              <textarea
                value={draftContent}
                onChange={(event) => setDraftContent(event.target.value)}
                rows={14}
                className="af-input mt-2 w-full bg-white/80 text-sm leading-7 text-slate-700"
              />
            </label>
          )}
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              void handleSave();
            }}
            disabled={saving}
            className="af-btn af-btn-primary border px-5 py-2.5 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <AppIcon name="bookmark" className="h-4 w-4" />
            {saving ? t("common.saving", "保存中...") : t("common.save", "保存")}
          </button>
          <Link href={`/knowledge/${entry.id}`} className="af-btn af-btn-secondary border px-5 py-2.5">
            <AppIcon name="knowledge" className="h-4 w-4" />
            {t("knowledge.openRelated", "查看卡片")}
          </Link>
          {entry.item_id ? (
            <Link href={`/items/${entry.item_id}`} className="af-btn af-btn-secondary border px-5 py-2.5">
              <AppIcon name="external" className="h-4 w-4" />
              {t("knowledge.openItem", "打开原内容详情")}
            </Link>
          ) : null}
        </div>
        {message ? <p className="mt-3 text-sm text-slate-500">{message}</p> : null}
      </section>
    </div>
  );
}
