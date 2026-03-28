"use client";

import { useEffect, useState } from "react";
import {
  boostPreference,
  getPreferenceSummary,
  resetPreferences,
  type ApiPreferenceScore,
  type ApiPreferenceSummary,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

function formatTimestamp(value: string | null | undefined, language: string): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString(language, { hour12: false });
}

function PreferenceList({
  title,
  entries,
  onBoost,
  emptyText,
}: {
  title: string;
  entries: ApiPreferenceScore[];
  onBoost: (key: string) => void;
  emptyText: string;
}) {
  return (
    <section className="rounded-[26px] border border-white/80 bg-white/75 p-4">
      <p className="af-kicker">{title}</p>
      <div className="mt-3 space-y-2">
        {entries.length ? (
          entries.map((entry) => (
            <div
              key={entry.key}
              className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">{entry.key}</p>
                <p className="text-xs text-slate-500">
                  Raw {entry.preference_score.toFixed(1)} · Score {Math.round(entry.mapped_score)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onBoost(entry.key)}
                className="af-btn af-btn-secondary px-3 py-1.5 text-xs"
              >
                +1
              </button>
            </div>
          ))
        ) : (
          <p className="text-sm text-slate-500">{emptyText}</p>
        )}
      </div>
    </section>
  );
}

export function PreferenceInsightsPanel() {
  const { preferences, t } = useAppPreferences();
  const [summary, setSummary] = useState<ApiPreferenceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [busyKey, setBusyKey] = useState("");

  const loadSummary = async () => {
    setLoading(true);
    try {
      const next = await getPreferenceSummary();
      setSummary(next);
      setMessage("");
    } catch {
      setSummary(null);
      setMessage(t("preferences.loadFailed", "偏好数据暂时不可用，请确认后端已启动。"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSummary();
  }, []);

  const handleReset = async () => {
    setBusyKey("reset");
    try {
      const next = await resetPreferences("all");
      setSummary(next);
      setMessage(t("preferences.resetDone", "偏好画像已重置。"));
    } catch {
      setMessage(t("preferences.resetFailed", "偏好重置失败，请稍后再试。"));
    } finally {
      setBusyKey("");
    }
  };

  const handleBoost = async (dimension: "topic" | "source", key: string) => {
    setBusyKey(`${dimension}:${key}`);
    try {
      const result = await boostPreference({ dimension, key, delta: 1 });
      setSummary(result.summary);
      setMessage(
        t("preferences.boostDone", "已强化偏好信号") + ` · ${key}`,
      );
    } catch {
      setMessage(t("preferences.boostFailed", "偏好强化失败，请稍后再试。"));
    } finally {
      setBusyKey("");
    }
  };

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">{t("preferences.kicker", "Preference Center")}</p>
          <h3 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-slate-900">
            {t("preferences.title", "偏好学习画像")}
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {t(
              "preferences.desc",
              "把 like / ignore / save / open_detail 转成主题与来源权重，直接影响推荐排序。",
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              void loadSummary();
            }}
            disabled={loading || busyKey !== ""}
            className="af-btn af-btn-secondary px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {t("common.refresh", "刷新")}
          </button>
          <button
            type="button"
            onClick={() => {
              void handleReset();
            }}
            disabled={busyKey !== ""}
            className="af-btn af-btn-secondary px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busyKey === "reset"
              ? t("common.processing", "处理中...")
              : t("preferences.reset", "重置偏好")}
          </button>
        </div>
      </div>

      {message ? <p className="mt-3 text-sm text-slate-600">{message}</p> : null}

      {loading ? (
        <p className="mt-4 text-sm text-slate-500">{t("common.loading", "加载中...")}</p>
      ) : summary ? (
        <div className="mt-5 space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-[24px] border border-white/80 bg-white/75 p-4">
              <p className="af-kicker">{t("preferences.feedbackTotal", "累计反馈")}</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.feedback_total}</p>
            </div>
            <div className="rounded-[24px] border border-white/80 bg-white/75 p-4">
              <p className="af-kicker">{t("preferences.likeSave", "正向信号")}</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">
                {(summary.recent_feedback_counts.like || 0) + (summary.recent_feedback_counts.save || 0)}
              </p>
            </div>
            <div className="rounded-[24px] border border-white/80 bg-white/75 p-4">
              <p className="af-kicker">{t("preferences.ignoreSignals", "负向信号")}</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">
                {(summary.recent_feedback_counts.ignore || 0) + (summary.recent_feedback_counts.inaccurate || 0)}
              </p>
            </div>
            <div className="rounded-[24px] border border-white/80 bg-white/75 p-4">
              <p className="af-kicker">{t("preferences.lastFeedback", "最近反馈")}</p>
              <p className="mt-2 text-sm font-medium text-slate-700">
                {formatTimestamp(summary.last_feedback_at, preferences.language)}
              </p>
            </div>
          </div>

          <div className="rounded-[26px] border border-white/80 bg-white/75 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
              {t("preferences.version", "Preference Version")}
            </p>
            <p className="mt-2 text-sm text-slate-700">{summary.preference_version}</p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <PreferenceList
              title={t("preferences.topTags", "主题偏好 Top")}
              entries={summary.top_tags}
              onBoost={(key) => {
                void handleBoost("topic", key);
              }}
              emptyText={t("preferences.topTagsEmpty", "还没有稳定的主题偏好。")}
            />
            <PreferenceList
              title={t("preferences.topSources", "来源偏好 Top")}
              entries={summary.top_domains}
              onBoost={(key) => {
                void handleBoost("source", key);
              }}
              emptyText={t("preferences.topSourcesEmpty", "还没有稳定的来源偏好。")}
            />
          </div>
        </div>
      ) : null}
    </section>
  );
}
