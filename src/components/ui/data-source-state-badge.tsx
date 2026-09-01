"use client";

import {
  getDataSourceStateCopy,
  type DataSourceState,
} from "@/lib/data-source-state";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

const toneClass: Record<DataSourceState, string> = {
  live: "border-emerald-200/80 bg-emerald-50/70 text-emerald-800",
  degraded: "border-amber-200/80 bg-amber-50/80 text-amber-900",
  empty: "border-slate-200/90 bg-slate-50/80 text-slate-700",
  unavailable: "border-rose-200/80 bg-rose-50/80 text-rose-900",
  demo: "border-violet-200/80 bg-violet-50/80 text-violet-900",
};

interface DataSourceStateBadgeProps {
  state: DataSourceState;
  className?: string;
  detail?: string;
}

export function DataSourceStateBadge({
  state,
  className = "",
  detail,
}: DataSourceStateBadgeProps) {
  const { t } = useAppPreferences();
  const copy = getDataSourceStateCopy(state, t);

  return (
    <div
      className={`rounded-2xl border px-3 py-2 text-xs leading-5 ${toneClass[state]} ${className}`.trim()}
      data-source-state={state}
      data-testid="data-source-state"
      role="status"
    >
      <div className="flex flex-wrap items-center gap-x-2 font-semibold">
        <span className="uppercase tracking-[0.12em] opacity-75">
          {t("dataSource.title", "数据源")}
        </span>
        <span>{copy.label}</span>
      </div>
      <p className="mt-0.5 opacity-85">{detail || copy.detail}</p>
    </div>
  );
}
