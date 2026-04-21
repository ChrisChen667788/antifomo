"use client";

import Link from "next/link";
import type { ApiKnowledgeAccountDetail } from "@/lib/api";
import { sanitizeExternalDisplayList, sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";

function maturityLabel(value: string) {
  if (value === "scaling") return "规模化";
  if (value === "piloting") return "试点推进";
  if (value === "discovering") return "方向验证";
  return "早期判断";
}

function probabilityTone(value: number) {
  if (value >= 70) return "bg-emerald-100 text-emerald-700";
  if (value >= 50) return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-500";
}

function riskTone(value: string) {
  if (value === "high") return "bg-rose-100 text-rose-700";
  if (value === "medium") return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-500";
}

function reviewStatusTone(value?: string | null) {
  if (value === "resolved") return "bg-emerald-100 text-emerald-700";
  if (value === "deferred") return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-500";
}

function reviewStatusLabel(value?: string | null) {
  if (value === "resolved") return "已核验";
  if (value === "deferred") return "已延后";
  return "待处理";
}

export function KnowledgeAccountWorkspace({ account }: { account: ApiKnowledgeAccountDetail }) {
  const { t } = useAppPreferences();

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="af-kicker">账户情报</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900">{account.name}</h2>
            {account.summary ? <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">{sanitizeExternalDisplayText(account.summary)}</p> : null}
            <div className="mt-4 flex flex-wrap gap-2">
              <span className={`rounded-full px-2.5 py-1 text-xs ${probabilityTone(account.budget_probability)}`}>
                预算概率 {account.budget_probability}%
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                {maturityLabel(account.maturity_stage)}
              </span>
              <span className="rounded-full bg-sky-100 px-2.5 py-1 text-xs text-sky-700">
                可信度 {account.confidence_score}
              </span>
              <span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs text-violet-700">
                关联研报 {account.report_count}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/knowledge/accounts" className="af-btn af-btn-secondary border px-4 py-2">
              返回账户页
            </Link>
            <Link href="/knowledge" className="af-btn af-btn-secondary border px-4 py-2">
              返回知识库
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <article className="af-glass rounded-[28px] p-5">
          <p className="af-kicker">Why Now</p>
          <div className="mt-3 space-y-3">
            {account.why_now.length ? (
              account.why_now.map((reason) => (
                <div
                  key={reason}
                  className="rounded-[22px] border border-sky-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(240,249,255,0.84))] p-4 text-sm leading-6 text-slate-700"
                >
                  {sanitizeExternalDisplayText(reason)}
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">当前还缺少足够强的时间窗口解释，建议继续补预算和采购信号。</p>
            )}
          </div>
          {account.next_best_action ? (
            <div className="mt-4 rounded-[22px] border border-emerald-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(236,253,245,0.84))] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Next Best Action</p>
              <p className="mt-2 text-sm leading-6 text-emerald-900">{sanitizeExternalDisplayText(account.next_best_action)}</p>
            </div>
          ) : null}
        </article>

        <article className="af-glass rounded-[28px] p-5">
          <p className="af-kicker">组织与触达</p>
          <div className="mt-3 grid gap-3">
            <div className="rounded-[22px] border border-white/80 bg-white/84 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">关键部门</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {account.departments.length ? (
                  account.departments.map((value) => (
                    <span key={value} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-700">
                      {value}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-slate-500">仍待补部门映射</span>
                )}
              </div>
            </div>
            <div className="rounded-[22px] border border-white/80 bg-white/84 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">公开联系入口</p>
              <div className="mt-3 space-y-2">
                {account.contacts.length ? (
                  account.contacts.map((value) => (
                    <p key={value} className="text-sm leading-6 text-slate-700">
                      {value}
                    </p>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">当前仍缺少公开联系人或组织入口。</p>
                )}
              </div>
            </div>
            <div className="rounded-[22px] border border-white/80 bg-white/84 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">风险提示</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {account.risks.length ? (
                  account.risks.map((value) => (
                    <span key={value} className="rounded-full bg-rose-50 px-2.5 py-1 text-xs text-rose-700">
                      {value}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-slate-500">暂无显性高风险项。</span>
                )}
              </div>
            </div>
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.02fr_0.98fr]">
        <article className="af-glass rounded-[28px] p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="af-kicker">Account Plan</p>
              <p className="mt-2 text-sm text-slate-500">按账户规划工作流，将目标、关系和价值假设沉淀为统一账户计划。</p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
              BD 工作台
            </span>
          </div>
          <div className="mt-4 grid gap-3">
            <div className="rounded-[22px] border border-sky-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(240,249,255,0.86))] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Objective</p>
              <p className="mt-2 text-sm leading-6 text-slate-700">{sanitizeExternalDisplayText(account.account_plan.objective || "继续收敛账户目标与下一步动作。")}</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-[22px] border border-white/80 bg-white/84 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Relationship Goal</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">{sanitizeExternalDisplayText(account.account_plan.relationship_goal || "先建立业务 sponsor 与数字化接口人的映射。")}</p>
              </div>
              <div className="rounded-[22px] border border-white/80 bg-white/84 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Value Hypothesis</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">{sanitizeExternalDisplayText(account.account_plan.value_hypothesis || "当前仍需继续补价值假设。")}</p>
              </div>
            </div>
            <div className="rounded-[22px] border border-white/80 bg-white/84 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Strategic Wedges</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {account.account_plan.strategic_wedges.length ? (
                  sanitizeExternalDisplayList(account.account_plan.strategic_wedges).map((value) => (
                    <span key={value} className="rounded-full bg-sky-50 px-2.5 py-1 text-xs text-sky-700">
                      {value}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-slate-500">仍待补差异化切入点。</span>
                )}
              </div>
              {account.account_plan.proof_points.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {sanitizeExternalDisplayList(account.account_plan.proof_points).map((value) => (
                    <span key={`${value}-proof`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">
                      {value}
                    </span>
                  ))}
                </div>
              ) : null}
              {account.account_plan.next_meeting_goal ? (
                <p className="mt-3 text-sm font-medium leading-6 text-sky-800">下次会面目标：{sanitizeExternalDisplayText(account.account_plan.next_meeting_goal)}</p>
              ) : null}
            </div>
          </div>
        </article>

        <article className="af-glass rounded-[28px] p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="af-kicker">Stakeholder Map</p>
              <p className="mt-2 text-sm text-slate-500">将关键部门、公开入口和潜在 gatekeeper 整理为角色地图。</p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
              {account.stakeholder_map.length} 人/角色
            </span>
          </div>
          <div className="mt-4 space-y-3">
            {account.stakeholder_map.length ? (
              account.stakeholder_map.map((stakeholder) => (
                <article key={`${stakeholder.name}-${stakeholder.role}`} className="rounded-[22px] border border-white/80 bg-white/84 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">{stakeholder.name}</h3>
                    <div className="flex flex-wrap gap-2 text-[11px]">
                      <span className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700">{stakeholder.role}</span>
                      <span className={`rounded-full px-2 py-0.5 ${stakeholder.priority === "high" ? "bg-rose-100 text-rose-700" : stakeholder.priority === "medium" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500"}`}>
                        {stakeholder.priority === "high" ? "高优先级" : stakeholder.priority === "medium" ? "中优先级" : "低优先级"}
                      </span>
                    </div>
                  </div>
                  <p className="mt-2 text-sm text-slate-500">判断：{sanitizeExternalDisplayText(stakeholder.stance)}</p>
                  {stakeholder.next_move ? (
                    <p className="mt-2 text-sm leading-6 text-slate-700">下一步：{sanitizeExternalDisplayText(stakeholder.next_move)}</p>
                  ) : null}
                </article>
              ))
            ) : (
              <p className="text-sm text-slate-500">当前仍未形成足够明确的干系人地图。</p>
            )}
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <article className="af-glass rounded-[28px] p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="af-kicker">机会对象</p>
              <p className="mt-2 text-sm text-slate-500">将研报结果进一步转化为可跟进的商机对象。</p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
              {account.opportunity_count} 条
            </span>
          </div>
          <div className="mt-4 space-y-3">
            {account.opportunities.map((opportunity) => (
              <article
                key={`${opportunity.account_slug}-${opportunity.title}`}
                className="rounded-[24px] border border-emerald-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(236,253,245,0.9))] p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">{opportunity.title}</h3>
                  <div className="flex flex-wrap gap-2 text-[11px]">
                    <span className={`rounded-full px-2 py-0.5 ${probabilityTone(opportunity.budget_probability)}`}>
                      {opportunity.confidence_label || `评分 ${opportunity.score}`}
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
                      {maturityLabel(opportunity.stage)}
                    </span>
                  </div>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-700">{sanitizeExternalDisplayText(opportunity.next_best_action)}</p>
                <div className="mt-3 grid gap-3 text-sm text-slate-600 md:grid-cols-2">
                  <p>进入窗口：{sanitizeExternalDisplayText(opportunity.entry_window || "待补")}</p>
                  <p>标杆：{sanitizeExternalDisplayText(opportunity.benchmark_case || "待补")}</p>
                </div>
                {opportunity.why_now.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {sanitizeExternalDisplayList(opportunity.why_now).map((reason) => (
                      <span key={`${opportunity.title}-${reason}`} className="rounded-full bg-white/86 px-2.5 py-1 text-[11px] text-emerald-800">
                        {reason}
                      </span>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </article>

        <article className="af-glass rounded-[28px] p-5">
          <p className="af-kicker">证据与来源</p>
          <div className="mt-4 space-y-3">
            {account.evidence_links.length ? (
              account.evidence_links.map((link) => (
                <div
                  key={`${link.url}-${link.title}`}
                  className="block rounded-[22px] border border-slate-200/80 bg-white/84 p-4 transition hover:border-slate-300 hover:bg-white"
                >
                  <a
                    href={normalizeExternalUrl(link.url)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-semibold text-slate-900 underline-offset-4 hover:text-sky-800 hover:underline"
                  >
                    {link.title}
                  </a>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                    <span className="rounded-full bg-sky-50 px-2 py-0.5 text-sky-700">
                      {link.source_tier === "official"
                        ? t("research.sourceOfficial", "官方源")
                        : link.source_tier === "aggregate"
                          ? t("research.sourceAggregate", "聚合源")
                          : t("research.sourceMedia", "媒体源")}
                    </span>
                    {link.source_label ? (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">{link.source_label}</span>
                    ) : null}
                  </div>
                  <ExternalLinkActions
                    url={link.url}
                    className="mt-3"
                    openLabel="网页打开"
                  />
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">当前仍需补强账户级证据锚点。</p>
            )}
          </div>

          <div className="mt-5 rounded-[22px] border border-white/80 bg-white/84 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">关联研报</p>
            <div className="mt-3 space-y-3">
              {account.related_entries.map((entry) => (
                <Link
                  key={entry.entry_id}
                  href={`/knowledge/${entry.entry_id}`}
                  className="block rounded-[18px] border border-slate-200/80 bg-slate-50/84 p-3 transition hover:border-slate-300 hover:bg-white/84"
                >
                  <p className="text-sm font-semibold text-slate-900">{entry.title}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {entry.collection_name || entry.source_domain || "知识卡片"} · {new Date(entry.created_at).toLocaleDateString()}
                  </p>
                </Link>
              ))}
            </div>
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <article className="af-glass rounded-[28px] p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="af-kicker">Close Plan</p>
              <p className="mt-2 text-sm text-slate-500">将进入路径、预算确认和交付物按阶段拆解为 Close Plan。</p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
              {account.close_plan.length} 步
            </span>
          </div>
          <div className="mt-4 space-y-3">
            {account.close_plan.map((step, index) => (
              <article key={`${step.title}-${index}`} className="rounded-[22px] border border-emerald-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(236,253,245,0.88))] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">{step.title}</h3>
                  <div className="flex flex-wrap gap-2 text-[11px]">
                    <span className="rounded-full bg-white/86 px-2 py-0.5 text-slate-600">{step.owner}</span>
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700">{step.due_window}</span>
                  </div>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-700">{sanitizeExternalDisplayText(step.exit_criteria)}</p>
              </article>
            ))}
          </div>
        </article>

        <article className="af-glass rounded-[28px] p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="af-kicker">Pipeline Risk</p>
              <p className="mt-2 text-sm text-slate-500">将预算、证据、联系人和标杆缺口整理为可执行的风险缓释列表。</p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
              {account.pipeline_risks.length} 项
            </span>
          </div>
          <div className="mt-4 space-y-3">
            {account.pipeline_risks.length ? (
              account.pipeline_risks.map((risk) => (
                <article key={`${risk.title}-${risk.detail}`} className="rounded-[22px] border border-white/80 bg-white/84 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">{risk.title}</h3>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] ${riskTone(risk.severity)}`}>
                      {risk.severity === "high" ? "高优先级" : risk.severity === "medium" ? "中优先级" : "低优先级"}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(risk.detail)}</p>
                  {risk.mitigation ? (
                    <p className="mt-2 text-sm font-medium leading-6 text-rose-800">缓释：{sanitizeExternalDisplayText(risk.mitigation)}</p>
                  ) : null}
                </article>
              ))
            ) : (
              <p className="text-sm text-slate-500">当前暂无显性 pipeline risk。</p>
            )}
          </div>
        </article>
      </section>

      <section className="af-glass rounded-[28px] p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="af-kicker">账户时间线</p>
            <p className="mt-2 text-sm text-slate-500">将研报、机会、Watchlist 变化和冲突审查状态统一到同一条推进时间线。</p>
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
            {account.timeline.length} 条
          </span>
        </div>
        <div className="mt-4 space-y-3">
          {account.timeline.length ? (
            account.timeline.map((item) => (
              <article
                key={item.id}
                className="rounded-[22px] border border-white/80 bg-white/84 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-[11px]">
                      <span
                        className={`rounded-full px-2 py-0.5 ${
                          item.kind === "watchlist"
                            ? "bg-violet-100 text-violet-700"
                            : item.kind === "opportunity"
                              ? "bg-emerald-100 text-emerald-700"
                              : item.kind === "review_queue"
                                ? "bg-rose-100 text-rose-700"
                              : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {item.kind === "watchlist" ? "Watchlist" : item.kind === "opportunity" ? "机会" : item.kind === "review_queue" ? "审查" : "研报"}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 ${
                          item.severity === "high"
                            ? "bg-rose-100 text-rose-700"
                            : item.severity === "medium"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {item.severity === "high" ? "高优先级" : item.severity === "medium" ? "中优先级" : "低优先级"}
                      </span>
                      {item.kind === "review_queue" ? (
                        <span className={`rounded-full px-2 py-0.5 ${reviewStatusTone(item.resolution_status)}`}>
                          {reviewStatusLabel(item.resolution_status)}
                        </span>
                      ) : null}
                      {item.budget_probability > 0 ? (
                        <span className="rounded-full bg-sky-100 px-2 py-0.5 text-sky-700">
                          预算概率 {item.budget_probability}%
                        </span>
                      ) : null}
                      {item.watchlist_name ? (
                        <span className="rounded-full bg-white px-2 py-0.5 text-slate-600">
                          {item.watchlist_name}
                        </span>
                      ) : null}
                    </div>
                    <h3 className="mt-2 text-sm font-semibold text-slate-900">{item.title}</h3>
                    {item.summary ? <p className="mt-2 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(item.summary)}</p> : null}
                    {item.next_action ? (
                      <p className="mt-2 text-sm font-medium leading-6 text-sky-800">下一步：{sanitizeExternalDisplayText(item.next_action)}</p>
                    ) : null}
                    {item.resolution_note ? (
                      <p className="mt-2 text-xs leading-5 text-slate-500">备注：{sanitizeExternalDisplayText(item.resolution_note)}</p>
                    ) : null}
                    {item.tags.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.tags.map((tag) => (
                          <span key={`${item.id}-${tag}`} className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-600">
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div className="flex flex-col items-end gap-2 text-xs text-slate-500">
                    <span>{new Date(item.created_at).toLocaleString()}</span>
                    {item.related_entry_id ? (
                      <Link href={`/knowledge/${item.related_entry_id}`} className="font-medium text-sky-700">
                        查看卡片
                      </Link>
                    ) : null}
                  </div>
                </div>
              </article>
            ))
          ) : (
            <p className="text-sm text-slate-500">当前账户还没有形成连续时间线，建议继续补 Watchlist 或保存更多研报。</p>
          )}
        </div>
      </section>
    </div>
  );
}
