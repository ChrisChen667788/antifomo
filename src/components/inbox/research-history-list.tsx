"use client";

import Link from "next/link";
import { ApiKnowledgeEntry } from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

function buildResearchExcerpt(content: string) {
  const lines = String(content || "")
    .split("\n")
    .map((line) => line.replace(/^#+\s*/, "").replace(/^- /, "").trim())
    .filter(Boolean)
    .filter((line) => !line.startsWith("来源:") && !line.startsWith("创建时间:") && !line.startsWith("最近更新:"));
  const seed = lines.find((line) => line.length >= 16) || lines[0] || "";
  return seed.length > 96 ? `${seed.slice(0, 95).trim()}…` : seed;
}

type ResearchHistoryActionCard = {
  title: string;
  target_persona?: string;
  execution_window?: string;
  deliverable?: string;
  recommended_steps?: string[];
};

type ResearchHistoryActionPhase = {
  label: string;
  horizon: string;
  content: string;
};

function valueBucket(score: number | null | undefined) {
  if (typeof score !== "number") return "普通价值";
  if (score >= 75) return "高价值";
  if (score >= 55) return "普通价值";
  return "低价值";
}

function retrievalQualityLabel(level: string | null | undefined) {
  if (level === "high") return "高价值";
  if (level === "medium") return "普通价值";
  return "低价值";
}

function evidenceModeMeta(mode: string | null | undefined) {
  if (mode === "strong") return { label: "强证据", className: "bg-emerald-50 text-emerald-700" };
  if (mode === "provisional") return { label: "可用初版", className: "bg-amber-50 text-amber-700" };
  return { label: "兜底候选", className: "bg-slate-100 text-slate-600" };
}

function normalizeList(values: unknown): string[] {
  return Array.isArray(values)
    ? values.map((value) => String(value || "").trim()).filter(Boolean)
    : [];
}

function conciseEntityName(value: string): string {
  const normalized = String(value || "").trim();
  if (!normalized) return "";
  const primary = normalized.split(/[：:]/)[0]?.trim() || normalized;
  return primary.split(/\s*[·•|｜]\s*/)[0]?.trim() || primary;
}

function parseActionPhases(steps: string[] | undefined): ResearchHistoryActionPhase[] {
  return normalizeList(steps)
    .map((step) => {
      const match = step.match(/^(短期|中期|长期|Short term|Mid term|Long term)(?:（([^）]+)）|\(([^)]+)\))?[:：]\s*(.+)$/i);
      if (!match) {
        return {
          label: "关键动作",
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

function extractResearchMetadata(entry: ApiKnowledgeEntry): {
  summary: string;
  topTargets: string[];
  topCompetitors: string[];
  topPartners: string[];
  actionCards: ResearchHistoryActionCard[];
  diagnostics: {
    scopeRegions: string[];
    scopeIndustries: string[];
    scopeClients: string[];
    topicAnchors: string[];
    matchedThemes: string[];
    filteredOldSourceCount: number;
    filteredRegionConflictCount: number;
    retrievalQuality: string;
    evidenceMode: string;
    officialSourcePercent: number;
    uniqueDomainCount: number;
    normalizedEntityCount: number;
    correctiveTriggered: boolean;
  };
} {
  const payload = entry.metadata_payload;
  if (!payload || typeof payload !== "object") {
    return {
      summary: buildResearchExcerpt(entry.content),
      topTargets: [],
      topCompetitors: [],
      topPartners: [],
        actionCards: [],
        diagnostics: {
        scopeRegions: [],
        scopeIndustries: [],
        scopeClients: [],
        topicAnchors: [],
        matchedThemes: [],
        filteredOldSourceCount: 0,
        filteredRegionConflictCount: 0,
        retrievalQuality: "low",
        evidenceMode: "fallback",
        officialSourcePercent: 0,
        uniqueDomainCount: 0,
        normalizedEntityCount: 0,
        correctiveTriggered: false,
      },
    };
  }

  const typedPayload = payload as {
    report?: {
      executive_summary?: string;
      target_accounts?: string[];
      competitor_profiles?: string[];
      ecosystem_partners?: string[];
      source_diagnostics?: {
        topic_anchor_terms?: string[];
        matched_theme_labels?: string[];
        filtered_old_source_count?: number;
        filtered_region_conflict_count?: number;
        retrieval_quality?: "low" | "medium" | "high";
        official_source_ratio?: number;
        unique_domain_count?: number;
        normalized_entity_count?: number;
      };
      top_target_accounts?: Array<{ name?: string; score?: number | null }>;
      top_competitors?: Array<{ name?: string; score?: number | null }>;
      top_ecosystem_partners?: Array<{ name?: string; score?: number | null }>;
      pending_target_candidates?: Array<{ name?: string; score?: number | null }>;
      pending_competitor_candidates?: Array<{ name?: string; score?: number | null }>;
      pending_partner_candidates?: Array<{ name?: string; score?: number | null }>;
    };
    action_cards?: Array<{
      title?: string;
      target_persona?: string;
      execution_window?: string;
      deliverable?: string;
      recommended_steps?: string[];
    }>;
  };

  const report = typedPayload.report || {};
  const summary = String(report.executive_summary || "").trim() || buildResearchExcerpt(entry.content);

  const buildRanked = (
    ranked: Array<{ name?: string; score?: number | null }> | undefined,
    pending: Array<{ name?: string; score?: number | null }> | undefined,
  ) =>
    (Array.isArray(ranked) && ranked.length
      ? ranked.map((item) => `${conciseEntityName(String(item.name || ""))} · ${valueBucket(item.score)}`)
      : Array.isArray(pending) && pending.length
        ? pending.map((item) => `${conciseEntityName(String(item.name || ""))} · 待补证`)
        : []
    )
      .map((item) => {
        const normalized = String(item || "").trim();
        if (!normalized) return "";
        if (normalized.includes("·")) return normalized;
        return conciseEntityName(normalized);
      })
      .filter(Boolean)
      .slice(0, 3);

  const actionCards = (typedPayload.action_cards || [])
    .map((card) => ({
      title: String(card.title || "").trim(),
      target_persona: String(card.target_persona || "").trim(),
      execution_window: String(card.execution_window || "").trim(),
      deliverable: String(card.deliverable || "").trim(),
      recommended_steps: normalizeList(card.recommended_steps),
    }))
    .filter((card) => card.title)
    .slice(0, 2);

  return {
    summary,
    topTargets: buildRanked(report.top_target_accounts, report.pending_target_candidates),
    topCompetitors: buildRanked(report.top_competitors, report.pending_competitor_candidates),
    topPartners: buildRanked(report.top_ecosystem_partners, report.pending_partner_candidates),
    actionCards,
    diagnostics: {
      scopeRegions: normalizeList((report.source_diagnostics as { scope_regions?: string[] } | undefined)?.scope_regions).slice(0, 2),
      scopeIndustries: normalizeList((report.source_diagnostics as { scope_industries?: string[] } | undefined)?.scope_industries).slice(0, 2),
      scopeClients: normalizeList((report.source_diagnostics as { scope_clients?: string[] } | undefined)?.scope_clients).slice(0, 2),
      topicAnchors: normalizeList(report.source_diagnostics?.topic_anchor_terms).slice(0, 3),
      matchedThemes: normalizeList(report.source_diagnostics?.matched_theme_labels).slice(0, 3),
      filteredOldSourceCount: Number(report.source_diagnostics?.filtered_old_source_count || 0),
      filteredRegionConflictCount: Number((report.source_diagnostics as { filtered_region_conflict_count?: number } | undefined)?.filtered_region_conflict_count || 0),
      retrievalQuality: String(report.source_diagnostics?.retrieval_quality || "low"),
      evidenceMode: String((report.source_diagnostics as { evidence_mode?: string } | undefined)?.evidence_mode || "fallback"),
      officialSourcePercent: Math.round(Number(report.source_diagnostics?.official_source_ratio || 0) * 100),
      uniqueDomainCount: Number(report.source_diagnostics?.unique_domain_count || 0),
      normalizedEntityCount: Number(report.source_diagnostics?.normalized_entity_count || 0),
      correctiveTriggered: Boolean((report.source_diagnostics as { corrective_triggered?: boolean } | undefined)?.corrective_triggered),
    },
  };
}

export function ResearchHistoryList({ items }: { items: ApiKnowledgeEntry[] }) {
  const { t } = useAppPreferences();

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-7">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">{t("inbox.researchHistory", "最近研报")}</p>
          <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
            {t("inbox.researchHistory", "最近研报")}
          </h3>
          <p className="mt-2 text-sm text-slate-500">
            {t(
              "inbox.researchHistoryDesc",
              "已保存的关键词研报会在这里沉淀，便于继续深读和复用。",
            )}
          </p>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-white/55 p-4 text-sm text-slate-500">
          {t("inbox.researchHistoryEmpty", "还没有保存的研报，先生成一份再加入知识库。")}
        </div>
      ) : (
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            (() => {
              const meta = extractResearchMetadata(item);
              const evidenceMeta = evidenceModeMeta(meta.diagnostics.evidenceMode);
              return (
                <article
                  key={item.id}
                  className="rounded-2xl border border-white/80 bg-white/60 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h4 className="min-w-0 flex-1 text-base font-semibold leading-7 text-slate-900">
                      {item.title}
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {item.is_focus_reference ? (
                        <span className="rounded-full bg-sky-100 px-2.5 py-1 text-xs font-medium text-sky-700">
                          {t("inbox.researchHistoryFocus", "Focus 参考")}
                        </span>
                      ) : null}
                      {item.collection_name ? (
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                          {t("inbox.researchHistoryCollection", "分组")} · {item.collection_name}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  <p className="mt-3 text-sm leading-6 text-slate-600">{meta.summary}</p>

                  {(meta.diagnostics.scopeRegions.length ||
                    meta.diagnostics.scopeIndustries.length ||
                    meta.diagnostics.scopeClients.length ||
                    meta.diagnostics.topicAnchors.length ||
                    meta.diagnostics.matchedThemes.length ||
                    meta.diagnostics.filteredOldSourceCount > 0 ||
                    meta.diagnostics.filteredRegionConflictCount > 0 ||
                    meta.diagnostics.uniqueDomainCount > 0 ||
                    meta.diagnostics.normalizedEntityCount > 0) ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${evidenceMeta.className}`}>
                        {evidenceMeta.label}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-600">
                        检索质量 {retrievalQualityLabel(meta.diagnostics.retrievalQuality)}
                      </span>
                      <span className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                        官方源 {meta.diagnostics.officialSourcePercent}%
                      </span>
                      {meta.diagnostics.uniqueDomainCount > 0 ? (
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-600">
                          域名 {meta.diagnostics.uniqueDomainCount}
                        </span>
                      ) : null}
                      {meta.diagnostics.normalizedEntityCount > 0 ? (
                        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                          归一化实体 {meta.diagnostics.normalizedEntityCount}
                        </span>
                      ) : null}
                      {meta.diagnostics.scopeRegions.map((value) => (
                        <span key={`${item.id}-scope-region-${value}`} className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] text-cyan-700">
                          区域 · {value}
                        </span>
                      ))}
                      {meta.diagnostics.scopeIndustries.map((value) => (
                        <span key={`${item.id}-scope-industry-${value}`} className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] text-blue-700">
                          领域 · {value}
                        </span>
                      ))}
                      {meta.diagnostics.scopeClients.map((value) => (
                        <span key={`${item.id}-scope-client-${value}`} className="rounded-full bg-fuchsia-50 px-2.5 py-1 text-[11px] text-fuchsia-700">
                          公司 · {value}
                        </span>
                      ))}
                      {meta.diagnostics.topicAnchors.map((value) => (
                        <span key={`${item.id}-anchor-${value}`} className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] text-violet-700">
                          {value}
                        </span>
                      ))}
                      {meta.diagnostics.matchedThemes.map((value) => (
                        <span key={`${item.id}-theme-${value}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                          {value}
                        </span>
                      ))}
                      {meta.diagnostics.filteredOldSourceCount > 0 ? (
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-500">
                          剔除过旧来源 {meta.diagnostics.filteredOldSourceCount}
                        </span>
                      ) : null}
                      {meta.diagnostics.filteredRegionConflictCount > 0 ? (
                        <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] text-rose-700">
                          拦截越界区域 {meta.diagnostics.filteredRegionConflictCount}
                        </span>
                      ) : null}
                      {meta.diagnostics.correctiveTriggered ? (
                        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] text-amber-700">
                          已触发纠错检索
                        </span>
                      ) : null}
                    </div>
                  ) : null}

                  {meta.actionCards.length ? (
                    <div className="mt-4 grid gap-3">
                      {meta.actionCards.map((card) => (
                        <div
                          key={`${item.id}-${card.title}`}
                          className="rounded-2xl border border-slate-200/80 bg-white/85 p-3"
                        >
                          <div className="break-words text-sm font-semibold leading-6 text-slate-900">{card.title}</div>
                          <div className="mt-2 grid gap-2 text-xs text-slate-500">
                            {card.target_persona ? (
                              <div className="rounded-2xl border border-slate-200/70 bg-slate-50/80 px-3 py-2 break-words">
                                <span className="font-medium text-slate-700">{t("research.actionTarget", "优先对象")}：</span>
                                {card.target_persona}
                              </div>
                            ) : null}
                            {card.execution_window ? (
                              <div className="rounded-2xl border border-slate-200/70 bg-slate-50/80 px-3 py-2 break-words">
                                <span className="font-medium text-slate-700">{t("research.actionWindow", "执行窗口")}：</span>
                                {card.execution_window}
                              </div>
                            ) : null}
                            {card.deliverable ? (
                              <div className="rounded-2xl border border-slate-200/70 bg-slate-50/80 px-3 py-2 break-words">
                                <span className="font-medium text-slate-700">{t("research.actionDeliverable", "产出物")}：</span>
                                {card.deliverable}
                              </div>
                            ) : null}
                          </div>
                          {parseActionPhases(card.recommended_steps).length ? (
                            <div className="mt-3 grid gap-2">
                              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                                {t("research.actionTimeline", "推进节奏")}
                              </div>
                              <div className="grid gap-2">
                                {parseActionPhases(card.recommended_steps).map((phase) => (
                                  <div
                                    key={`${card.title}-${phase.label}-${phase.content}`}
                                    className="min-w-0 overflow-hidden rounded-2xl border border-slate-200/70 bg-slate-50/70 px-3 py-2.5"
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-medium text-white">
                                        {phase.label}
                                      </span>
                                      {phase.horizon ? (
                                        <span className="text-[11px] font-medium text-slate-500">{phase.horizon}</span>
                                      ) : null}
                                    </div>
                                    <div className="mt-2 min-w-0 break-words whitespace-pre-wrap text-xs leading-5 text-slate-600 [overflow-wrap:anywhere]">
                                      {phase.content}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {(meta.topTargets.length || meta.topCompetitors.length || meta.topPartners.length) ? (
                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                      {meta.topTargets.length ? (
                        <div className="rounded-2xl border border-sky-100/90 bg-sky-50/80 p-3">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-600">
                            高价值甲方
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {meta.topTargets.map((value) => (
                              <span key={value} className="rounded-full bg-white px-2.5 py-1 text-xs text-sky-900">
                                {value}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {meta.topCompetitors.length ? (
                        <div className="rounded-2xl border border-amber-100/90 bg-amber-50/80 p-3">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-600">
                            高威胁竞品
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {meta.topCompetitors.map((value) => (
                              <span key={value} className="rounded-full bg-white px-2.5 py-1 text-xs text-amber-900">
                                {value}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {meta.topPartners.length ? (
                        <div className="rounded-2xl border border-emerald-100/90 bg-emerald-50/80 p-3">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-600">
                            高影响力伙伴
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {meta.topPartners.map((value) => (
                              <span key={value} className="rounded-full bg-white px-2.5 py-1 text-xs text-emerald-900">
                                {value}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="mt-4 flex items-center justify-between gap-3 text-xs text-slate-400">
                    <span>{new Date(item.created_at).toLocaleString()}</span>
                    <Link
                      href={`/knowledge/${item.id}`}
                      className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
                    >
                      {t("inbox.researchHistoryOpen", "打开知识卡片")}
                    </Link>
                  </div>
                </article>
              );
            })()
          ))}
        </div>
      )}
    </section>
  );
}
