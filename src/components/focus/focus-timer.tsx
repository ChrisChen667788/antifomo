"use client";

import type { CSSProperties } from "react";
import type { ApiSession, CollectorDaemonStatus, WechatAgentBatchStatus } from "@/lib/api/types";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  finishSession,
  getCollectorDaemonStatus,
  getWechatAgentConfig,
  getSession,
  getWechatAgentBatchStatus,
  getWechatAgentStatus,
  pauseSession,
  runWechatAgentBatch,
  runWechatAgentOnce,
  resumeSession,
  startCollectorDaemon,
  startSession,
  startWechatAgent,
  stopWechatAgent,
  updateWechatAgentConfig,
} from "@/lib/api";
import { FocusAssistantPanel } from "@/components/focus/focus-assistant-panel";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import {
  FOCUS_DURATIONS,
  clampProgress,
  formatCountdown,
  formatRatioPercent,
  getBatchProgress,
  hasBatchSnapshot,
  resolveSessionRemainingSeconds,
  sourceCoverageClass,
  sourceCoverageLabel,
  type FocusDuration,
} from "@/lib/focus-runtime-model";

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
type FocusTransportMode = "idle" | "bootstrapping" | "live" | "local";

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
  const [sessionControlPending, setSessionControlPending] = useState(false);
  const [transportMode, setTransportMode] = useState<FocusTransportMode>("idle");
  const [focusOwnsWechatAgent, setFocusOwnsWechatAgent] = useState(false);
  const [newItemsCount, setNewItemsCount] = useState(0);
  const [collectorDaemonStatus, setCollectorDaemonStatus] = useState<CollectorDaemonStatus | null>(null);
  const [wechatBatchStatus, setWechatBatchStatus] = useState<WechatAgentBatchStatus | null>(null);
  const durationRef = useRef<FocusDuration>(25);
  const focusBootstrapTokenRef = useRef(0);

  const applySelectedDuration = (nextDuration: FocusDuration) => {
    durationRef.current = nextDuration;
    setDuration(nextDuration);
  };

  const invalidateFocusBootstrap = useCallback(() => {
    focusBootstrapTokenRef.current += 1;
    window.sessionStorage.removeItem("anti_fomo_focus_start_loop_after_batch");
  }, []);

  const issueFocusBootstrapToken = () => {
    focusBootstrapTokenRef.current += 1;
    return focusBootstrapTokenRef.current;
  };

  const isFocusBootstrapActive = (token: number) => focusBootstrapTokenRef.current === token;

  const clearFocusWechatFlags = useCallback(() => {
    setFocusOwnsWechatAgent(false);
    window.localStorage.removeItem(FOCUS_WECHAT_AGENT_KEY);
    window.sessionStorage.removeItem("anti_fomo_focus_start_loop_after_batch");
  }, []);

  const releaseFocusCollection = useCallback(async () => {
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
  }, [clearFocusWechatFlags, focusOwnsWechatAgent]);

  const ensureHeadlessSourceCollector = async () => {
    const currentStatus = await getCollectorDaemonStatus().catch(() => null);
    if (currentStatus) {
      setCollectorDaemonStatus(currentStatus);
    }
    if (currentStatus?.running) {
      return true;
    }

    const result = await startCollectorDaemon().catch(() => null);
    if (result?.status) {
      setCollectorDaemonStatus(result.status);
    }
    return Boolean(result?.ok || result?.status?.running);
  };

  const ensureFocusCollectionOnResume = async () => {
    try {
      await ensureHeadlessSourceCollector().catch(() => false);
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

  const applyRemoteSessionSnapshot = useCallback(
    (session: ApiSession) => {
      const resolvedDuration = (Number(
        session.duration_minutes || durationRef.current,
      ) as FocusDuration) || durationRef.current;
      const remaining = resolveSessionRemainingSeconds(session, resolvedDuration);
      const isRunning = session.status === "running";
      const isPaused = session.status === "paused";
      const isFinished = session.status === "finished";

      window.localStorage.setItem(SESSION_ID_KEY, session.id);
      if (session.goal_text) {
        window.localStorage.setItem(SESSION_GOAL_KEY, session.goal_text);
      }
      window.localStorage.setItem(FEED_MODE_KEY, isRunning ? "focus" : "normal");

      setSessionId(session.id);
      setGoal((prev) => session.goal_text || prev);
      applySelectedDuration(resolvedDuration);
      setTransportMode(isFinished ? "idle" : "live");
      setSessionClosed(isFinished);
      setPaused(isPaused && remaining > 0);
      setRunning(isRunning && remaining > 0);
      setSecondsLeft(isFinished ? 0 : remaining);
      setNewItemsCount(Number(session.metrics?.new_content_count || 0));
      setSessionMessage((prev) => {
        if (isPaused) {
          return t("focus.sessionPaused", "专注会话已暂停，可随时继续。");
        }
        if (isFinished) {
          return prev === ""
            ? t("focus.sessionFinished", "本轮专注已结束，摘要已准备好。")
            : prev;
        }
        return prev;
      });

      if (isPaused || isFinished) {
        clearFocusWechatFlags();
      }
    },
    [clearFocusWechatFlags, t],
  );

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
        applyRemoteSessionSnapshot(session);
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
  }, [applyRemoteSessionSnapshot, sessionId]);

  useEffect(() => {
    let cancelled = false;

    const refreshCollectorDaemonStatus = async () => {
      try {
        const status = await getCollectorDaemonStatus();
        if (!cancelled) {
          setCollectorDaemonStatus(status);
        }
      } catch {
        // keep last visible daemon snapshot on transient failures
      }
    };

    void refreshCollectorDaemonStatus();
    const poller = window.setInterval(() => {
      void refreshCollectorDaemonStatus();
    }, running || Boolean(sessionId) ? 8000 : 20000);

    return () => {
      cancelled = true;
      window.clearInterval(poller);
    };
  }, [running, sessionId]);

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
          t("focus.sessionFinished", "本轮专注已结束，摘要已准备好。"),
        );
      } catch {
        setSessionMessage(
          t(
            "focus.sessionFinishedFallback",
            "本轮已结束，稍后可再同步总结。",
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
  }, [preferences.language, releaseFocusCollection, secondsLeft, sessionClosed, sessionId, t]);

  const totalSeconds = duration * 60;
  const progress = clampProgress(((totalSeconds - secondsLeft) / totalSeconds) * 100);
  const batchProgress = getBatchProgress(wechatBatchStatus);
  const showBatchCard = hasBatchSnapshot(wechatBatchStatus);
  const showSourceCollectorCard = Boolean(
    collectorDaemonStatus &&
      (running ||
        collectorDaemonStatus.running ||
        collectorDaemonStatus.last_run_at ||
        collectorDaemonStatus.source_file_count > 0),
  );
  const problematicSources = (collectorDaemonStatus?.source_health || [])
    .filter((source) => source.health_state !== "good")
    .slice(0, 3);
  const orbStyle = {
    "--af-focus-progress": `${progress.toFixed(2)}%`,
  } as CSSProperties;

  const bootstrapFocusSession = async (bootstrapToken: number, selectedDuration: FocusDuration) => {
    try {
      const session = await startSession({
        goal_text: goal || undefined,
        duration_minutes: selectedDuration,
        output_language: preferences.language,
      });
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }
      if (session && typeof session === "object" && "id" in session) {
        const nextSessionId = String(session.id);
        setSessionId(nextSessionId);
        setSessionClosed(false);
        setTransportMode("live");
        window.localStorage.setItem(SESSION_ID_KEY, nextSessionId);
      }
      setSessionMessage(
        t("focus.sessionStarted", "本轮专注已开始。"),
      );
    } catch {
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }
      setTransportMode("local");
      setSessionMessage(
        t("focus.sessionLocalMode", "当前仅保留本地计时，稍后可重新开始正式记录。"),
      );
    }
  };

  const bootstrapFocusCollection = async (bootstrapToken: number) => {
    try {
      const headlessReady = await ensureHeadlessSourceCollector().catch(() => false);
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }
      setSessionMessage(
        headlessReady
          ? t(
              "focus.headlessCollectEnabled",
              "源页面采集已接入，微信真链采集将作为补充。",
            )
          : t(
              "focus.headlessCollectFailed",
              "源页面采集暂不可用，正在尝试微信真链采集。",
            ),
      );

      const status = await getWechatAgentStatus().catch(() => ({ running: false }));
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }
      const alreadyRunning = Boolean(status && status.running);
      if (alreadyRunning) {
        setFocusOwnsWechatAgent(false);
        window.localStorage.removeItem(FOCUS_WECHAT_AGENT_KEY);
        setSessionMessage(t("focus.autoCollectReady", "公众号采集已接入本轮专注。"));
        return;
      }

      const config = await getWechatAgentConfig().catch(() => null);
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }

      const previousInterval = Number(config?.loop_interval_sec || 0);
      if (previousInterval > 90) {
        window.sessionStorage.setItem("anti_fomo_focus_prev_loop_interval", String(previousInterval));
        await updateWechatAgentConfig({ loop_interval_sec: 90 }).catch(() => null);
      } else {
        window.sessionStorage.removeItem("anti_fomo_focus_prev_loop_interval");
      }
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }

      const batchResult = await runWechatAgentBatch({
        output_language: preferences.language,
        total_items: 12,
        segment_items: 6,
      }).catch(() => null);
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }

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
        return;
      }

      window.sessionStorage.removeItem("anti_fomo_focus_start_loop_after_batch");
      await runWechatAgentOnce({
        output_language: preferences.language,
        max_items: 6,
      }).catch(() => null);
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }
      await startWechatAgent();
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }
      setSessionMessage(
        t(
          "focus.autoCollectEnabled",
          "已自动接入公众号采集，新文章会静默进入解析队列。",
        ),
      );
    } catch {
      if (!isFocusBootstrapActive(bootstrapToken)) {
        return;
      }
      setSessionMessage(
        t(
          "focus.autoCollectFailed",
          "专注已开始，但公众号自动采集启动失败，可去采集器页检查。",
        ),
      );
    }
  };

  const startFocus = async () => {
    if (paused && secondsLeft > 0) {
      if (sessionId && !sessionClosed) {
        setSessionControlPending(true);
        try {
          const session = await resumeSession(sessionId);
          applyRemoteSessionSnapshot(session);
          void ensureFocusCollectionOnResume();
        } catch {
          setSessionMessage(
            t("focus.resumeFailed", "恢复专注会话失败，请稍后重试。"),
          );
        } finally {
          setSessionControlPending(false);
        }
      } else {
        setPaused(false);
        setRunning(true);
        setTransportMode((current) => (current === "idle" ? "local" : current));
      }
      return;
    }

    if (sessionId && !sessionClosed) {
      setSessionControlPending(true);
      try {
        const session = await resumeSession(sessionId);
        applyRemoteSessionSnapshot(session);
        void ensureFocusCollectionOnResume();
      } catch {
        setSessionMessage(
          t("focus.resumeFailed", "恢复专注会话失败，请稍后重试。"),
        );
      } finally {
        setSessionControlPending(false);
      }
      return;
    }

    const selectedDuration = durationRef.current;
    const bootstrapToken = issueFocusBootstrapToken();
    setPaused(false);
    setSessionClosed(false);
    setSecondsLeft(selectedDuration * 60);
    setRunning(true);
    setTransportMode("bootstrapping");
    window.localStorage.setItem(FEED_MODE_KEY, "focus");
    window.localStorage.setItem(SESSION_GOAL_KEY, goal || "");
    setSessionMessage(
      t(
        "focus.sessionBootstrapping",
        "倒计时已开始，后台正在接入专注会话与采集。",
      ),
    );
    void bootstrapFocusSession(bootstrapToken, selectedDuration);
    void bootstrapFocusCollection(bootstrapToken);
  };

  const handlePrimaryAction = async () => {
    if (running) {
      invalidateFocusBootstrap();
      if (sessionId && !sessionClosed) {
        setSessionControlPending(true);
        try {
          const session = await pauseSession(sessionId);
          await releaseFocusCollection();
          applyRemoteSessionSnapshot(session);
        } catch {
          setSessionMessage(
            t("focus.pauseFailed", "暂停专注会话失败，请稍后重试。"),
          );
        } finally {
          setSessionControlPending(false);
        }
        return;
      }

      void releaseFocusCollection();
      setPaused(true);
      setRunning(false);
      setTransportMode((current) =>
        sessionId && !sessionClosed ? "live" : current === "live" ? "live" : "local",
      );
      setSessionMessage(
        t("focus.sessionPaused", "专注会话已暂停，可随时继续。"),
      );
      return;
    }

    setPaused(false);
    void startFocus();
  };

  const focusStateLabel = running
    ? t("focus.state.running", "专注进行中")
    : paused
      ? t("focus.state.paused", "已暂停")
      : secondsLeft === 0
        ? t("focus.state.done", "本轮已完成")
        : t("focus.state.ready", "准备开始");
  const transportBadgeLabel =
    transportMode === "bootstrapping"
      ? t("focus.transport.bootstrapping", "接入中")
      : transportMode === "live"
        ? t("focus.transport.live", "记录中")
        : transportMode === "local"
          ? t("focus.transport.local", "本地模式")
          : t("focus.transport.idle", "未接入");
  const focusStatusTitle = paused
    ? t("focus.status.pausedTitle", "已暂停专注会话")
    : running && transportMode === "bootstrapping"
      ? t("focus.status.bootstrappingTitle", "倒计时已启动，后台正在接入")
      : running && transportMode === "local"
        ? t("focus.status.localTitle", "正在本地模式下专注")
        : running
          ? t("focus.status.liveTitle", "专注会话已连接")
          : secondsLeft === 0
            ? t("focus.status.doneTitle", "本轮专注已结束")
            : t("focus.status.readyTitle", "准备开始一轮专注");
  const focusStatusDetail = paused
    ? sessionId && !sessionClosed
      ? t(
          "focus.status.pausedRemoteDetail",
          "点击继续后，会从当前剩余时间恢复。",
        )
      : t(
          "focus.status.pausedLocalDetail",
          "本地倒计时已暂停，点击继续会从当前剩余时间恢复。",
        )
    : running && transportMode === "bootstrapping"
      ? t(
          "focus.status.bootstrappingDetail",
          "倒计时已经开始，本轮记录和采集会随后准备好。",
        )
      : running && transportMode === "local"
        ? t(
            "focus.status.localDetail",
            "当前只保留本地倒计时，稍后可重新开始正式记录。",
          )
        : running
          ? t(
              "focus.status.liveDetail",
              "新增内容会归入本轮专注，结束后统一查看。",
            )
          : secondsLeft === 0
            ? t(
                "focus.status.doneDetail",
                "你可以查看总结，或直接重置开始下一轮。",
              )
            : t(
                "focus.status.readyDetail",
                "设置目标后点击开始，倒计时会立即启动。",
              );
  const phaseBadgeClass = running
    ? "border-emerald-200/80 bg-emerald-50/90 text-emerald-700"
    : paused
      ? "border-amber-200/80 bg-amber-50/90 text-amber-700"
      : secondsLeft === 0
        ? "border-violet-200/80 bg-violet-50/90 text-violet-700"
        : "border-slate-200/80 bg-slate-50/90 text-slate-600";
  const transportBadgeClass =
    transportMode === "bootstrapping"
      ? "border-cyan-200/80 bg-cyan-50/90 text-cyan-700"
      : transportMode === "live"
        ? "border-sky-200/80 bg-sky-50/90 text-sky-700"
        : transportMode === "local"
          ? "border-amber-200/80 bg-amber-50/90 text-amber-700"
          : "border-slate-200/80 bg-slate-50/90 text-slate-600";

  return (
    <div className="mx-auto w-full max-w-3xl af-glass rounded-[34px] p-6 md:p-8">
      <div className="flex flex-wrap items-center gap-2">
        {FOCUS_DURATIONS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => {
              if (running || paused || (sessionId && !sessionClosed)) {
                return;
              }
              applySelectedDuration(option);
              if (!running) {
                setSecondsLeft(option * 60);
              }
            }}
            disabled={running || paused || (Boolean(sessionId) && !sessionClosed)}
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
                  {focusStateLabel}
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
            void handlePrimaryAction();
          }}
          disabled={secondsLeft === 0 || sessionControlPending}
          className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-55"
        >
          {running
            ? t("focus.pause", "暂停")
            : paused
              ? t("focus.resume", "继续")
              : t("focus.start", "开始")}
        </button>
        <button
          type="button"
          onClick={() => {
            invalidateFocusBootstrap();
            void releaseFocusCollection();
            setPaused(false);
            setRunning(false);
            setSecondsLeft(0);
          }}
          disabled={sessionControlPending}
          className="af-btn af-btn-secondary"
        >
          {t("focus.finishEarly", "提前结束")}
        </button>
        <button
          type="button"
          onClick={async () => {
            invalidateFocusBootstrap();
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
            setTransportMode("idle");
            window.localStorage.removeItem(SESSION_ID_KEY);
            window.localStorage.removeItem(SESSION_GOAL_KEY);
            window.localStorage.setItem(FEED_MODE_KEY, "normal");
          }}
          disabled={sessionControlPending}
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

      <section className="mt-5 rounded-2xl border border-white/85 bg-white/55 px-4 py-4 text-sm text-slate-600">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <p className="af-kicker">{t("focus.statusKicker", "专注状态")}</p>
            <p className="mt-2 text-base font-semibold text-slate-900">{focusStatusTitle}</p>
            <p className="mt-1 text-sm text-slate-500">{focusStatusDetail}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className={`rounded-full border px-3 py-1 text-xs font-medium ${phaseBadgeClass}`}>
              {focusStateLabel}
            </span>
            <span className={`rounded-full border px-3 py-1 text-xs font-medium ${transportBadgeClass}`}>
              {transportBadgeLabel}
            </span>
          </div>
        </div>
        {sessionMessage ? <p className="mt-3 text-xs text-slate-500">{sessionMessage}</p> : null}
      </section>

      {showSourceCollectorCard ? (
        <section className="mt-5 rounded-2xl border border-white/85 bg-white/55 px-4 py-4 text-sm text-slate-600">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="af-kicker">{t("focus.sourceCollectorKicker", "源页面采集")}</p>
              <p className="mt-2 text-base font-semibold text-slate-900">
                {collectorDaemonStatus?.running
                  ? t("focus.sourceCollectorRunning", "Headless 正在后台增量扫描")
                  : t("focus.sourceCollectorLatest", "最近一轮源页面结果")}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {t("focus.sourceCollectorSourceCount", "已配置源")}{" "}
                {collectorDaemonStatus?.source_file_count || 0} ·{" "}
                {t("focus.sourceCollectorProblemSources", "异常源")}{" "}
                {(collectorDaemonStatus?.poor_source_count || 0) +
                  (collectorDaemonStatus?.watch_source_count || 0)} ·{" "}
                {t("focus.sourceCollectorDiscovered", "发现")}{" "}
                {collectorDaemonStatus?.last_run_discovered_count || 0} ·{" "}
                {t("focus.sourceCollectorCollected", "入库")}{" "}
                {collectorDaemonStatus?.last_run_collected_count || 0}
              </p>
            </div>
            <span className={sourceCoverageClass(collectorDaemonStatus?.coverage_state)}>
              {t(
                `focus.sourceCollectorCoverage.${collectorDaemonStatus?.coverage_state || "idle"}`,
                sourceCoverageLabel(collectorDaemonStatus?.coverage_state),
              )}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500 md:grid-cols-4">
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.sourceCollectorCoverageRate", "处理覆盖")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {formatRatioPercent(collectorDaemonStatus?.last_run_coverage_rate)}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.sourceCollectorBodyRate", "正文命中")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {formatRatioPercent(collectorDaemonStatus?.last_run_body_success_rate)}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.sourceCollectorPlugin", "正文抽取")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {collectorDaemonStatus?.last_run_plugin_count || 0}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.sourceCollectorUrlFallback", "链接兜底")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {collectorDaemonStatus?.last_run_url_count || 0}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.sourceCollectorSeen", "历史跳过")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {collectorDaemonStatus?.last_run_skipped_seen_count || 0}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/70 px-3 py-2">
              <p>{t("focus.sourceCollectorFailed", "失败")}</p>
              <p className="mt-1 text-base font-semibold text-slate-900">
                {collectorDaemonStatus?.last_run_failed_count || 0}
              </p>
            </div>
          </div>
          {collectorDaemonStatus?.coverage_recommendation ? (
            <p className="mt-3 text-xs text-slate-500">{collectorDaemonStatus.coverage_recommendation}</p>
          ) : null}
          {problematicSources.length ? (
            <div className="mt-3 space-y-2">
              {problematicSources.map((source) => (
                <div
                  key={source.source_url || source.source_token}
                  className="rounded-xl border border-white/80 bg-white/70 px-3 py-2 text-xs text-slate-500"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-slate-700">{source.source_token}</span>
                    <span className={sourceCoverageClass(source.health_state)}>
                      {t(
                        `focus.sourceCollectorCoverage.${source.health_state}`,
                        sourceCoverageLabel(source.health_state),
                      )}
                    </span>
                  </div>
                  <p className="mt-1">
                    {t("focus.sourceCollectorDiscovered", "发现")} {source.discovered_count} ·{" "}
                    {t("focus.sourceCollectorCollected", "入库")} {source.collected_count} ·{" "}
                    {t("focus.sourceCollectorFailed", "失败")} {source.failed_count}
                  </p>
                  <p className="mt-1">{source.last_error || source.recommendation}</p>
                </div>
              ))}
            </div>
          ) : null}
        </section>
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
              <p>{t("focus.collectorSubmittedOcr", "OCR 补录")}</p>
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
