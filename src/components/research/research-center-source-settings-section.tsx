"use client";

import type { useResearchCenterController } from "@/components/research/use-research-center-controller";

type ResearchCenterController = ReturnType<typeof useResearchCenterController>;
type ResearchCenterSourceSettingsSectionProps = ResearchCenterController["sourceSettingsSectionProps"];

export function ResearchCenterSourceSettingsSection({
  t,
  sourceSettings,
  sourceSaving,
  sourceError,
  toggleResearchSource,
}: ResearchCenterSourceSettingsSectionProps) {
  return (
        <div className="mt-5 rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-4 shadow-[var(--af-shadow-soft)]">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
                {t("research.centerSourcePanelKicker", "Research Sources")}
              </p>
              <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {t("research.centerSourcePanelDesc", "使用公开可访问来源补充线索。")}
              </p>
            </div>
            <div className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1 text-xs font-medium text-[var(--af-text-tertiary)]">
              {t("research.centerSourceActive", "当前开启")} · {sourceSettings?.enabled_source_labels?.join(" / ") || t("research.centerSourceNone", "无")}
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {[
              {
                key: "enable_jianyu_tender_feed" as const,
                title: t("research.centerSourceJianyu", "剑鱼标讯"),
                desc: t(
                  "research.centerSourceJianyuDesc",
                  "补充公开招标公告、中标成交、采购意向与项目分包线索。",
                ),
                enabled: !!sourceSettings?.enable_jianyu_tender_feed,
              },
              {
                key: "enable_yuntoutiao_feed" as const,
                title: t("research.centerSourceYuntoutiao", "云头条"),
                desc: t(
                  "research.centerSourceYuntoutiaoDesc",
                  "补充云计算、AI、产业竞争和技术商业化动态解读。",
                ),
                enabled: !!sourceSettings?.enable_yuntoutiao_feed,
              },
              {
                key: "enable_ggzy_feed" as const,
                title: t("research.centerSourceGgzy", "全国公共资源交易平台"),
                desc: t(
                  "research.centerSourceGgzyDesc",
                  "补充工程建设、政府采购、成交公示等全国公共资源交易公告。",
                ),
                enabled: !!sourceSettings?.enable_ggzy_feed,
              },
              {
                key: "enable_cecbid_feed" as const,
                title: t("research.centerSourceCecbid", "中国招标投标网"),
                desc: t(
                  "research.centerSourceCecbidDesc",
                  "补充招标、结果、资讯和招标前信息公示等公开招采流。",
                ),
                enabled: !!sourceSettings?.enable_cecbid_feed,
              },
              {
                key: "enable_ccgp_feed" as const,
                title: t("research.centerSourceCcgp", "政府采购合规聚合"),
                desc: t(
                  "research.centerSourceCcgpDesc",
                  "补充采购人、预算和中标线索。",
                ),
                enabled: !!sourceSettings?.enable_ccgp_feed,
              },
              {
                key: "enable_gov_policy_feed" as const,
                title: t("research.centerSourceGovPolicy", "中国政府网政策/讲话"),
                desc: t(
                  "research.centerSourceGovPolicyDesc",
                  "补充政府工作报告、政策文件、领导讲话与战略规划等官方信号。",
                ),
                enabled: !!sourceSettings?.enable_gov_policy_feed,
              },
              {
                key: "enable_local_ggzy_feed" as const,
                title: t("research.centerSourceLocalGgzy", "地方公共资源交易平台"),
                desc: t(
                  "research.centerSourceLocalGgzyDesc",
                  "按区域定向补充省市公共资源交易平台与地方政府采购平台公开公告。",
                ),
                enabled: !!sourceSettings?.enable_local_ggzy_feed,
              },
              {
                key: "enable_curated_wechat_channels" as const,
                title: t("research.centerSourceCuratedWechat", "精选公众号观察池"),
                desc: t(
                  "research.centerSourceCuratedWechatDesc",
                  "补充云、算力和大模型主题线索。",
                ),
                enabled: !!sourceSettings?.enable_curated_wechat_channels,
              },
            ].map((source) => (
              <button
                key={source.key}
                type="button"
                onClick={() => void toggleResearchSource(source.key)}
                disabled={sourceSaving}
                className={`rounded-[24px] border px-4 py-4 text-left transition disabled:cursor-not-allowed disabled:opacity-70 ${
                  source.enabled
                    ? "af-state-panel-info shadow-[var(--af-shadow-soft)]"
                    : "border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)]"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">{source.title}</p>
                    <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                      {source.enabled
                        ? t("research.centerSourceEnabled", "已开启")
                        : t("research.centerSourceDisabled", "已关闭")}
                    </p>
                  </div>
                  <span
                    className={`inline-flex h-8 min-w-14 items-center rounded-full px-1 ${
                      source.enabled ? "bg-[var(--af-info)]" : "bg-[var(--af-border-strong)]"
                    }`}
                  >
                    <span
                      className={`h-6 w-6 rounded-full bg-[var(--af-surface-elevated)] shadow transition ${
                        source.enabled ? "translate-x-6" : "translate-x-0"
                      }`}
                    />
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{source.desc}</p>
              </button>
            ))}
          </div>
          {sourceError ? <p className="mt-3 text-sm text-[var(--af-warning)]">{sourceError}</p> : null}
          {sourceSettings?.connector_statuses?.length ? (
            <div className="mt-4 rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">
                {t("research.centerConnectorStatus", "授权/接入状态")}
              </p>
              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                {sourceSettings.connector_statuses.map((status) => (
                  <div key={status.key} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{status.label}</p>
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                          status.status === "active"
                            ? "af-chip af-chip-success"
                            : status.status === "authorization_required"
                              ? "af-chip af-chip-warning"
                              : "af-chip"
                        }`}
                      >
                        {status.status === "active"
                          ? t("research.centerConnectorActive", "已启用")
                          : status.status === "authorization_required"
                            ? t("research.centerConnectorAuthorization", "需授权")
                            : t("research.centerConnectorAvailable", "可接入")}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{status.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {sourceSaving ? (
            <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">
              {t("research.centerSourceSaving", "正在保存公开源设置...")}
            </p>
          ) : null}
        </div>
  );
}
