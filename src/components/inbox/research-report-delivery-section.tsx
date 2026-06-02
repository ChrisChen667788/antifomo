"use client";

import type { ApiResearchReport } from "@/lib/api/types";
import type { ReportScoreBucket, ReportToneMeta } from "@/components/inbox/research-report-section-types";

type ResearchSolutionDeliveryPack = NonNullable<ApiResearchReport["solution_delivery_pack"]>;
type ResearchSolutionArchitectWorkbench = NonNullable<ResearchSolutionDeliveryPack["architect_workbench"]>;

export function ResearchReportDeliverySection({
  report,
  marketIntelligence,
  solutionDeliveryPack,
  solutionDeliveryQuality,
  projectProposalQuality,
  architectureReadiness,
  architectWorkbench,
  primaryCustomerScenario,
  solutionDeliveryQualityMeta,
  projectProposalQualityMeta,
  architectureReadinessState,
  valueBucket,
}: {
  report: ApiResearchReport;
  marketIntelligence: ApiResearchReport["market_intelligence"];
  solutionDeliveryPack: ApiResearchReport["solution_delivery_pack"];
  solutionDeliveryQuality: ResearchSolutionDeliveryPack["solution_quality_profile"];
  projectProposalQuality: ResearchSolutionDeliveryPack["project_proposal_quality_profile"];
  architectureReadiness: ResearchSolutionDeliveryPack["architecture_readiness"];
  architectWorkbench: ResearchSolutionDeliveryPack["architect_workbench"];
  primaryCustomerScenario: ResearchSolutionArchitectWorkbench["customer_scenarios"][number] | undefined;
  solutionDeliveryQualityMeta: ReportToneMeta;
  projectProposalQualityMeta: ReportToneMeta;
  architectureReadinessState: ReportToneMeta;
  valueBucket: (score: number) => ReportScoreBucket;
}) {
  return (
    <>
      {(marketIntelligence?.tender_projects?.length ||
        marketIntelligence?.product_catalog?.length ||
        solutionDeliveryPack?.client_ppt_outline?.length) ? (
        <article className="mt-5 af-report-surface rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-info)]">近三年公开情报与交付包</p>
              <h4 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">
                招投标明细、产品清单、技术参数和方案材料大纲
              </h4>
              <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {marketIntelligence?.source_scope_summary ||
                  "基于公开网页、政府采购、公共资源交易、招投标公开平台、企业官网/产品页和行业媒体整理。"}
              </p>
            </div>
            {marketIntelligence?.window_start && marketIntelligence?.window_end ? (
              <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-3 py-1 text-xs font-semibold text-[var(--af-info)]">
                {marketIntelligence.window_start} - {marketIntelligence.window_end}
              </span>
            ) : null}
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-3">
            <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">招投标项目明细</p>
              <div className="mt-3 space-y-2">
                {(marketIntelligence?.tender_projects || []).slice(0, 4).map((item) => (
                  <div key={`${item.project_name}-${item.source_url}`} className="rounded-xl bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-3 py-2">
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">{item.project_name}</p>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                      {item.notice_type || "公开线索"} · {item.publish_date || "日期待核验"} · {item.amount || "金额待核验"}
                    </p>
                    {item.source_url ? (
                      <a className="mt-1 block truncate text-xs text-[var(--af-info)] text-[var(--af-info)]" href={item.source_url} target="_blank" rel="noreferrer">
                        {item.source_title || item.source_url}
                      </a>
                    ) : null}
                  </div>
                ))}
                {!(marketIntelligence?.tender_projects || []).length ? (
                  <p className="text-sm leading-6 text-[var(--af-text-tertiary)]">当前未形成可引用项目明细，需继续补公开招采来源。</p>
                ) : null}
              </div>
            </div>

            <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">产品清单与技术参数</p>
              <div className="mt-3 space-y-2">
                {(marketIntelligence?.product_catalog || []).slice(0, 5).map((item) => (
                  <div key={`product-${item.name}`} className="rounded-xl bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">{item.name}</p>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                      {(item.technical_parameters || []).slice(0, 2).join(" / ") || item.source_context || "参数待补"}
                    </p>
                  </div>
                ))}
                {marketIntelligence?.intelligence_gaps?.length ? (
                  <p className="text-xs leading-5 text-[var(--af-warning)]">{marketIntelligence.intelligence_gaps[0]}</p>
                ) : null}
              </div>
            </div>

            <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">交付材料大纲</p>
              <div className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                <p>场景：{solutionDeliveryPack?.scenario || report.keyword}</p>
                <p>目标客户：{solutionDeliveryPack?.target_customer || report.target_accounts[0] || "待确认"}</p>
                <p>可研章节：{solutionDeliveryPack?.feasibility_outline?.length || 0} 个</p>
                <p>建议书章节：{solutionDeliveryPack?.project_proposal_outline?.length || 0} 个</p>
                <p>PPT 页纲：{solutionDeliveryPack?.client_ppt_outline?.length || 0} 页</p>
                <p>Advisory 产物：{solutionDeliveryPack?.advisory_artifacts?.length || 0} 份</p>
              </div>
              {solutionDeliveryPack?.review_checklist?.length ? (
                <p className="mt-2 text-xs leading-5 text-[var(--af-info)]">审阅重点：{solutionDeliveryPack.review_checklist[0]}</p>
              ) : null}
              {(solutionDeliveryQuality || projectProposalQuality) ? (
                <div className="mt-3 grid gap-2">
                  {solutionDeliveryQuality ? (
                    <div className={`rounded-xl border px-3 py-2 ${solutionDeliveryQualityMeta.className}`}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs font-semibold">解决方案质量</p>
                        <span className="rounded-full bg-[var(--af-surface-elevated)] px-2 py-0.5 text-[11px]">
                          {solutionDeliveryQuality.overall_score}/100 · {solutionDeliveryQualityMeta.label}
                        </span>
                      </div>
                      <p className="mt-1 text-xs leading-5">
                        {solutionDeliveryQuality.gaps?.[0] || solutionDeliveryQuality.strengths?.[0] || "已按交付质量口径完成结构化自审。"}
                      </p>
                    </div>
                  ) : null}
                  {projectProposalQuality ? (
                    <div className={`rounded-xl border px-3 py-2 ${projectProposalQualityMeta.className}`}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs font-semibold">项目建议书质量</p>
                        <span className="rounded-full bg-[var(--af-surface-elevated)] px-2 py-0.5 text-[11px]">
                          {projectProposalQuality.overall_score}/100 · {projectProposalQualityMeta.label}
                        </span>
                      </div>
                      <p className="mt-1 text-xs leading-5">
                        {projectProposalQuality.self_review?.triggered
                          ? `已自修订：${projectProposalQuality.self_review.before_score}→${projectProposalQuality.self_review.after_score}`
                          : projectProposalQuality.gaps?.[0] || projectProposalQuality.strengths?.[0] || "已完成项目建议书质量自审。"}
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : null}
              {solutionDeliveryPack?.advisory_artifacts?.length ? (
                <div className="mt-3 space-y-2">
                  {solutionDeliveryPack.advisory_artifacts.slice(0, 3).map((artifact) => (
                    <div key={artifact.artifact_type} className="rounded-xl bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-3 py-2">
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{artifact.title}</p>
                      <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">{artifact.purpose}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          {architectureReadiness ? (
            <div className="mt-4 rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] p-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-info)]">解决方案架构就绪度</p>
                  <h5 className="mt-2 text-base font-semibold text-[var(--af-text-primary)]">
                    架构蓝图、接口风险和核验动作
                  </h5>
                  <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                    {architectureReadiness.summary || "已为解决方案架构师沉淀架构评估框架，需补充客户和接口约束后形成外发版。"}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className={`rounded-full border px-2.5 py-1 font-semibold ${architectureReadinessState.className}`}>
                    {architectureReadinessState.label}
                  </span>
                  <span className="rounded-full bg-[var(--af-text-primary)] px-2.5 py-1 font-semibold text-[var(--af-text-inverse)]">
                    {architectureReadiness.overall_score || 0}/100
                  </span>
                </div>
              </div>
              {architectureReadiness.metrics?.length ? (
                <div className="mt-3 grid gap-2 md:grid-cols-5">
                  {architectureReadiness.metrics.slice(0, 5).map((metric) => {
                    const bucket = valueBucket(metric.score);
                    return (
                      <div key={`architecture-metric-${metric.key}`} className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                        <p className="text-[11px] font-semibold text-[var(--af-text-tertiary)]">{metric.label}</p>
                        <div className="mt-1 flex items-center justify-between gap-2">
                          <span className="text-lg font-semibold text-[var(--af-text-primary)]">{metric.score}</span>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] ${bucket.className}`}>{bucket.label}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : null}
              {architectureReadiness.blueprint_sections?.length ? (
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {architectureReadiness.blueprint_sections.slice(0, 4).map((section) => (
                    <div key={`architecture-section-${section.title}`} className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{section.title}</p>
                      <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">{section.purpose}</p>
                      {section.components?.length ? (
                        <p className="mt-1 text-xs leading-5 text-[var(--af-info)]">
                          {section.components.slice(0, 4).join(" / ")}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
              {(architectureReadiness.integration_risks?.length || architectureReadiness.validation_actions?.length) ? (
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {architectureReadiness.integration_risks?.length ? (
                    <div className="rounded-xl border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-warning)]">集成 / 落地风险</p>
                      <ul className="mt-2 space-y-1 text-xs leading-5 text-[var(--af-warning)]">
                        {architectureReadiness.integration_risks.slice(0, 3).map((risk) => (
                          <li key={`architecture-risk-${risk}`}>{risk}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {architectureReadiness.validation_actions?.length ? (
                    <div className="rounded-xl border border-[color-mix(in_srgb,var(--af-success)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_9%,var(--af-surface-muted))] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-success)]">架构核验动作</p>
                      <ul className="mt-2 space-y-1 text-xs leading-5 text-[var(--af-success)]">
                        {architectureReadiness.validation_actions.slice(0, 3).map((action) => (
                          <li key={`architecture-action-${action}`}>{action}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}

          {architectWorkbench &&
          (primaryCustomerScenario ||
            architectWorkbench.stakeholders?.length ||
            architectWorkbench.decision_criteria?.length ||
            architectWorkbench.capability_architecture_matrix?.length ||
            architectWorkbench.architecture_decision_records?.length ||
            architectWorkbench.integration_dependencies?.length ||
            architectWorkbench.next_meeting_agenda?.length) ? (
            <div className="mt-3 rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] p-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-info)]">
                    {architectWorkbench.framework_label || "解决方案架构师工作台"}
                  </p>
                  <h5 className="mt-2 text-base font-semibold text-[var(--af-text-primary)]">
                    客户场景、干系人问题和决策核验
                  </h5>
                </div>
                {primaryCustomerScenario ? (
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-xs font-semibold text-[var(--af-info)]">
                    {primaryCustomerScenario.target_customer || solutionDeliveryPack?.target_customer || "待确认客户"}
                  </span>
                ) : null}
              </div>

              {primaryCustomerScenario ? (
                <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">{primaryCustomerScenario.name || solutionDeliveryPack?.scenario}</p>
                    {primaryCustomerScenario.primary_roles?.length ? (
                      <p className="text-[11px] text-[var(--af-info)]">{primaryCustomerScenario.primary_roles.slice(0, 3).join(" / ")}</p>
                    ) : null}
                  </div>
                  {primaryCustomerScenario.success_metrics?.length ? (
                    <ul className="mt-2 grid gap-1 text-xs leading-5 text-[var(--af-text-secondary)] md:grid-cols-2">
                      {primaryCustomerScenario.success_metrics.slice(0, 4).map((metric) => (
                        <li key={`scenario-metric-${metric}`}>{metric}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}

              {(architectWorkbench.stakeholders?.length || architectWorkbench.decision_criteria?.length) ? (
                <div className="mt-3 grid gap-2 lg:grid-cols-2">
                  {architectWorkbench.stakeholders?.length ? (
                    <div className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-info)]">干系人问题地图</p>
                      <div className="mt-2 space-y-2">
                        {architectWorkbench.stakeholders.slice(0, 4).map((stakeholder) => (
                          <div key={`stakeholder-${stakeholder.role}`} className="border-t border-[var(--af-border-subtle)] pt-2 first:border-t-0 first:pt-0">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-semibold text-[var(--af-text-primary)]">{stakeholder.role}</p>
                              <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-2 py-0.5 text-[10px] font-semibold text-[var(--af-info)]">
                                {stakeholder.influence === "high" ? "高影响" : stakeholder.influence === "low" ? "低影响" : "中影响"}
                              </span>
                            </div>
                            <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                              {stakeholder.decision_questions?.[0] || stakeholder.likely_concerns?.[0] || "待补客户问题"}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {architectWorkbench.decision_criteria?.length ? (
                    <div className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-info)]">决策标准与验证动作</p>
                      <div className="mt-2 space-y-2">
                        {architectWorkbench.decision_criteria.slice(0, 4).map((criterion) => (
                          <div key={`criterion-${criterion.criterion}`} className="border-t border-[var(--af-border-subtle)] pt-2 first:border-t-0 first:pt-0">
                            <p className="text-sm font-semibold text-[var(--af-text-primary)]">{criterion.criterion}</p>
                            <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                              {criterion.validation_action || criterion.why_it_matters}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {(architectWorkbench.capability_architecture_matrix?.length ||
                architectWorkbench.integration_dependencies?.length) ? (
                <div className="mt-3 grid gap-2 lg:grid-cols-2">
                  {architectWorkbench.capability_architecture_matrix?.length ? (
                    <div className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-info)]">能力到架构矩阵</p>
                      <div className="mt-2 space-y-2">
                        {architectWorkbench.capability_architecture_matrix.slice(0, 3).map((mapping) => (
                          <div key={`capability-mapping-${mapping.business_capability}`} className="border-t border-[var(--af-border-subtle)] pt-2 first:border-t-0 first:pt-0">
                            <p className="text-sm font-semibold text-[var(--af-text-primary)]">{mapping.business_capability}</p>
                            <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                              {(mapping.application_services?.slice(0, 2) || []).join(" / ") || "待补应用服务"}
                            </p>
                            {mapping.integration_surfaces?.length ? (
                              <p className="mt-1 text-[11px] leading-5 text-[var(--af-info)]">
                                集成面：{mapping.integration_surfaces.slice(0, 2).join(" / ")}
                              </p>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {architectWorkbench.integration_dependencies?.length ? (
                    <div className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-info)]">集成依赖诊断</p>
                      <div className="mt-2 space-y-2">
                        {architectWorkbench.integration_dependencies.slice(0, 3).map((dependency) => (
                          <div key={`integration-dependency-${dependency.dependency}`} className="border-t border-[var(--af-border-subtle)] pt-2 first:border-t-0 first:pt-0">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-semibold text-[var(--af-text-primary)]">{dependency.dependency}</p>
                              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                                dependency.risk_level === "high"
                                  ? "af-chip af-chip-danger"
                                  : dependency.risk_level === "low"
                                    ? "af-chip af-chip-success"
                                    : "af-chip af-chip-warning"
                              }`}>
                                {dependency.risk_level === "high" ? "高风险" : dependency.risk_level === "low" ? "低风险" : "中风险"}
                              </span>
                            </div>
                            <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                              {dependency.source_system || dependency.api_or_data_contract || "待确认来源系统"}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {architectWorkbench.architecture_decision_records?.length ? (
                <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-info)]">ADR 架构决策记录</p>
                  <div className="mt-2 grid gap-2 md:grid-cols-3">
                    {architectWorkbench.architecture_decision_records.slice(0, 3).map((record) => (
                      <div key={`architecture-decision-${record.decision}`} className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                        <p className="text-sm font-semibold leading-5 text-[var(--af-text-primary)]">{record.decision}</p>
                        <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                          {record.selected_direction || record.context || "待确认决策方向"}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {architectWorkbench.next_meeting_agenda?.length ? (
                <div className="mt-3 rounded-xl border border-[color-mix(in_srgb,var(--af-info)_28%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] px-3 py-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--af-info)]">下一次客户会议议程</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {architectWorkbench.next_meeting_agenda.slice(0, 5).map((item) => (
                      <span key={`meeting-agenda-${item}`} className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] text-[var(--af-text-secondary)]">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          {marketIntelligence?.external_source_queries?.length ? (
            <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">后续全网公开源检索清单</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {marketIntelligence.external_source_queries.slice(0, 6).map((query) => (
                  <span key={`external-query-${query}`} className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] text-[var(--af-text-secondary)]">
                    {query}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </article>
      ) : null}
    </>
  );
}
