"use client";

import { useEffect, useMemo, useState } from "react";
import { getLLMConfig, runLLMDryRun } from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

type Mode = "normal" | "focus";
type Action = "skip" | "later" | "deep_read";

const actionBonus: Record<Action, number> = {
  skip: -8,
  later: 3,
  deep_read: 8,
};

function clamp(v: number, min = 0, max = 100) {
  return Math.max(min, Math.min(max, v));
}

export function RecommenderTuner() {
  const { t } = useAppPreferences();
  const [mode, setMode] = useState<Mode>("normal");
  const [topic, setTopic] = useState(70);
  const [source, setSource] = useState(50);
  const [quality, setQuality] = useState(75);
  const [freshness, setFreshness] = useState(60);
  const [focusMatch, setFocusMatch] = useState(70);
  const [action, setAction] = useState<Action>("later");

  const [wTopic, setWTopic] = useState(35);
  const [wSource, setWSource] = useState(20);
  const [wQuality, setWQuality] = useState(25);
  const [wFreshness, setWFreshness] = useState(20);
  const [wFocus, setWFocus] = useState(20);
  const [llmConfigText, setLlmConfigText] = useState("");
  const [llmDryRunText, setLlmDryRunText] = useState("");
  const [llmLoading, setLlmLoading] = useState(false);

  const result = useMemo(() => {
    const weights =
      mode === "focus"
        ? {
            topic: wTopic,
            source: wSource,
            quality: wQuality,
            freshness: wFreshness,
            focus: wFocus,
          }
        : {
            topic: wTopic,
            source: wSource,
            quality: wQuality,
            freshness: wFreshness,
            focus: 0,
          };
    const total = weights.topic + weights.source + weights.quality + weights.freshness + weights.focus;
    const safeTotal = total <= 0 ? 1 : total;

    const normalized = {
      topic: weights.topic / safeTotal,
      source: weights.source / safeTotal,
      quality: weights.quality / safeTotal,
      freshness: weights.freshness / safeTotal,
      focus: weights.focus / safeTotal,
    };

    const scoreRaw =
      normalized.topic * topic +
      normalized.source * source +
      normalized.quality * quality +
      normalized.freshness * freshness +
      normalized.focus * (mode === "focus" ? focusMatch : 0);
    const finalScore = clamp(scoreRaw + actionBonus[action]);
    const bucket = finalScore >= 75 ? "deep_read" : finalScore >= 45 ? "later" : "skip";

    return {
      totalWeight: total,
      normalized,
      scoreRaw: Number(scoreRaw.toFixed(2)),
      finalScore: Number(finalScore.toFixed(2)),
      bucket,
    };
  }, [
    action,
    focusMatch,
    freshness,
    mode,
    quality,
    source,
    topic,
    wFocus,
    wFreshness,
    wQuality,
    wSource,
    wTopic,
  ]);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await getLLMConfig();
        setLlmConfigText(JSON.stringify(config, null, 2));
      } catch {
        setLlmConfigText(t("tuner.configReadFailed", "读取失败，请确认后端已启动。"));
      }
    };
    void loadConfig();
  }, [t]);

  const runDryRun = async () => {
    setLlmLoading(true);
    try {
      const result = await runLLMDryRun({
        prompt_name: "summarize.txt",
      });
      setLlmDryRunText(JSON.stringify(result, null, 2));
    } catch {
      setLlmDryRunText(
        t("tuner.dryRunFailed", "联调失败，请确认后端 /api/system/llm/dry-run 可访问。"),
      );
    } finally {
      setLlmLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("tuner.mode", "Mode")}</p>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => setMode("normal")}
            className={`af-btn ${mode === "normal" ? "af-btn-primary" : "af-btn-secondary"}`}
          >
            {t("mode.normal", "Normal")}
          </button>
          <button
            type="button"
            onClick={() => setMode("focus")}
            className={`af-btn ${mode === "focus" ? "af-btn-primary" : "af-btn-secondary"}`}
          >
            {t("mode.focus", "Focus")}
          </button>
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("tuner.featureScores", "Feature Scores (0-100)")}</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Slider label={t("tuner.topicPreference", "Topic Preference")} value={topic} onChange={setTopic} />
          <Slider label={t("tuner.sourcePreference", "Source Preference")} value={source} onChange={setSource} />
          <Slider label={t("tuner.itemQuality", "Item Quality")} value={quality} onChange={setQuality} />
          <Slider label={t("tuner.freshness", "Freshness")} value={freshness} onChange={setFreshness} />
          {mode === "focus" ? (
            <Slider label={t("tuner.focusMatch", "Focus Goal Match")} value={focusMatch} onChange={setFocusMatch} />
          ) : null}
        </div>
        <div className="mt-4">
          <label className="text-sm font-medium text-slate-700">
            {t("tuner.actionBonus", "Action Suggestion Bonus")}
          </label>
          <select
            value={action}
            onChange={(event) => setAction(event.target.value as Action)}
            className="af-input mt-2 max-w-xs"
          >
            <option value="skip">{`${t("action.skip", "skip")} (-8)`}</option>
            <option value="later">{`${t("action.later", "later")} (+3)`}</option>
            <option value="deep_read">{`${t("action.deep_read", "deep_read")} (+8)`}</option>
          </select>
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("tuner.weights", "Weights (visual tuning)")}</p>
        <p className="mt-2 text-xs text-slate-500">
          {t("tuner.currentWeightTotal", "当前总权重")}：{result.totalWeight}（
          {t("tuner.weightTip", "页面会自动归一化后计算")}）
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Slider label="w_topic" value={wTopic} onChange={setWTopic} max={60} />
          <Slider label="w_source" value={wSource} onChange={setWSource} max={40} />
          <Slider label="w_quality" value={wQuality} onChange={setWQuality} max={50} />
          <Slider label="w_freshness" value={wFreshness} onChange={setWFreshness} max={40} />
          {mode === "focus" ? (
            <Slider label="w_focus" value={wFocus} onChange={setWFocus} max={40} />
          ) : null}
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("tuner.result", "Result")}</p>
        <div className="mt-3 grid gap-2 text-sm text-slate-700 md:grid-cols-2">
          <p>
            {t("tuner.rawScore", "Raw Score")}: {result.scoreRaw}
          </p>
          <p>
            {t("tuner.finalScore", "Final Score")}: {result.finalScore}
          </p>
          <p>
            {t("tuner.bucket", "Bucket")}: {result.bucket}
          </p>
          <p>
            {t("tuner.actionBonusValue", "Action Bonus")}: {actionBonus[action]}
          </p>
        </div>
        <div className="mt-4 h-2 rounded-full bg-slate-200">
          <div
            className="h-2 rounded-full bg-slate-900"
            style={{ width: `${Math.max(2, result.finalScore)}%` }}
          />
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <p className="af-kicker">{t("tuner.llmDryRun", "LLM Dry-Run")}</p>
        <p className="mt-2 text-xs text-slate-500">
          {t("tuner.llmDryRunDesc", "用于联调当前 provider 是否可用（mock/openai/fallback）。")}
        </p>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => {
              void runDryRun();
            }}
            disabled={llmLoading}
            className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            {llmLoading ? t("tuner.running", "运行中...") : t("tuner.runDryRun", "运行 Dry-Run")}
          </button>
        </div>
        <textarea
          readOnly
          value={llmConfigText}
          rows={7}
          className="mt-3 w-full rounded-2xl border border-white/85 bg-white/70 px-4 py-3 font-mono text-xs leading-6 text-slate-700 outline-none"
        />
        <textarea
          readOnly
          value={llmDryRunText}
          rows={10}
          className="mt-3 w-full rounded-2xl border border-white/85 bg-white/70 px-4 py-3 font-mono text-xs leading-6 text-slate-700 outline-none"
        />
      </section>
    </div>
  );
}

function Slider({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <label className="rounded-2xl border border-white/80 bg-white/55 p-3">
      <div className="flex items-center justify-between text-sm text-slate-700">
        <span>{label}</span>
        <span className="font-semibold">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-2 w-full"
      />
    </label>
  );
}
