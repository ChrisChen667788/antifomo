"use client";

import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";
import { dedupeByKey } from "@/lib/display-list";
import type { ApiResearchReport } from "@/lib/api/types";
import type { ReportScoreBucket } from "@/components/inbox/research-report-section-types";

export function ResearchReportStrategicSection({
  report,
  valueBucket,
  sourceTierLabel,
}: {
  report: ApiResearchReport;
  valueBucket: (score: number) => ReportScoreBucket;
  sourceTierLabel: (value: string) => string;
}) {
  const pendingRankedEntities = (role: "target" | "competitor" | "partner") => {
    const sourceMap = {
      target: report.pending_target_candidates || [],
      competitor: report.pending_competitor_candidates || [],
      partner: report.pending_partner_candidates || [],
    };
    return dedupeByKey(sourceMap[role], (item) => String(item?.name || "").trim(), 3);
  };


  const factorBucket = (score: number) => {
    if (score >= 14) return { label: "强支撑", className: "af-chip af-chip-success" };
    if (score >= 6) return { label: "中支撑", className: "af-chip af-chip-warning" };
    if (score > 0) return { label: "弱支撑", className: "af-chip af-chip-info" };
    if (score < 0) return { label: "风险提示", className: "af-chip af-chip-danger" };
    return { label: "待补依据", className: "bg-[var(--af-surface-muted)] text-[var(--af-text-tertiary)]" };
  };
  const hasStrategicPanels =
    report.target_accounts.length ||
    report.target_departments.length ||
    report.public_contact_channels.length ||
    report.account_team_signals.length ||
    report.budget_signals.length ||
    report.project_distribution.length ||
    report.strategic_directions.length ||
    report.tender_timeline.length ||
    report.leadership_focus.length ||
    report.ecosystem_partners.length ||
    report.competitor_profiles.length ||
    report.benchmark_cases.length ||
    report.flagship_products.length ||
    report.key_people.length ||
    report.five_year_outlook.length ||
    report.client_peer_moves.length ||
    report.winner_peer_moves.length ||
    report.competition_analysis.length;

  const highlightPanels = [
    { title: "重点甲方", items: report.target_accounts, tone: "sky" },
    { title: "高概率决策部门", items: report.target_departments, tone: "slate" },
    { title: "公开业务联系方式", items: report.public_contact_channels, tone: "slate" },
    { title: "目标区域活跃团队", items: report.account_team_signals, tone: "sky" },
    { title: "预算与投资信号", items: report.budget_signals, tone: "emerald" },
    { title: "项目分布与期次", items: report.project_distribution, tone: "emerald" },
    { title: "战略方向", items: report.strategic_directions, tone: "violet" },
    { title: "招标时间预测", items: report.tender_timeline, tone: "violet" },
    { title: "领导关注点", items: report.leadership_focus, tone: "slate" },
    { title: "活跃生态伙伴", items: report.ecosystem_partners, tone: "sky" },
    { title: "竞品公司概况", items: report.competitor_profiles, tone: "amber" },
    { title: "标杆案例", items: report.benchmark_cases, tone: "emerald" },
    { title: "明星产品/方案", items: report.flagship_products, tone: "violet" },
    { title: "关键人物", items: report.key_people, tone: "slate" },
  ].filter((panel) => panel.items.length);

  const toneClasses: Record<string, string> = {
    sky: "border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] text-[var(--af-info)] [&_.af-panel-kicker]:text-[var(--af-info)] [&_.af-bullet]:bg-[var(--af-info)]",
    amber:
      "border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))] text-[var(--af-warning)] [&_.af-panel-kicker]:text-[var(--af-warning)] [&_.af-bullet]:bg-[var(--af-warning)]",
    emerald:
      "border-[color-mix(in_srgb,var(--af-success)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_9%,var(--af-surface-muted))] text-[var(--af-success)] [&_.af-panel-kicker]:text-[var(--af-success)] [&_.af-bullet]:bg-[var(--af-success)]",
    violet:
      "border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] text-[var(--af-info)] [&_.af-panel-kicker]:text-[var(--af-info)] [&_.af-bullet]:bg-[var(--af-info)]",
    slate:
      "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] text-[var(--af-text-secondary)] [&_.af-panel-kicker]:text-[var(--af-text-tertiary)] [&_.af-bullet]:bg-[var(--af-border-strong)]",
  };

  const rankedPanels = [
    {
      title: (report.top_target_accounts && report.top_target_accounts.length) ? "高价值甲方 Top 3" : "待核验甲方候选",
      items: dedupeByKey(
        (report.top_target_accounts && report.top_target_accounts.length)
          ? report.top_target_accounts
          : pendingRankedEntities("target"),
        (entity) => String(entity?.name || "").trim(),
        3,
      ),
      tone: "sky",
    },
    {
      title: (report.top_competitors && report.top_competitors.length) ? "高威胁竞品 Top 3" : "待核验竞品候选",
      items: dedupeByKey(
        (report.top_competitors && report.top_competitors.length)
          ? report.top_competitors
          : pendingRankedEntities("competitor"),
        (entity) => String(entity?.name || "").trim(),
        3,
      ),
      tone: "amber",
    },
    {
      title: (report.top_ecosystem_partners && report.top_ecosystem_partners.length) ? "高影响力生态伙伴 Top 3" : "待核验伙伴候选",
      items: dedupeByKey(
        (report.top_ecosystem_partners && report.top_ecosystem_partners.length)
          ? report.top_ecosystem_partners
          : pendingRankedEntities("partner"),
        (entity) => String(entity?.name || "").trim(),
        3,
      ),
      tone: "emerald",
    },
  ].filter((panel) => panel.items.length);

  return (
    <>
      {hasStrategicPanels ? (
        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
          {report.five_year_outlook.length ? (
            <article className="rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-info)]">
                未来五年演化判断
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-info)]">
                {report.five_year_outlook.map((item) => (
                  <li key={item} className="grid grid-cols-[8px_1fr] items-start gap-2">
                    <span className="mt-[9px] h-1.5 w-1.5 rounded-full bg-[var(--af-info)]" />
                    <span className="min-w-0 break-words">{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
          {report.competition_analysis.length ? (
            <article className="rounded-2xl border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-warning)]">
                竞争分析
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-warning)]">
                {report.competition_analysis.map((item) => (
                  <li key={item} className="grid grid-cols-[8px_1fr] items-start gap-2">
                    <span className="mt-[9px] h-1.5 w-1.5 rounded-full bg-[var(--af-warning)]" />
                    <span className="min-w-0 break-words">{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
        </div>
      ) : null}

      {rankedPanels.length ? (
        <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
          {rankedPanels.map((panel) => (
            <article
              key={panel.title}
              className={`rounded-2xl border p-4 ${toneClasses[panel.tone] || toneClasses.slate}`}
            >
              <p className="af-panel-kicker text-xs font-semibold uppercase tracking-[0.22em]">
                {panel.title}
              </p>
              <div className="mt-3 space-y-3">
                {panel.items.map((entity) => (
                  <div
                    key={`${panel.title}-${entity.name}`}
                    className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h4 className="text-sm font-semibold text-[var(--af-text-primary)]">{entity.name}</h4>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] ${valueBucket(entity.score).className}`}>
                        {valueBucket(entity.score).label}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{entity.reasoning}</p>
                    {entity.score_breakdown?.length ? (
                      <div className="mt-3 grid grid-cols-1 gap-2">
                        {entity.score_breakdown.slice(0, 3).map((factor) => (
                          <div
                            key={`${entity.name}-${factor.label}`}
                            className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-medium text-[var(--af-text-secondary)]">{factor.label}</span>
                              <span className={`rounded-full px-2 py-0.5 text-[10px] ${factorBucket(factor.score).className}`}>
                                {factorBucket(factor.score).label}
                              </span>
                            </div>
                            {factor.note ? <p className="mt-1 text-[11px] leading-5 text-[var(--af-text-tertiary)]">{factor.note}</p> : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {entity.evidence_links?.length ? (
                      <div className="mt-3 space-y-2">
                        {entity.evidence_links.map((link) => (
                          <div
                            key={`${entity.name}-${link.url}`}
                            className="block rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2 transition hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <a
                                href={normalizeExternalUrl(link.url)}
                                target="_blank"
                                rel="noreferrer"
                                className="text-xs font-medium text-[var(--af-text-primary)] underline-offset-4 text-[var(--af-info)] hover:underline"
                              >
                                {link.title}
                              </a>
                              <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2 py-0.5 text-[10px] text-[var(--af-info)]">
                                {sourceTierLabel(link.source_tier || "media")}
                              </span>
                              {link.source_label ? (
                                <span className="rounded-full bg-[var(--af-surface-muted)] px-2 py-0.5 text-[10px] text-[var(--af-text-tertiary)]">
                                  {link.source_label}
                                </span>
                              ) : null}
                            </div>
                            <ExternalLinkActions
                              url={link.url}
                              className="mt-2"
                              openLabel="网页打开"
                            />
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {(report.client_peer_moves.length || report.winner_peer_moves.length) ? (
        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
          {report.client_peer_moves.length ? (
            <article className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                甲方同行 Top 3 动态
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {report.client_peer_moves.map((item) => (
                  <li key={item} className="grid grid-cols-[8px_1fr] items-start gap-2">
                    <span className="mt-[9px] h-1.5 w-1.5 rounded-full bg-[var(--af-border-strong)]" />
                    <span className="min-w-0 break-words">{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
          {report.winner_peer_moves.length ? (
            <article className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                中标方同行 Top 3 动态
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {report.winner_peer_moves.map((item) => (
                  <li key={item} className="grid grid-cols-[8px_1fr] items-start gap-2">
                    <span className="mt-[9px] h-1.5 w-1.5 rounded-full bg-[var(--af-border-strong)]" />
                    <span className="min-w-0 break-words">{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
        </div>
      ) : null}

      {highlightPanels.length ? (
        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {highlightPanels.map((panel) => (
            <article
              key={panel.title}
              className={`rounded-2xl border p-4 ${toneClasses[panel.tone] || toneClasses.slate}`}
            >
              <p className="af-panel-kicker text-xs font-semibold uppercase tracking-[0.22em]">{panel.title}</p>
              <ul className="mt-3 space-y-2 text-sm leading-6">
                {panel.items.map((item) => (
                  <li key={item} className="grid grid-cols-[8px_1fr] items-start gap-2">
                    <span className="af-bullet mt-[9px] h-1.5 w-1.5 rounded-full" />
                    <span className="min-w-0 break-words">{item}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      ) : null}
    </>
  );
}
