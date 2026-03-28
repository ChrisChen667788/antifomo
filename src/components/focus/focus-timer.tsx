"use client";

import type { CSSProperties } from "react";
import type { WechatAgentBatchStatus } from "@/lib/api";
import { useEffect, useRef, useState } from "react";
import {
  finishSession,
  getWechatAgentConfig,
  getSession,
  getWechatAgentBatchStatus,
  getWechatAgentStatus,
  runWechatAgentBatch,
  runWechatAgentOnce,
  startSession,
  startWechatAgent,
  stopWechatAgent,
  updateWechatAgentConfig,
} from "@/lib/api";
import { FocusAssistantPanel } from "@/components/focus/focus-assistant-panel";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

const DURATIONS = [25, 50] as const;
type FocusDuration = (typeof DURATIONS)[number];
const FOCUS_BUBBLES = [
  { left: "16%", size: 10, duration: "7.8s", delay: "0s", drift: "-14px" },
  { left: "28%", size: 14, duration: "6.6s", delay: "1.2s", drift: "10px" },
  { left: "49%", size: 12, duration: "8.4s", delay: "0.6s", drift: "-8px" },
  { left: "67%", size: 8, duration: "5.9s", delay: "1.9s", drift: "12px" },
  { left: "79%", size: 16, duration: "9.1s", delay: "0.4s", drift: "-10px" },
] as const;
const FEED_MODE_KEY = "anti_fomo_feed_mode";
const SESSION_ID_KEY = "anti_fomo_session_id";
const SESSION_GOAL_KEY = "anti_fomo_session_goal";
const FOCUS_WECHAT_AGENT_KEY = "anti_fomo_focus_wechat_agent_owned";

