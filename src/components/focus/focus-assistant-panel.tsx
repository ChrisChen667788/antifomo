"use client";

import { useState } from "react";
import type { ApiTask, FocusAssistantAction, FocusAssistantPlan } from "@/lib/api";
import { createFocusAssistantPlan, executeFocusAssistantAction } from "@/lib/api";
import {
  buildStoredFocusAssistantResult,
  appendFocusAssistantResult,
} from "@/lib/focus-assistant-storage";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";
import { WorkBuddyMark } from "@/components/ui/workbuddy-mark";

function renderTaskPreview(task: ApiTask | null): string {
  const content = typeof task?.output_payload?.content === "string" ? task.output_payload.content : "";
  return content.slice(0, 220).trim();
}

function renderBridgeLabel(task: ApiTask | null, t: (key: string, fallback: string) => string): string {
  const bridge = task?.output_payload?.workbuddy_bridge as
    | {
        provider?: string | null;
        official_cli_used?: boolean;
        official_cli_authenticated?: boolean;
      }
    | undefined;
  if (!bridge) return "";
  if (bridge.official_cli_used || bridge.provider === "tencent_codebuddy_cli") {
    return t("focus.assistant.bridgeOfficial", "腾讯官方 CodeBuddy CLI");
  }
  if (bridge.official_cli_authenticated === false) {
    return t("focus.assistant.bridgeLocalFallback", "本地兼容层（官方 CLI 未登录）");
  }
  return t("focus.assistant.bridgeLocal", "本地兼容层");
}

export function FocusAssistantPanel({
  goal,
  duration,
}: {
  goal: string;
  duration: number;
}) {
  const { preferences, t } = useAppPreferences();
  const [plan, setPlan] = useState<FocusAssistantPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [executingKey, setExecutingKey] = useState<string>("");
  const [message, setMessage] = useState("");
  const [latestTask, setLatestTask] = useState<ApiTask | null>(null);

  const loadPlan = async () => {
    setLoading(true);
    setMessage("");
    try {
      const result = await createFocusAssistantPlan({
        goal_text: goal || undefined,
        duration_minutes: duration,
        output_language: preferences.language,
      });
      setPlan(result);
    } catch {
      setMessage(t("focus.assistant.planFailed", "生成 Assistant 计划失败，请稍后重试。"));
    } finally {
      setLoading(false);
    }
  };

  const runAction = async (action: FocusAssistantAction, channel: "workbuddy" | "direct") => {
    setExecutingKey(`${action.key}:${channel}`);
    setMessage("");
    try {
      const result = await executeFocusAssistantAction({
        action_key: action.key,
        goal_text: goal || undefined,
        duration_minutes: duration,
        output_language: preferences.language,
        channel,
      });
      setLatestTask(result.task);
      setMessage(result.message);
      appendFocusAssistantResult(
        buildStoredFocusAssistantResult({
          action,
          channelUsed: result.channel_used,
          message: result.message,
          task: result.task,
          sessionId: plan?.latest_session_id || null,
          goalText: goal || null,
          durationMinutes: duration,
        }),
      );
    } catch {
      setMessage(t("focus.assistant.executeFailed", "执行失败，请稍后重试。"));
    } finally {
      setExecutingKey("");
    }
  };

  return (
    <section className="mt-5 rounded-3xl border border-white/85 bg-white/55 p-4 md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">{t("focus.assistant.title", "Focus Assistant")}</p>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {t(
              "focus.assistant.subtitle",
              "先生成安全动作计划，再确认是否通过 WorkBuddy 或直连通道执行。",
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void loadPlan();
          }}
          disabled={loading}
          className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <AppIcon name="spark" className="h-4 w-4" />
          {loading ? t("common.loading", "加载中...") : t("focus.assistant.build", "生成计划")}
        </button>
      </div>

      {plan ? (
        <div className="mt-4 space-y-4">
          <div className="rounded-[24px] border border-slate-200 bg-white/75 p-4">
            <p className="text-sm leading-6 text-slate-600">{plan.summary}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                {t("focus.goal", "本次目标")}：{plan.goal_text || t("common.notSet", "未设置")}
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                {t("common.minutes", "分钟")}：{plan.duration_minutes || duration}
              </span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                Focus Ref：{plan.focus_reference_count}
              </span>
            </div>
          </div>

          <div className="grid gap-3">
            {plan.actions.map((action) => (
              <div key={action.key} className="rounded-[24px] border border-slate-200 bg-white/75 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-slate-900">{action.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-500">{action.description}</p>
                    {action.reason ? <p className="mt-2 text-xs text-amber-600">{action.reason}</p> : null}
                    {action.steps.length ? (
                      <ol className="mt-3 space-y-1 text-xs text-slate-500">
                        {action.steps.map((step, index) => (
                          <li key={`${action.key}-${index}`}>{index + 1}. {step}</li>
                        ))}
                      </ol>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        void runAction(action, "workbuddy");
                      }}
                      disabled={!action.available || !!executingKey}
                      className="af-btn af-btn-primary px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <WorkBuddyMark size={14} />
                      {executingKey === `${action.key}:workbuddy`
                        ? t("focus.assistant.executing", "执行中...")
                        : t("focus.assistant.toWorkBuddy", "交给 WorkBuddy")}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void runAction(action, "direct");
                      }}
                      disabled={!action.available || !!executingKey}
                      className="af-btn af-btn-secondary px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <AppIcon name="summary" className="h-4 w-4" />
                      {executingKey === `${action.key}:direct`
                        ? t("focus.assistant.executing", "执行中...")
                        : t("focus.assistant.direct", "直接执行")}
                    </button>
                  </div>
                </div>
                {action.handoff_prompt ? (
                  <div className="mt-3 rounded-2xl bg-slate-100 px-3 py-2 text-xs leading-6 text-slate-500">
                    {action.handoff_prompt}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          {plan.blocked_actions.length ? (
            <div className="rounded-[24px] border border-amber-200 bg-amber-50/80 p-4">
              <p className="text-sm font-medium text-amber-700">
                {t("focus.assistant.blocked", "当前不支持的高风险动作")}
              </p>
              <div className="mt-2 space-y-2 text-sm text-amber-700">
                {plan.blocked_actions.map((action) => (
                  <div key={action.key}>
                    <p className="font-medium">{action.title}</p>
                    <p className="text-xs">{action.reason || action.description}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {plan.guardrails.length ? (
            <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-4 text-xs leading-6 text-slate-500">
              {plan.guardrails.map((line, index) => (
                <p key={`${line}-${index}`}>{line}</p>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {message ? <p className="mt-3 text-sm text-slate-500">{message}</p> : null}
      {latestTask ? (
        <div className="mt-3 rounded-[24px] border border-slate-200 bg-white/75 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-slate-900">{latestTask.task_type}</p>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">{latestTask.status}</span>
          </div>
          {renderTaskPreview(latestTask) ? (
            <pre className="mt-3 whitespace-pre-wrap text-xs leading-6 text-slate-600">
              {renderTaskPreview(latestTask)}
            </pre>
          ) : null}
          {renderBridgeLabel(latestTask, t) ? (
            <p className="mt-3 text-xs text-slate-500">{renderBridgeLabel(latestTask, t)}</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
