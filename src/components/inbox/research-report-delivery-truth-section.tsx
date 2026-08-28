"use client";

import type { ApiResearchReport } from "@/lib/api/types";

type DeliveryTruthStatus = "formal" | "provisional" | "awaiting_user" | "system_degraded";

const truthMeta = (status?: DeliveryTruthStatus) => {
  if (status === "formal") return { label: "正式交付", tone: "border-emerald-200 bg-emerald-50 text-emerald-800" };
  if (status === "provisional") return { label: "候选材料", tone: "border-amber-200 bg-amber-50 text-amber-800" };
  if (status === "system_degraded") return { label: "系统待恢复", tone: "border-rose-200 bg-rose-50 text-rose-800" };
  return { label: "待补资料", tone: "border-amber-200 bg-amber-50 text-amber-800" };
};

const traceabilityLabel = (status?: string) => {
  if (status === "ready_for_workshop") return "可进入客户工作坊";
  if (status === "assumption_required") return "需确认客户现状";
  return "暂不作为客户方案";
};

export function ResearchReportDeliveryTruthSection({ report }: { report: ApiResearchReport }) {
  const truth = report.delivery_truth;
  const pursuit = report.account_pursuit_pack;
  const commercial = report.commercial_bid_pack;
  const traceability = report.solution_delivery_pack?.customer_architecture_traceability;
  const evidenceGate = report.research_evidence_gate;
  if (!truth && !pursuit && !commercial && !traceability) return null;

  const meta = truthMeta(truth?.status);
  return (
    <article data-testid="research-delivery-truth" className="mt-5 af-report-surface rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-info)]">交付状态与账户推进</p>
          <h4 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">
            {truth?.delivery_mode === "account_pursuit" ? "账户推进材料" : "市场扫描与补证路径"}
          </h4>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            {truth?.decisive_reasons?.[0] || pursuit?.summary || "当前结论会按证据状态控制可交付范围。"}
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${meta.tone}`}>{meta.label}</span>
      </div>

      {evidenceGate ? (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            ["本地甲方证明", evidenceGate.local_target_proof_count || 0],
            ["本地决策来源", evidenceGate.local_decision_source_count || 0],
            ["外部标杆", evidenceGate.external_benchmark_count || 0],
            ["历史/政策背景", (evidenceGate.historical_context_count || 0) + (evidenceGate.policy_context_count || 0)],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
              <p className="text-[11px] text-[var(--af-text-tertiary)]">{label}</p>
              <p className="mt-1 text-base font-semibold text-[var(--af-text-primary)]">{value}</p>
            </div>
          ))}
        </div>
      ) : null}

      {truth?.next_action ? (
        <p className="mt-3 rounded-xl border border-[color-mix(in_srgb,var(--af-warning)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_8%,var(--af-surface-muted))] px-3 py-2 text-sm leading-6 text-[var(--af-text-secondary)]">
          下一步：{truth.next_action}
        </p>
      ) : null}

      {pursuit?.cards?.length ? (
        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
          {pursuit.cards.slice(0, 3).map((card) => (
            <section key={card.account_name} className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">{card.account_name}</p>
                  <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">{card.account_role || "采购/建设责任主体"}</p>
                </div>
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                  {card.procurement_stage === "intent" ? "采购意向" : card.procurement_stage === "tender" ? "招标阶段" : "已核验"}
                </span>
              </div>
              <p className="mt-3 text-xs leading-5 text-[var(--af-text-secondary)]">{card.current_signal}</p>
              <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">预算：{card.budget_signal}</p>
              <p className="mt-2 text-xs leading-5 text-[var(--af-info)]">行动：{card.next_action}</p>
              {card.evidence_links[0]?.url ? (
                <a href={card.evidence_links[0].url} target="_blank" rel="noreferrer" className="mt-2 block truncate text-xs text-[var(--af-info)] hover:underline">
                  查看依据：{card.evidence_links[0].title}
                </a>
              ) : null}
            </section>
          ))}
        </div>
      ) : pursuit ? (
        <div className="mt-4 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
          <p className="text-sm font-semibold text-[var(--af-text-primary)]">{pursuit.summary}</p>
          {pursuit.market_scan_actions?.length ? (
            <ul className="mt-2 space-y-1 text-xs leading-5 text-[var(--af-text-secondary)]">
              {pursuit.market_scan_actions.slice(0, 3).map((action) => <li key={action}>{action}</li>)}
            </ul>
          ) : null}
        </div>
      ) : null}

      {(commercial?.buyer_map?.length || traceability) ? (
        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
          {commercial?.buyer_map?.length ? (
            <section className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">商务推进</p>
              <p className="mt-2 text-sm font-semibold text-[var(--af-text-primary)]">{commercial.account_name || "账户待确认"}</p>
              <div className="mt-2 space-y-1.5 text-xs leading-5 text-[var(--af-text-secondary)]">
                {commercial.buyer_map.slice(0, 3).map((entry) => <p key={`${entry.role}-${entry.organization}`}>{entry.role}：{entry.organization || "待核验"}</p>)}
              </div>
              {commercial.next_actions?.[0] ? <p className="mt-2 text-xs leading-5 text-[var(--af-info)]">下一步：{commercial.next_actions[0]}</p> : null}
              {commercial.no_bid_triggers?.[0] ? <p className="mt-2 text-xs leading-5 text-[var(--af-warning)]">暂缓条件：{commercial.no_bid_triggers[0]}</p> : null}
            </section>
          ) : null}
          {traceability ? (
            <section className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">客户方案边界</p>
              <p className="mt-2 text-sm font-semibold text-[var(--af-text-primary)]">{traceabilityLabel(traceability.status)}</p>
              <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                事实 {traceability.facts.length} 项 · 假设 {traceability.assumptions.length} 项 · 建议 {traceability.recommendations.length} 项
              </p>
              <p className="mt-2 text-xs leading-5 text-[var(--af-warning)]">
                {traceability.blockers[0] || traceability.current_estate_questions[0] || "需在客户工作坊确认现有系统和数据边界。"}
              </p>
            </section>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