function formatCountdown(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function clampProgress(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

function parseServerUtcDate(value: string | null | undefined): number {
  const text = String(value || "").trim();
  if (!text) {
    return Number.NaN;
  }
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(text) ? text : `${text}Z`;
  return Date.parse(normalized);
}

function hasBatchSnapshot(status: WechatAgentBatchStatus | null): boolean {
  if (!status) {
    return false;
  }
  return Boolean(
    status.total_segments ||
      status.finished_at ||
      status.running ||
      status.submitted ||
      status.submitted_new ||
      status.deduplicated_existing ||
      status.skipped_seen ||
      status.failed,
  );
}

function getBatchProgress(status: WechatAgentBatchStatus | null): number {
  if (!status || status.total_segments <= 0) {
    return 0;
  }
  if (status.running) {
    return Math.max(
      8,
      Math.min(96, Math.round((Math.max(status.current_segment_index, 1) / status.total_segments) * 100)),
    );
  }
  return status.finished_at ? 100 : 0;
}

export function FocusTimer() {
  const { t, preferences } = useAppPreferences();
  const [duration, setDuration] = useState<FocusDuration>(25);
  const [goal, setGoal] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(25 * 60);
  const [running, setRunning] = useState(false);
  const [muteIncoming, setMuteIncoming] = useState(true);
  const [summaryAfter, setSummaryAfter] = useState(true);
  const [generateTodo, setGenerateTodo] = useState(true);
  const [sessionId, setSessionId] = useState("");
  const [sessionClosed, setSessionClosed] = useState(false);
  const [paused, setPaused] = useState(false);
  const [sessionMessage, setSessionMessage] = useState("");
  const [startingSession, setStartingSession] = useState(false);
  const [focusOwnsWechatAgent, setFocusOwnsWechatAgent] = useState(false);
  const [newItemsCount, setNewItemsCount] = useState(0);
  const [wechatBatchStatus, setWechatBatchStatus] = useState<WechatAgentBatchStatus | null>(null);
  const durationRef = useRef<FocusDuration>(25);

  const applySelectedDuration = (nextDuration: FocusDuration) => {
    durationRef.current = nextDuration;
    setDuration(nextDuration);
  };

  const clearFocusWechatFlags = () => {
    setFocusOwnsWechatAgent(false);
    window.localStorage.removeItem(FOCUS_WECHAT_AGENT_KEY);
    window.sessionStorage.removeItem("anti_fomo_focus_start_loop_after_batch");
  };

  const releaseFocusCollection = async () => {
    const ownsAgent =
      focusOwnsWechatAgent || window.localStorage.getItem(FOCUS_WECHAT_AGENT_KEY) === "1";
    clearFocusWechatFlags();
    const previousInterval = Number(window.sessionStorage.getItem("anti_fomo_focus_prev_loop_interval") || 0);
    window.sessionStorage.removeItem("anti_fomo_focus_prev_loop_interval");
    if (previousInterval > 0) {
      try {
        await updateWechatAgentConfig({ loop_interval_sec: previousInterval });
      } catch {
        // ignore restore failures
      }
    }
    if (ownsAgent) {
      try {
        await stopWechatAgent();
      } catch {
        // ignore stop failures
      }
    }
  };

  const ensureFocusCollectionOnResume = async () => {
    try {
      const status = await getWechatAgentStatus().catch(() => ({ running: false }));
      if (status && status.running) {
        setSessionMessage(t("focus.autoCollectReady", "公众号采集已接入本轮专注。"));
        return;
      }
      const config = await getWechatAgentConfig().catch(() => null);
      const previousInterval = Number(config?.loop_interval_sec || 0);
      if (previousInterval > 90) {
        window.sessionStorage.setItem("anti_fomo_focus_prev_loop_interval", String(previousInterval));
        await updateWechatAgentConfig({ loop_interval_sec: 90 }).catch(() => null);
      }
      await startWechatAgent();
      setFocusOwnsWechatAgent(true);
      window.localStorage.setItem(FOCUS_WECHAT_AGENT_KEY, "1");
      setSessionMessage(
        t("focus.autoCollectEnabled", "已自动接入公众号采集，新文章会静默进入解析队列。"),
      );
    } catch {
      setSessionMessage(
        t("focus.autoCollectFailed", "专注已开始，但公众号自动采集启动失败，可去采集器页检查。"),
      );
    }
  };

  useEffect(() => {
    durationRef.current = duration;
  }, [duration]);

  useEffect(() => {
    const storedGoal = window.localStorage.getItem(SESSION_GOAL_KEY) || "";
    const storedSessionId = window.localStorage.getItem(SESSION_ID_KEY) || "";
    const storedOwnsWechatAgent = window.localStorage.getItem(FOCUS_WECHAT_AGENT_KEY) === "1";
    if (storedGoal) {
      setGoal(storedGoal);
    }
    if (storedSessionId) {
      setSessionId(storedSessionId);
    }
    setFocusOwnsWechatAgent(storedOwnsWechatAgent);
  }, []);

  useEffect(() => {
    const activeSessionId = sessionId || window.localStorage.getItem(SESSION_ID_KEY) || "";
    if (!activeSessionId) {
      return;
    }

    const refreshSessionSnapshot = async (targetSessionId: string) => {
      try {
        const session = await getSession(targetSessionId);
        const resolvedDuration = (Number(
          session.duration_minutes || durationRef.current,
        ) as FocusDuration) || durationRef.current;
        const totalSeconds = Math.max(60, resolvedDuration * 60);
        const startMs = parseServerUtcDate(session.start_time || "");
        const isRunning = session.status === "running";
        const remaining =
          isRunning && !Number.isNaN(startMs)
            ? Math.max(0, totalSeconds - Math.floor((Date.now() - startMs) / 1000))
            : 0;
        window.localStorage.setItem(SESSION_ID_KEY, session.id);
        if (session.goal_text) {
          window.localStorage.setItem(SESSION_GOAL_KEY, session.goal_text);
        }
        window.localStorage.setItem(FEED_MODE_KEY, isRunning ? "focus" : "normal");

        setSessionId(session.id);
        setGoal((prev) => session.goal_text || prev);
        applySelectedDuration(resolvedDuration);
        setSessionClosed(!isRunning);
        setNewItemsCount(Number(session.metrics?.new_content_count || 0));
        if (paused && isRunning) {
          return;
        }
        setSecondsLeft(isRunning ? remaining : 0);
        setRunning(isRunning && remaining > 0);
        setSessionMessage((prev) =>
          !isRunning && prev === ""
            ? t("focus.sessionFinished", "本轮 Focus Session 已结束并生成回流摘要。")
            : prev,
        );

        if (!isRunning) {
          setPaused(false);
          clearFocusWechatFlags();
        }
      } catch {
        // keep local countdown if backend is temporarily unavailable
      }
    };

    void refreshSessionSnapshot(activeSessionId);
    const poller = window.setInterval(() => {
      void refreshSessionSnapshot(activeSessionId);
    }, 8000);

    return () => {
      window.clearInterval(poller);
    };
  }, [paused, sessionId, t]);

  useEffect(() => {
    let cancelled = false;

    const refreshWechatBatchStatus = async () => {
      try {
        const status = await getWechatAgentBatchStatus();
        if (!cancelled) {
          setWechatBatchStatus(status);
        }
      } catch {
        // keep last visible batch snapshot on transient failures
      }
    };

    void refreshWechatBatchStatus();
    const poller = window.setInterval(() => {
      void refreshWechatBatchStatus();
    }, running || Boolean(sessionId) ? 5000 : 12000);

    return () => {
      cancelled = true;
      window.clearInterval(poller);
    };
  }, [running, sessionId]);

  useEffect(() => {
    if (!focusOwnsWechatAgent || !wechatBatchStatus || wechatBatchStatus.running) {
      return;
    }
    if (window.sessionStorage.getItem("anti_fomo_focus_start_loop_after_batch") !== "1") {
      return;
    }
    window.sessionStorage.removeItem("anti_fomo_focus_start_loop_after_batch");
    void startWechatAgent()
      .then(() => {
        setSessionMessage(
          t("focus.autoCollectEnabled", "已自动接入公众号采集，新文章会静默进入解析队列。"),
        );
      })
      .catch(() => {
        setSessionMessage(
          t(
            "focus.autoCollectFailed",
            "专注已开始，但公众号自动采集启动失败，可去采集器页检查。",
          ),
        );
      });
  }, [focusOwnsWechatAgent, t, wechatBatchStatus]);

  useEffect(() => {
    if (!running || secondsLeft === 0) {
      return;
    }

    const timerId = window.setTimeout(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          setRunning(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      window.clearTimeout(timerId);
    };
  }, [running, secondsLeft]);

  useEffect(() => {
    if (secondsLeft !== 0 || !sessionId || sessionClosed) {
      return;
    }

    const finalizeSessionFlow = async () => {
      try {
        await finishSession(sessionId, { output_language: preferences.language });
        setSessionMessage(
          t("focus.sessionFinished", "本轮 Focus Session 已结束并生成回流摘要。"),
        );
      } catch {
        setSessionMessage(
          t(
            "focus.sessionFinishedFallback",
            "本轮已结束，待后端可用时可补发 session finish。",
          ),
        );
      } finally {
        setSessionClosed(true);
        setPaused(false);
        setRunning(false);
        window.localStorage.setItem(FEED_MODE_KEY, "normal");
        await releaseFocusCollection();
      }
    };

    void finalizeSessionFlow();
  }, [focusOwnsWechatAgent, preferences.language, secondsLeft, sessionClosed, sessionId, t]);

  const totalSeconds = duration * 60;
  const progress = clampProgress(((totalSeconds - secondsLeft) / totalSeconds) * 100);
  const batchProgress = getBatchProgress(wechatBatchStatus);
  const showBatchCard = hasBatchSnapshot(wechatBatchStatus);
  const orbStyle = {
    "--af-focus-progress": `${progress.toFixed(2)}%`,
  } as CSSProperties;

  const startFocus = async () => {
    if (sessionId && !sessionClosed) {
      setPaused(false);
      setRunning(true);
      void ensureFocusCollectionOnResume();
      return;
    }

    const selectedDuration = durationRef.current;
    setStartingSession(true);
    try {
      const session = await startSession({
        goal_text: goal || undefined,
        duration_minutes: selectedDuration,
        output_language: preferences.language,
      });
      if (session && typeof session === "object" && "id" in session) {
        const nextSessionId = String(session.id);
        setSessionId(nextSessionId);
        setSessionClosed(false);
        window.localStorage.setItem(SESSION_ID_KEY, nextSessionId);
      }
      window.localStorage.setItem(FEED_MODE_KEY, "focus");
      window.localStorage.setItem(SESSION_GOAL_KEY, goal || "");
      setSessionMessage(t("focus.sessionStarted", "Focus Session 已启动。"));
      setSecondsLeft(selectedDuration * 60);

      try {
        const status = await getWechatAgentStatus().catch(() => ({ running: false }));
        const alreadyRunning = Boolean(status && status.running);
        if (alreadyRunning) {
          setFocusOwnsWechatAgent(false);
          window.localStorage.removeItem(FOCUS_WECHAT_AGENT_KEY);
          setSessionMessage(t("focus.autoCollectReady", "公众号采集已接入本轮专注。"));
        } else {
          const config = await getWechatAgentConfig().catch(() => null);
          const previousInterval = Number(config?.loop_interval_sec || 0);
          if (previousInterval > 90) {
            window.sessionStorage.setItem("anti_fomo_focus_prev_loop_interval", String(previousInterval));
            await updateWechatAgentConfig({ loop_interval_sec: 90 }).catch(() => null);
          } else {
            window.sessionStorage.removeItem("anti_fomo_focus_prev_loop_interval");
          }

          const batchResult = await runWechatAgentBatch({
            output_language: preferences.language,
            total_items: 12,
            segment_items: 6,
          }).catch(() => null);

          setFocusOwnsWechatAgent(true);
          window.localStorage.setItem(FOCUS_WECHAT_AGENT_KEY, "1");

          if (batchResult?.ok) {
            setWechatBatchStatus(batchResult.batch_status || null);
            window.sessionStorage.setItem("anti_fomo_focus_start_loop_after_batch", "1");
            setSessionMessage(
              t(
                "focus.autoCollectEnabled",
                "已自动接入公众号采集，新文章会静默进入解析队列。",
              ),
            );
          } else {
            window.sessionStorage.removeItem("anti_fomo_focus_start_loop_after_batch");
            await runWechatAgentOnce({
              output_language: preferences.language,
              max_items: 6,
            }).catch(() => null);
            await startWechatAgent();
            setSessionMessage(
              t(
                "focus.autoCollectEnabled",
                "已自动接入公众号采集，新文章会静默进入解析队列。",
              ),
            );
          }
        }
      } catch {
        setSessionMessage(
          t(
            "focus.autoCollectFailed",
            "专注已开始，但公众号自动采集启动失败，可去采集器页检查。",
          ),
        );
      }
    } catch {
      window.localStorage.setItem(FEED_MODE_KEY, "focus");
      window.localStorage.setItem(SESSION_GOAL_KEY, goal || "");
      setSessionMessage(
        t("focus.sessionLocalMode", "后端未连接，当前以本地计时模式运行。"),
      );
      setSecondsLeft(selectedDuration * 60);
    } finally {
      setStartingSession(false);
    }
    setRunning(true);
  };

  return (
    <div className="mx-auto w-full max-w-3xl af-glass rounded-[34px] p-6 md:p-8">
      <div className="flex flex-wrap items-center gap-2">
        {DURATIONS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => {
              if (running || (sessionId && !sessionClosed)) {
                return;
              }
              applySelectedDuration(option);
              if (!running) {
                setSecondsLeft(option * 60);
              }
            }}
            disabled={running || (Boolean(sessionId) && !sessionClosed)}
            className={`af-btn px-4 py-1.5 ${
              duration === option
                ? "af-btn-primary"
                : "af-btn-secondary"
            }`}
          >
            {option} {t("common.minutes", "分钟")}
          </button>
        ))}
      </div>

      <label className="mt-5 block text-sm font-semibold text-slate-700">
        {t("focus.goal", "本次目标")}
        <input
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
          placeholder={t("focus.goalPlaceholder", "例如：读完 1 篇深度文章并记录 3 个要点")}
          className="af-input mt-2"
        />
      </label>

      <section className="mt-5 rounded-3xl border border-white/85 bg-white/55 p-4 md:p-5">
        <p className="af-kicker">{t("focus.strategyTitle", "Focus Strategy")}</p>
        <div className="mt-3 grid gap-2">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={muteIncoming}
              onChange={(event) => setMuteIncoming(event.target.checked)}
            />
            {t("focus.strategy.muteIncoming", "新内容暂不打断")}
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={summaryAfter}
              onChange={(event) => setSummaryAfter(event.target.checked)}
            />
            {t("focus.strategy.summaryAfter", "结束后统一汇总")}
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={generateTodo}
              onChange={(event) => setGenerateTodo(event.target.checked)}
            />
            {t("focus.strategy.generateTodo", "生成待办建议")}
          </label>
        </div>
      </section>

      <div className="mt-7">
        <div className="mx-auto h-64 w-64 md:h-72 md:w-72">
          <div className="af-focus-orb h-full w-full" style={orbStyle}>
            <div className="af-focus-water">
              <div className="af-focus-wave af-focus-wave-back" />
              <div className="af-focus-wave af-focus-wave-front" />
              <div className="af-focus-bubbles">
                {FOCUS_BUBBLES.map((bubble, index) => (
                  <span
                    key={`${bubble.left}-${index}`}
                    className="af-focus-bubble"
                    style={
                      {
                        left: bubble.left,
                        width: `${bubble.size}px`,
                        height: `${bubble.size}px`,
                        animationDuration: bubble.duration,
                        animationDelay: bubble.delay,
                        "--af-bubble-drift": bubble.drift,
                      } as CSSProperties
                    }
                  />
                ))}
              </div>
            </div>
            <div className="af-focus-sheen" />
            <div className="af-focus-overlay">
              <div className="text-center">
                <p className="af-kicker">{t("focus.countdown", "倒计时")}</p>
                <p className="mt-2 text-5xl font-semibold tracking-[-0.03em] text-[color:var(--text-strong)] md:text-6xl">
                  {formatCountdown(secondsLeft)}
                </p>
                <p className="mt-2 text-sm text-[color:var(--text-soft)]">
                  {running
                    ? t("focus.state.running", "专注进行中")
                    : secondsLeft === 0
                      ? t("focus.state.done", "本轮已完成")
                      : t("focus.state.ready", "准备开始")}
                </p>
                <p className="mt-1 text-sm text-[color:var(--text-soft)]">
                  {t("focus.newItems", "新增内容")} {newItemsCount}{" "}
                  {t("feed.status.itemsUnit", "条")}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={() => {
            if (running) {
              void releaseFocusCollection().finally(() => {
                setSessionMessage(
                  t("focus.statePaused", "已暂停，公众号自动采集也已停止。"),
                );
              });
              setPaused(true);
              setRunning(false);
              return;
            }
            setPaused(false);
            void startFocus();
          }}
          disabled={secondsLeft === 0 || startingSession}
          className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-55"
        >
          {startingSession
            ? t("focus.starting", "启动中...")
            : running
              ? t("focus.pause", "暂停")
              : t("focus.start", "开始")}
        </button>
        <button
          type="button"
          onClick={() => {
            void releaseFocusCollection();
            setPaused(false);
            setRunning(false);
            setSecondsLeft(0);
          }}
          className="af-btn af-btn-secondary"
        >
          {t("focus.finishEarly", "提前结束")}
        </button>
        <button
          type="button"
          onClick={async () => {
            if (sessionId && !sessionClosed) {
              try {
                await finishSession(sessionId, { output_language: preferences.language });
              } catch {
                // ignore reset finish failures
              }
            }
            await releaseFocusCollection();
            setPaused(false);
            setRunning(false);
            setSecondsLeft(durationRef.current * 60);
            setNewItemsCount(0);
            setSessionId("");
            setSessionClosed(false);
            setSessionMessage("");
            window.localStorage.removeItem(SESSION_ID_KEY);
            window.localStorage.removeItem(SESSION_GOAL_KEY);
            window.localStorage.setItem(FEED_MODE_KEY, "normal");
          }}
          className="af-btn af-btn-secondary"
        >
          {t("focus.reset", "重置")}
        </button>
      </div>

      <div className="mt-5 rounded-2xl border border-white/85 bg-white/55 px-4 py-3 text-sm text-slate-600">
        <p>
          {t("focus.currentGoal", "当前目标")}：{goal || t("common.notSet", "未设置")}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {t("focus.strategyStatus", "策略状态")}：
          {muteIncoming
            ? t("focus.strategyStatus.muted", "暂不打断")
            : t("focus.strategyStatus.allowNotify", "允许提醒")}{" "}
          /{" "}
          {summaryAfter
            ? t("focus.strategyStatus.summaryOn", "结束后汇总")
            : t("focus.strategyStatus.summaryOff", "不自动汇总")}{" "}
          /{" "}
          {generateTodo
            ? t("focus.strategyStatus.todoOn", "生成待办建议")
            : t("focus.strategyStatus.todoOff", "不生成待办")}
        </p>
      </div>

      {sessionMessage ? (
        <p className="mt-3 text-xs text-slate-500">{sessionMessage}</p>
      ) : null}

      {showBatchCard ? (
        <section className="mt-5 rounded-2xl border border-white/85 bg-white/55 px-4 py-4 text-sm text-slate-600">
          {(() => {
            const submittedUrl = Math.max(
              wechatBatchStatus?.submitted_url || 0,
              wechatBatchStatus?.live_report_submitted_url || 0,
            );
            const submittedUrlDirect = Math.max(
              wechatBatchStatus?.submitted_url_direct || 0,
              wechatBatchStatus?.live_report_submitted_url_direct || 0,
            );
            const submittedUrlShareCopy = Math.max(
              wechatBatchStatus?.submitted_url_share_copy || 0,
              wechatBatchStatus?.live_report_submitted_url_share_copy || 0,
            );
            const submittedUrlResolved = Math.max(
              wechatBatchStatus?.submitted_url_resolved || 0,
              wechatBatchStatus?.live_report_submitted_url_resolved || 0,
            );
            const submittedOcr = Math.max(
              wechatBatchStatus?.submitted_ocr || 0,
              wechatBatchStatus?.live_report_submitted_ocr || 0,
            );
            return (
              <>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="af-kicker">{t("focus.collectorKicker", "公众号采集")}</p>
              <p className="mt-2 text-base font-semibold text-slate-900">
                {wechatBatchStatus?.running
                  ? t("focus.collectorRunning", "正在静默扫描最新文章")
                  : t("focus.collectorLatest", "最近一轮采集结果")}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {wechatBatchStatus?.running
                  ? `第 ${Math.max(wechatBatchStatus?.current_segment_index || 1, 1)}/${Math.max(
                      wechatBatchStatus?.total_segments || 1,
                      1,
                    )} 段 · ${t("focus.collectorSubmitted", "累计入队")} ${
                      wechatBatchStatus?.submitted || 0
                    } ${t("feed.status.itemsUnit", "条")}`
                  : `第 ${Math.max(wechatBatchStatus?.total_segments || 0, 0)} ${t(
                      "focus.collectorSegments",
                      "段",
                    )} · ${t("focus.collectorSubmitted", "累计入队")} ${
                      wechatBatchStatus?.submitted || 0
                    } ${t("feed.status.itemsUnit", "条")}`}
              </p>
            </div>
            <div className="rounded-full border border-sky-200/80 bg-sky-50/80 px-3 py-1 text-xs font-medium text-sky-700">
              {batchProgress}%
            </div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200/80">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-400 via-blue-500 to-cyan-400 transition-all duration-500"
              style={{ width: `${batchProgress}%` }}
            />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500 md:grid-cols-3 xl:grid-cols-6">
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.collectorSubmittedNew", "真正新增")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {wechatBatchStatus?.submitted_new || 0}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.collectorSubmittedUrl", "链接入队")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {submittedUrl}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.collectorSubmittedOcr", "OCR兜底")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {submittedOcr}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.collectorDedup", "历史去重")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {wechatBatchStatus?.deduplicated_existing || 0}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.collectorSeen", "已跳过")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {wechatBatchStatus?.skipped_seen || 0}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.collectorFailed", "失败")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {wechatBatchStatus?.failed || 0}
              </p>
            </div>
          </div>
          <div className="mt-2 grid grid-cols-1 gap-2 text-xs text-slate-500 md:grid-cols-3">
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.collectorUrlDirect", "直接真链")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">{submittedUrlDirect}</p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.collectorUrlShareCopy", "分享取链")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">{submittedUrlShareCopy}</p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.collectorUrlResolved", "真链恢复")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">{submittedUrlResolved}</p>
            </div>
          </div>
          {wechatBatchStatus?.last_message ? (
            <p className="mt-3 text-xs text-slate-500">
              {t("focus.collectorLastMessage", "状态")}：{wechatBatchStatus.last_message}
            </p>
          ) : null}
          {wechatBatchStatus?.last_error ? (
            <p className="mt-1 text-xs text-rose-500">
              {t("focus.collectorLastError", "最近错误")}：{wechatBatchStatus.last_error}
            </p>
          ) : null}
              </>
            );
          })()}
        </section>
      ) : null}

      <FocusAssistantPanel goal={goal} duration={duration} />
    </div>
  );
}
