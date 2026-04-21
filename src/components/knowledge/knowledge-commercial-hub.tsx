"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type {
  ApiKnowledgeAccountDigest,
  ApiKnowledgeDashboard,
  ApiKnowledgeOpportunity,
} from "@/lib/api";
import { createTask } from "@/lib/api";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";
import { triggerFileDownload } from "@/lib/research-delivery-export";

type CommercialActionTaskType =
  | "export_exec_brief"
  | "export_sales_brief"
  | "export_outreach_draft"
  | "export_watchlist_digest";

const COMMERCIAL_ACTION_LABELS: Record<CommercialActionTaskType, string> = {
  export_exec_brief: "Exec Brief",
  export_sales_brief: "Sales Brief",
  export_outreach_draft: "Outreach Draft",
  export_watchlist_digest: "Watchlist Digest",
};

function downloadCommercialTask(task: Awaited<ReturnType<typeof createTask>>) {
  const filename =
    typeof task.output_payload?.filename === "string"
      ? task.output_payload.filename
      : `${task.task_type}.md`;
  const content = String(task.output_payload?.content || "").trim();
  if (!content) {
    throw new Error("task output missing");
  }
  triggerFileDownload(filename, content, "text/markdown;charset=utf-8");
}

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

export function KnowledgeCommercialHub({
  dashboard,
  accounts,
  opportunities,
  expanded = false,
}: {
  dashboard: ApiKnowledgeDashboard;
  accounts: ApiKnowledgeAccountDigest[];
  opportunities: ApiKnowledgeOpportunity[];
  expanded?: boolean;
}) {
  const roleViews = useMemo(() => dashboard.role_views || [], [dashboard.role_views]);
  const topAlerts = useMemo(() => dashboard.top_alerts || [], [dashboard.top_alerts]);
  const reviewQueue = useMemo(() => dashboard.review_queue || [], [dashboard.review_queue]);
  const [roleViewKey, setRoleViewKey] = useState(roleViews[0]?.key || "bd");
  const [workspaceQuery, setWorkspaceQuery] = useState("");
  const [focusFilter, setFocusFilter] = useState<"all" | "high_confidence" | "high_budget" | "needs_review" | "high_risk">("all");
  const [runningTask, setRunningTask] = useState<CommercialActionTaskType | "">("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionTone, setActionTone] = useState<"success" | "error">("success");
  const [visibleModules, setVisibleModules] = useState<Record<string, boolean>>({
    alerts: true,
    reviewQueue: true,
    accounts: true,
    opportunities: true,
  });
  const normalizedWorkspaceQuery = workspaceQuery.trim().toLowerCase();
  const activeRoleView = useMemo(
    () => roleViews.find((item) => item.key === roleViewKey) || roleViews[0] || null,
    [roleViews, roleViewKey],
  );
  const filteredAccounts = useMemo(
    () =>
      accounts.filter((account) => {
        const matchesQuery = !normalizedWorkspaceQuery || [
          account.name,
          account.latest_signal,
          account.next_best_action,
          ...(account.benchmark_cases || []),
        ].join(" ").toLowerCase().includes(normalizedWorkspaceQuery);
        if (!matchesQuery) return false;
        if (focusFilter === "high_confidence") return account.confidence_score >= 75;
        if (focusFilter === "high_budget") return account.budget_probability >= 70;
        if (focusFilter === "needs_review") {
          return reviewQueue.some((item) => item.account_slug === account.slug && item.resolution_status !== "resolved");
        }
        if (focusFilter === "high_risk") {
          return topAlerts.some((item) => item.account_slug === account.slug && item.severity === "high");
        }
        return true;
      }),
    [accounts, focusFilter, normalizedWorkspaceQuery, reviewQueue, topAlerts],
  );
  const filteredOpportunities = useMemo(
    () =>
      opportunities.filter((opportunity) => {
        const matchesQuery = !normalizedWorkspaceQuery || [
          opportunity.title,
          opportunity.account_name,
          opportunity.next_best_action,
          ...(opportunity.why_now || []),
        ].join(" ").toLowerCase().includes(normalizedWorkspaceQuery);
        if (!matchesQuery) return false;
        if (focusFilter === "high_confidence") return opportunity.score >= 75 || opportunity.budget_probability >= 70;
        if (focusFilter === "high_budget") return opportunity.budget_probability >= 70;
        if (focusFilter === "needs_review") {
          return reviewQueue.some((item) => item.account_slug === opportunity.account_slug && item.resolution_status !== "resolved");
        }
        if (focusFilter === "high_risk") {
          return topAlerts.some((item) => item.account_slug === opportunity.account_slug && item.severity === "high");
        }
        return true;
      }),
    [focusFilter, normalizedWorkspaceQuery, opportunities, reviewQueue, topAlerts],
  );
  const filteredAlerts = useMemo(
    () =>
      topAlerts.filter((alert) => {
        const matchesQuery = !normalizedWorkspaceQuery || [
          alert.title,
          alert.summary,
          alert.account_name || "",
          alert.recommended_action || "",
        ].join(" ").toLowerCase().includes(normalizedWorkspaceQuery);
        if (!matchesQuery) return false;
        if (focusFilter === "high_risk") return alert.severity === "high";
        if (focusFilter === "needs_review") return alert.kind === "review_queue" || /核验|冲突|待补证/.test(alert.summary);
        return true;
      }),
    [focusFilter, normalizedWorkspaceQuery, topAlerts],
  );
  const filteredReviewQueue = useMemo(
    () =>
      reviewQueue.filter((item) => {
        const matchesQuery = !normalizedWorkspaceQuery || [
          item.title,
          item.summary,
          item.account_name || "",
          item.recommended_action || "",
        ].join(" ").toLowerCase().includes(normalizedWorkspaceQuery);
        if (!matchesQuery) return false;
        if (focusFilter === "high_confidence") return item.resolution_status === "resolved";
        if (focusFilter === "needs_review") return item.resolution_status !== "resolved";
        if (focusFilter === "high_risk") return item.severity === "high";
        return true;
      }),
    [focusFilter, normalizedWorkspaceQuery, reviewQueue],
  );
  const topAccount = dashboard.top_accounts[0] || filteredAccounts[0] || accounts[0] || null;
  const topOpportunity = dashboard.top_opportunities[0] || filteredOpportunities[0] || opportunities[0] || null;
  const topAlert = filteredAlerts[0] || topAlerts[0] || null;
  const topReviewItem = filteredReviewQueue[0] || reviewQueue[0] || null;
  const summaryCards = [
    { label: "账户对象", value: dashboard.account_count, hint: "已沉淀可跟进甲方/账户" },
    { label: "机会对象", value: dashboard.opportunity_count, hint: "已对象化的商机条目" },
    { label: "高可信研报", value: dashboard.high_confidence_report_count, hint: "可信度较高的研报" },
    { label: "标杆案例", value: dashboard.benchmark_case_count, hint: "可用于客户教育与对标" },
    { label: "规则提醒", value: topAlerts.length, hint: "需优先关注的 Watchlist / 风险 / 审查项" },
    { label: "审查队列", value: reviewQueue.length, hint: "建议优先人工或模型二次核验的结论" },
  ];

  const handleCommercialAction = async (taskType: CommercialActionTaskType) => {
    if (runningTask) {
      return;
    }
    setRunningTask(taskType);
    setActionTone("success");
    setActionMessage(`${COMMERCIAL_ACTION_LABELS[taskType]} 正在生成`);
    try {
      const task = await createTask({
        task_type: taskType,
      });
      if (task.status !== "done") {
        throw new Error(task.error_message || "task not completed");
      }
      downloadCommercialTask(task);
      setActionTone("success");
      setActionMessage(`${COMMERCIAL_ACTION_LABELS[taskType]} 已导出`);
    } catch {
      setActionTone("error");
      setActionMessage(`${COMMERCIAL_ACTION_LABELS[taskType]} 导出失败，请稍后重试`);
    } finally {
      setRunningTask("");
    }
  };

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">商业情报工作台</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-slate-900">
            把知识卡片升维成账户、机会和下一步动作
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-500">
            当前知识库已经不只是文档列表。这里把研报里的甲方、预算窗口、标杆案例和行动建议沉淀成可持续跟进的对象。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/knowledge/accounts" className="af-btn af-btn-primary px-4 py-2">
            账户页
          </Link>
          <Link href="/knowledge" className="af-btn af-btn-secondary border px-4 py-2">
            返回知识库
          </Link>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-4">
        {summaryCards.slice(0, 4).map((card) => (
          <article
            key={card.label}
            className="rounded-[24px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(241,245,249,0.78))] p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{card.label}</p>
            <p className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900">{card.value}</p>
            <p className="mt-2 text-sm leading-6 text-slate-500">{card.hint}</p>
          </article>
        ))}
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {summaryCards.slice(4).map((card) => (
          <article
            key={card.label}
            className="rounded-[24px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(241,245,249,0.78))] p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{card.label}</p>
            <p className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900">{card.value}</p>
            <p className="mt-2 text-sm leading-6 text-slate-500">{card.hint}</p>
          </article>
        ))}
      </div>

      <section className="mt-6 rounded-[26px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.9))] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">经营动作流</p>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
              把当前账户、机会、提醒和审查队列直接转成管理层简报、销售简报、外联草稿和 Watchlist 摘要。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(
              [
                "export_exec_brief",
                "export_sales_brief",
                "export_outreach_draft",
                "export_watchlist_digest",
              ] as CommercialActionTaskType[]
            ).map((taskType) => (
              <button
                key={taskType}
                type="button"
                onClick={() => {
                  void handleCommercialAction(taskType);
                }}
                disabled={Boolean(runningTask)}
                className={`rounded-full px-3 py-1.5 text-sm transition ${
                  runningTask === taskType
                    ? "bg-slate-900 text-white"
                    : "bg-sky-50 text-sky-700 hover:bg-sky-100"
                } disabled:cursor-not-allowed disabled:opacity-70`}
              >
                {runningTask === taskType ? `${COMMERCIAL_ACTION_LABELS[taskType]}...` : COMMERCIAL_ACTION_LABELS[taskType]}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-4">
          <article className="rounded-[20px] border border-white/90 bg-white/88 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Top Account</p>
            <p className="mt-2 text-sm font-semibold text-slate-900">{topAccount?.name || "待补对象"}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {sanitizeExternalDisplayText(topAccount?.next_best_action || topAccount?.latest_signal || "当前没有高优先级账户动作。")}
            </p>
          </article>
          <article className="rounded-[20px] border border-white/90 bg-white/88 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Top Opportunity</p>
            <p className="mt-2 text-sm font-semibold text-slate-900">{topOpportunity?.title || "待补商机"}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {sanitizeExternalDisplayText(topOpportunity?.next_best_action || topOpportunity?.account_name || "当前没有高优先级商机动作。")}
            </p>
          </article>
          <article className="rounded-[20px] border border-white/90 bg-white/88 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Watchlist Alert</p>
            <p className="mt-2 text-sm font-semibold text-slate-900">{topAlert?.title || "暂无高优先提醒"}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {sanitizeExternalDisplayText(topAlert?.recommended_action || topAlert?.summary || "当前没有需要立刻升级的 Watchlist 提醒。")}
            </p>
          </article>
          <article className="rounded-[20px] border border-white/90 bg-white/88 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Review Queue</p>
            <p className="mt-2 text-sm font-semibold text-slate-900">{topReviewItem?.title || "暂无待核验结论"}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {sanitizeExternalDisplayText(topReviewItem?.recommended_action || topReviewItem?.summary || "当前没有需要额外补证的审查项。")}
            </p>
          </article>
        </div>
        {actionMessage ? (
          <p
            className={`mt-4 text-sm ${
              actionTone === "error" ? "text-rose-700" : "text-emerald-700"
            }`}
          >
            {actionMessage}
          </p>
        ) : null}
      </section>

      <section className="mt-6 rounded-[26px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.9))] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">检索与聚合工作台</p>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              {sanitizeExternalDisplayText("用统一多视图和聚合筛选，将账户、机会、提醒和审查队列纳入同一组筛选维度。")}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-[11px]">
            <span className="rounded-full bg-white/88 px-2.5 py-1 text-slate-600">账户 {filteredAccounts.length}</span>
            <span className="rounded-full bg-white/88 px-2.5 py-1 text-slate-600">机会 {filteredOpportunities.length}</span>
            <span className="rounded-full bg-white/88 px-2.5 py-1 text-slate-600">提醒 {filteredAlerts.length}</span>
            <span className="rounded-full bg-white/88 px-2.5 py-1 text-slate-600">审查 {filteredReviewQueue.length}</span>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="min-w-[240px] flex-1 rounded-[18px] border border-white/80 bg-white/88 px-3 py-2">
            <input
              value={workspaceQuery}
              onChange={(event) => setWorkspaceQuery(event.target.value)}
              placeholder="搜索账户、机会、提醒、预算、联系人..."
              className="w-full bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
            />
          </div>
          {[
            { key: "all", label: "全部" },
            { key: "high_confidence", label: "高可信" },
            { key: "high_budget", label: "高预算" },
            { key: "needs_review", label: "待核验" },
            { key: "high_risk", label: "高风险" },
          ].map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setFocusFilter(item.key as typeof focusFilter)}
              className={`rounded-full px-3 py-1.5 text-sm ${
                focusFilter === item.key ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      {(roleViews.length || filteredAlerts.length || filteredReviewQueue.length) ? (
        <section className="mt-6 rounded-[26px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.88))] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">角色化仪表盘</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {sanitizeExternalDisplayText("用角色视图和规则提醒，将同一组账户与机会切换为不同职责视图。")}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                { key: "alerts", label: "规则提醒" },
                { key: "reviewQueue", label: "审查队列" },
                { key: "accounts", label: "账户" },
                { key: "opportunities", label: "机会" },
              ].map((module) => (
                <button
                  key={module.key}
                  type="button"
                  onClick={() => setVisibleModules((current) => ({ ...current, [module.key]: !current[module.key] }))}
                  className={`rounded-full px-3 py-1 text-xs ${
                    visibleModules[module.key]
                      ? "bg-slate-900 text-white"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {module.label}
                </button>
              ))}
            </div>
          </div>

          {roleViews.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {roleViews.map((view) => (
                <button
                  key={view.key}
                  type="button"
                  onClick={() => setRoleViewKey(view.key)}
                  className={`rounded-full px-3 py-1.5 text-sm ${
                    activeRoleView?.key === view.key
                      ? "bg-sky-100 text-sky-700"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {view.label}
                </button>
              ))}
            </div>
          ) : null}

          {activeRoleView ? (
            <div className="mt-4 rounded-[22px] border border-sky-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(240,249,255,0.88))] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">{activeRoleView.label}</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(activeRoleView.summary)}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  {activeRoleView.account_slugs.slice(0, 3).map((slug) => (
                    <span key={`${activeRoleView.key}-${slug}`} className="rounded-full bg-white/88 px-2.5 py-1 text-slate-600">
                      {slug}
                    </span>
                  ))}
                </div>
              </div>
              {activeRoleView.focus_items.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {activeRoleView.focus_items.map((item) => (
                    <span key={`${activeRoleView.key}-${item}`} className="rounded-full bg-sky-50 px-2.5 py-1 text-[11px] text-sky-700">
                      {item}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            {visibleModules.alerts && filteredAlerts.length ? (
              <article className="rounded-[24px] border border-rose-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(255,241,242,0.88))] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">规则提醒</p>
                    <p className="mt-2 text-sm text-slate-500">集中汇总 Watchlist 变化、推进风险和重点异常。</p>
                  </div>
                  <span className="rounded-full bg-white/84 px-2.5 py-1 text-xs text-slate-600">{filteredAlerts.length} 条</span>
                </div>
                <div className="mt-4 space-y-3">
                  {filteredAlerts.slice(0, expanded ? 8 : 4).map((alert) => (
                    <Link
                      key={alert.id}
                      href={alert.account_slug ? `/knowledge/accounts/${alert.account_slug}` : "/knowledge"}
                      className="block rounded-[20px] border border-white/90 bg-white/88 p-4 transition hover:bg-white"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-sm font-semibold text-slate-900">{alert.title}</h3>
                        <span className={`rounded-full px-2 py-0.5 text-[11px] ${
                          alert.severity === "high"
                            ? "bg-rose-100 text-rose-700"
                            : alert.severity === "medium"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-slate-100 text-slate-500"
                        }`}>
                          {alert.kind}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(alert.summary)}</p>
                      {alert.recommended_action ? (
                        <p className="mt-2 text-sm font-medium leading-6 text-rose-800">动作：{sanitizeExternalDisplayText(alert.recommended_action)}</p>
                      ) : null}
                    </Link>
                  ))}
                </div>
              </article>
            ) : null}

            {visibleModules.reviewQueue && filteredReviewQueue.length ? (
              <article className="rounded-[24px] border border-amber-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(255,251,235,0.88))] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">待核验结论</p>
                    <p className="mt-2 text-sm text-slate-500">集中呈现冲突结论和低置信章节，优先安排二次核验。</p>
                  </div>
                  <span className="rounded-full bg-white/84 px-2.5 py-1 text-xs text-slate-600">{filteredReviewQueue.length} 条</span>
                </div>
                <div className="mt-4 space-y-3">
                  {filteredReviewQueue.slice(0, expanded ? 8 : 4).map((item) => (
                    <Link
                      key={item.id}
                      href={item.related_entry_id ? `/knowledge/${item.related_entry_id}` : item.account_slug ? `/knowledge/accounts/${item.account_slug}` : "/knowledge"}
                      className="block rounded-[20px] border border-white/90 bg-white/88 p-4 transition hover:bg-white"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-sm font-semibold text-slate-900">{item.title}</h3>
                        <span className={`rounded-full px-2 py-0.5 text-[11px] ${
                          item.severity === "high"
                            ? "bg-rose-100 text-rose-700"
                            : item.severity === "medium"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-slate-100 text-slate-500"
                        }`}>
                          {item.severity === "high" ? "高优先级" : item.severity === "medium" ? "中优先级" : "低优先级"}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(item.summary)}</p>
                      {item.recommended_action ? (
                        <p className="mt-2 text-sm font-medium leading-6 text-amber-900">建议：{sanitizeExternalDisplayText(item.recommended_action)}</p>
                      ) : null}
                    </Link>
                  ))}
                </div>
              </article>
            ) : null}
          </div>
        </section>
      ) : null}

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        {visibleModules.accounts ? (
        <article className="rounded-[26px] border border-sky-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(240,249,255,0.9))] p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">高价值账户</p>
              <p className="mt-2 text-sm text-slate-500">优先处理可信度、预算概率和持续跟踪都更强的账户。</p>
            </div>
            <Link href="/knowledge/accounts" className="text-sm font-medium text-sky-700">
              查看全部
            </Link>
          </div>
          <div className="mt-4 space-y-3">
            {filteredAccounts.slice(0, expanded ? 12 : 4).map((account) => (
              <Link
                key={account.slug}
                href={`/knowledge/accounts/${account.slug}`}
                className="block rounded-[22px] border border-sky-100/80 bg-white/88 p-4 transition hover:border-sky-200 hover:bg-white"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">{account.name}</h3>
                  <div className="flex flex-wrap gap-2 text-[11px]">
                    <span className={`rounded-full px-2 py-0.5 ${probabilityTone(account.budget_probability)}`}>
                      预算概率 {account.budget_probability}%
                    </span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
                      {maturityLabel(account.maturity_stage)}
                    </span>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 text-sm text-slate-600 md:grid-cols-3">
                  <p>研报数 {account.report_count}</p>
                  <p>机会数 {account.opportunity_count}</p>
                  <p>可信度 {account.confidence_score}</p>
                </div>
                {account.latest_signal ? (
                  <p className="mt-3 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(account.latest_signal)}</p>
                ) : null}
                {account.next_best_action ? (
                  <p className="mt-2 text-sm font-medium leading-6 text-sky-800">下一步：{sanitizeExternalDisplayText(account.next_best_action)}</p>
                ) : null}
              </Link>
            ))}
          </div>
        </article>
        ) : <div />}

        {visibleModules.opportunities ? (
        <article className="rounded-[26px] border border-emerald-100/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(236,253,245,0.9))] p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">优先商机</p>
            <p className="mt-2 text-sm text-slate-500">可直接转为会前简报、拜访策略或外联任务的条目。</p>
          </div>
          <div className="mt-4 space-y-3">
            {filteredOpportunities.slice(0, expanded ? 10 : 4).map((opportunity) => (
              <Link
                key={`${opportunity.account_slug}-${opportunity.title}`}
                href={`/knowledge/accounts/${opportunity.account_slug}`}
                className="block rounded-[22px] border border-emerald-100/80 bg-white/88 p-4 transition hover:border-emerald-200 hover:bg-white"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">{opportunity.title}</h3>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] ${probabilityTone(opportunity.budget_probability)}`}>
                    {opportunity.confidence_label || `评分 ${opportunity.score}`}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-500">{opportunity.account_name}</p>
                <p className="mt-3 text-sm leading-6 text-slate-600">{sanitizeExternalDisplayText(opportunity.next_best_action)}</p>
                {opportunity.why_now?.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {opportunity.why_now.slice(0, 2).map((reason) => (
                      <span key={`${opportunity.title}-${reason}`} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                        {sanitizeExternalDisplayText(reason)}
                      </span>
                    ))}
                  </div>
                ) : null}
              </Link>
            ))}
          </div>
        </article>
        ) : <div />}
      </div>
    </section>
  );
}
