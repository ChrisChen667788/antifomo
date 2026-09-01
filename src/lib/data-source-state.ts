export type DataSourceState = "live" | "degraded" | "empty" | "unavailable" | "demo";

type DataSourceItemSignal = {
  fallbackUsed?: boolean | null;
  fallback_used?: boolean | null;
};

export type DataSourceTranslate = (key: string, fallback?: string) => string;

export interface DataSourceStateInput {
  /** A local fixture or mini-program fallback is being displayed instead of an API response. */
  isDemo?: boolean;
  /** The live API request failed and no substitute content is being shown. */
  isUnavailable?: boolean;
  /** A live response may contain content acquired through an explicit fallback path. */
  hasFallbackContent?: boolean;
  items?: readonly DataSourceItemSignal[] | null;
  itemCount?: number | null;
}

export interface DataSourceStateCopy {
  label: string;
  detail: string;
}

export function hasFallbackContent(items: readonly DataSourceItemSignal[] | null | undefined): boolean {
  return Boolean(items?.some((item) => item.fallbackUsed === true || item.fallback_used === true));
}

/**
 * Keep state precedence explicit: a local demo must never be presented as live,
 * and an unreachable API must never be hidden behind an empty-state label.
 */
export function resolveDataSourceState(input: DataSourceStateInput): DataSourceState {
  if (input.isDemo) return "demo";
  if (input.isUnavailable) return "unavailable";
  if (input.hasFallbackContent || hasFallbackContent(input.items)) return "degraded";
  if ((input.itemCount ?? input.items?.length ?? 0) === 0) return "empty";
  return "live";
}

export function getDataSourceStateCopy(
  state: DataSourceState,
  t: DataSourceTranslate,
): DataSourceStateCopy {
  switch (state) {
    case "degraded":
      return {
        label: t("dataSource.degraded.label", "实时 API · 降级内容"),
        detail: t(
          "dataSource.degraded.detail",
          "内容来自实时 API，但其中包含已使用可用正文或降级采集路径的记录；请在详情页复核采集诊断。",
        ),
      };
    case "empty":
      return {
        label: t("dataSource.empty.label", "实时 API · 暂无数据"),
        detail: t(
          "dataSource.empty.detail",
          "实时 API 已响应，但当前没有可展示的记录；不会自动回退演示数据。",
        ),
      };
    case "unavailable":
      return {
        label: t("dataSource.unavailable.label", "实时 API · 不可用"),
        detail: t(
          "dataSource.unavailable.detail",
          "暂时无法读取实时 API；当前未展示演示或缓存内容。",
        ),
      };
    case "demo":
      return {
        label: t("dataSource.demo.label", "本地演示数据"),
        detail: t(
          "dataSource.demo.detail",
          "后端未连接；当前展示的是本地演示数据，不能当作实时内容。",
        ),
      };
    case "live":
    default:
      return {
        label: t("dataSource.live.label", "实时 API 数据"),
        detail: t("dataSource.live.detail", "内容已从实时 API 读取。"),
      };
  }
}
