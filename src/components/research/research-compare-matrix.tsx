"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AppIcon } from "@/components/ui/app-icon";
import { listKnowledgeEntries, type ApiKnowledgeEntry } from "@/lib/api";
import { buildResearchCompareRows, type ResearchCompareRole } from "@/lib/research-compare";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

type CompareRoleFilter = "all" | ResearchCompareRole;

function sourceTierLabel(tier: "official" | "media" | "aggregate", t: (key: string, fallback: string) => string) {
  if (tier === "official") return t("research.sourceOfficial", "官方源");
  if (tier === "aggregate") return t("research.sourceAggregate", "聚合源");
  return t("research.sourceMedia", "媒体源");
}

function sortEntries(items: ApiKnowledgeEntry[]): ApiKnowledgeEntry[] {
  return [...items].sort((left, right) => {
    const leftTime = new Date(left.updated_at || left.created_at).getTime();
    const rightTime = new Date(right.updated_at || right.created_at).getTime();
    return rightTime - leftTime;
  });
}

export function ResearchCompareMatrix({
  initialQuery = "",
  initialRegion = "",
  initialIndustry = "",
}: {
  initialQuery?: string;
  initialRegion?: string;
  initialIndustry?: string;
}) {
  const { t } = useAppPreferences();
  const [entries, setEntries] = useState<ApiKnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState(initialQuery);
  const [regionFilter, setRegionFilter] = useState(initialRegion);
  const [industryFilter, setIndustryFilter] = useState(initialIndustry);
  const [roleFilter, setRoleFilter] = useState<CompareRoleFilter>("all");

  useEffect(() => {
    let active = true;
    setLoading(true);
    listKnowledgeEntries(80, {
      sourceDomain: "research.report",
      query: initialQuery || undefined,
    })
      .then((response) => {
        if (!active) return;
        setEntries(sortEntries(response.items || []));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [initialQuery]);

  const rows = useMemo(() => buildResearchCompareRows(entries), [entries]);
  const regionOptions = useMemo(
    () => ["", ...new Set(rows.map((row) => row.region).filter(Boolean))],
    [rows],
  );
  const industryOptions = useMemo(
    () => ["", ...new Set(rows.map((row) => row.industry).filter(Boolean))],
    [rows],
  );

  const visibleRows = useMemo(
    () =>
      rows.filter((row) => {
        if (roleFilter !== "all" && row.role !== roleFilter) return false;
        if (regionFilter && row.region !== regionFilter) return false;
        if (industryFilter && row.industry !== industryFilter) return false;
        if (query) {
          const haystack = [
            row.name,
            row.clue,
            row.keyword,
            row.sourceEntryTitle,
            ...(row.targetDepartments || []),
            ...(row.publicContacts || []),
            ...(row.competitorHighlights || []),
            ...(row.partnerHighlights || []),
            ...(row.benchmarkCases || []),
          ]
            .join(" ")
            .toLowerCase();
          if (!haystack.includes(query.toLowerCase())) return false;
        }
        return true;
      }),
    [rows, roleFilter, regionFilter, industryFilter, query],
  );

  const roleStats = useMemo(
    () =>
      ["甲方", "中标方", "竞品", "伙伴"].map((role) => ({
        role,
        count: rows.filter((row) => row.role === role).length,
      })),
    [rows],
  );

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[34px] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <p className="af-kicker">{t("research.compareKicker", "Compare Matrix")}</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900 md:text-[2rem]">
              {t("research.compareTitle", "甲方 / 中标方 / 竞品 / 伙伴 对比矩阵")}
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-500 md:text-[15px]">
              {t(
                "research.compareDesc",
                "把多份研报里的甲方、中标方、竞品和伙伴线索拉平对比，优先看预算、项目、战略和竞争压力。",
              )}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/research" className="af-btn af-btn-secondary border px-4 py-2">
              {t("research.compareBack", "返回研报中心")}
            </Link>
          </div>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {roleStats.map((item) => (
            <div key={item.role} className="rounded-[24px] border border-white/60 bg-white/72 p-4 shadow-[0_14px_32px_rgba(15,23,42,0.06)]">
              <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">{item.role}</p>
              <p className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-slate-900">{item.count}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1.4fr),repeat(3,minmax(0,0.8fr))]">
          <div className="flex items-center gap-2 rounded-[20px] border border-white/60 bg-white/70 px-3 py-2 shadow-[0_10px_30px_rgba(15,23,42,0.05)]">
            <AppIcon name="search" className="h-4 w-4 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("research.compareSearchPlaceholder", "搜索公司名、甲方、竞品、伙伴...")}
              className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
            />
          </div>
          <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value as CompareRoleFilter)} className="af-input bg-white/70">
            <option value="all">{t("research.compareRoleAll", "全部角色")}</option>
            <option value="甲方">甲方</option>
            <option value="中标方">中标方</option>
            <option value="竞品">竞品</option>
            <option value="伙伴">伙伴</option>
          </select>
          <select value={regionFilter} onChange={(event) => setRegionFilter(event.target.value)} className="af-input bg-white/70">
            <option value="">{t("research.centerRegionAll", "全部区域")}</option>
            {regionOptions.filter(Boolean).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select value={industryFilter} onChange={(event) => setIndustryFilter(event.target.value)} className="af-input bg-white/70">
            <option value="">{t("research.centerIndustryAll", "全部行业")}</option>
            {industryOptions.filter(Boolean).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      </section>

      {loading ? (
        <section className="af-glass rounded-[30px] p-5 text-sm text-slate-500">{t("common.loading", "加载中")}</section>
      ) : null}

      {!loading && visibleRows.length === 0 ? (
        <section className="af-glass rounded-[30px] p-5 text-sm text-slate-500">
          {t("research.compareEmpty", "当前没有可用于对比的实体线索。")}
        </section>
      ) : null}

      {!loading && visibleRows.length ? (
        <section className="space-y-3">
          {visibleRows.map((row) => (
            <article
              key={row.id}
              className="af-glass rounded-[28px] p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_20px_45px_rgba(15,23,42,0.08)]"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-semibold text-white/90">
                      {row.role}
                    </span>
                    {row.region ? <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">{row.region}</span> : null}
                    {row.industry ? <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">{row.industry}</span> : null}
                  </div>
                  <h3 className="mt-3 text-xl font-semibold tracking-[-0.03em] text-slate-900">{row.name}</h3>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{row.clue}</p>
                </div>
                <Link href={`/knowledge/${row.sourceEntryId}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-sm">
                  {t("research.compareOpenSource", "打开来源研报")}
                </Link>
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-4">
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.compareBudget", "预算信号")}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{row.budgetSignal}</p>
                  <p className="mt-3 text-xs text-slate-500">
                    {t("research.compareBudgetRange", "预算区间")} · {row.budgetRange}
                  </p>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.compareProject", "项目/招采")}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{row.projectSignal}</p>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.compareStrategy", "战略/讲话")}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{row.strategySignal}</p>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.compareCompetition", "竞合压力")}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{row.competitionSignal}</p>
                </div>
              </div>
              <div className="mt-4 grid gap-3 xl:grid-cols-5">
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareDepartments", "高概率决策部门")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.targetDepartments.length ? (
                      row.targetDepartments.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoDepartments", "暂无明确部门线索")}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareContacts", "公开业务联系方式")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.publicContacts.length ? (
                      row.publicContacts.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoContacts", "暂无公开联系方式")}</span>
                    )}
                  </div>
                  {row.candidateProfileCompanies.length || row.candidateProfileHitCount > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {row.candidateProfileCompanies.length ? (
                        <span className="rounded-full bg-sky-50 px-3 py-1.5 text-xs text-sky-700">
                          候选补证公司 {row.candidateProfileCompanies.length}
                        </span>
                      ) : null}
                      {row.candidateProfileHitCount > 0 ? (
                        <span className="rounded-full bg-sky-50 px-3 py-1.5 text-xs text-sky-700">
                          补证公开源 {row.candidateProfileHitCount}
                        </span>
                      ) : null}
                      {row.candidateProfileOfficialHitCount > 0 ? (
                        <span className="rounded-full bg-cyan-50 px-3 py-1.5 text-xs text-cyan-700">
                          其中官方源 {row.candidateProfileOfficialHitCount}
                        </span>
                      ) : null}
                      {row.candidateProfileCompanies.map((item) => (
                        <span key={`candidate-${row.id}-${item}`} className="rounded-full bg-sky-50 px-3 py-1.5 text-xs text-sky-700">
                          候选公司 · {item}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareCompetitorSet", "竞品公司")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.competitorHighlights.length ? (
                      row.competitorHighlights.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoCompetitors", "暂无明确竞品线索")}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.comparePartnerSet", "生态伙伴")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.partnerHighlights.length ? (
                      row.partnerHighlights.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoPartners", "暂无明确伙伴线索")}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareBenchmarks", "标杆案例")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.benchmarkCases.length ? (
                      row.benchmarkCases.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoBenchmarks", "暂无明确标杆案例")}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr),minmax(0,1.1fr)]">
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareBenchmarks", "标杆案例证据摘要")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.benchmarkCases.length ? (
                      row.benchmarkCases.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoBenchmarks", "暂无明确标杆案例")}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareEvidence", "证据链接")}
                  </p>
                  <div className="mt-3 space-y-2">
                    {row.evidenceLinks.length ? (
                      row.evidenceLinks.map((item) => (
                        <a
                          key={item.url}
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center justify-between gap-3 rounded-[16px] border border-white/60 bg-white/70 px-3 py-2 text-sm text-slate-700 transition hover:bg-white"
                        >
                          <div className="min-w-0">
                            <span className="line-clamp-1 block">{item.title}</span>
                            <div className="mt-1 flex flex-wrap gap-2">
                              <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-medium text-sky-700">
                                {sourceTierLabel(item.sourceTier, t)}
                              </span>
                              {item.sourceLabel ? (
                                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                                  {item.sourceLabel}
                                </span>
                              ) : null}
                              {row.candidateProfileSourceLabels.map((label) => (
                                <span key={`${item.url}-${label}`} className="rounded-full bg-cyan-50 px-2 py-0.5 text-[10px] text-cyan-700">
                                  {label}
                                </span>
                              ))}
                            </div>
                          </div>
                          <AppIcon name="external" className="h-4 w-4 shrink-0 text-slate-400" />
                        </a>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoEvidence", "暂无可直接打开的证据链接")}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
                <span>{t("research.compareKeyword", "关键词")} · {row.keyword || "—"}</span>
                <span>{t("research.compareSourceCount", "来源数")} · {row.sourceCount || 0}</span>
                <span>{t("research.compareUpdated", "更新")} · {new Date(row.updatedAt).toLocaleDateString()}</span>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </div>
  );
}
