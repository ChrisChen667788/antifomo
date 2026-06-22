"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getLatestSession,
  getWorkBuddyHealth,
  sendWorkBuddyWebhook,
  type WorkBuddyHealth,
  type WorkBuddyWebhookResponse,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import type { AppLanguage } from "@/lib/preferences";
import { WorkBuddyMark } from "@/components/ui/workbuddy-mark";

type WorkBuddyTaskType =
  | "export_markdown_summary"
  | "export_reading_list"
  | "export_todo_draft";

function pickText(
  language: AppLanguage,
  mapping: Partial<Record<AppLanguage, string>>,
  fallback: string,
): string {
  if (mapping[language]) return mapping[language] as string;
  if (language === "zh-TW" && mapping["zh-CN"]) return mapping["zh-CN"] as string;
  if (mapping.en) return mapping.en as string;
  return fallback;
}

function localText(language: AppLanguage, key: string): string {
  const map: Record<string, Partial<Record<AppLanguage, string>>> = {
    title: {
      "zh-CN": "导出通道",
      "zh-TW": "導出通道",
      en: "Export Channel",
      ja: "エクスポートチャネル",
      ko: "내보내기 채널",
    },
    description: {
      "zh-CN": "检查导出服务是否可用，并试运行一次导出。",
      "zh-TW": "檢查導出服務是否可用，並試運行一次導出。",
      en: "Check whether export service is available and run a test export.",
      ja: "エクスポートサービスが利用可能か確認し、テスト出力を実行します。",
      ko: "내보내기 서비스를 확인하고 테스트 내보내기를 실행합니다.",
    },
    statusTitle: {
      "zh-CN": "通道状态",
      "zh-TW": "通道狀態",
      en: "Channel Status",
      ja: "チャネル状態",
      ko: "채널 상태",
    },
    healthy: {
      "zh-CN": "已就绪",
      "zh-TW": "已就緒",
      en: "Ready",
      ja: "準備完了",
      ko: "준비됨",
    },
    signatureOn: {
      "zh-CN": "签名校验：开启",
      "zh-TW": "簽名校驗：開啟",
      en: "Signature: enabled",
      ja: "署名検証: 有効",
      ko: "서명 검증: 사용",
    },
    signatureOff: {
      "zh-CN": "签名校验：关闭",
      "zh-TW": "簽名校驗：關閉",
      en: "Signature: disabled",
      ja: "署名検証: 無効",
      ko: "서명 검증: 사용 안 함",
    },
    latestSession: {
      "zh-CN": "最近专注记录",
      "zh-TW": "最近專注記錄",
      en: "Latest Focus Record",
      ja: "最新の集中記録",
      ko: "최근 집중 기록",
    },
    noSession: {
      "zh-CN": "暂无可用专注记录",
      "zh-TW": "暫無可用專注記錄",
      en: "No focus record available.",
      ja: "利用可能な集中記録がありません。",
      ko: "사용 가능한 집중 기록이 없습니다.",
    },
    refresh: {
      "zh-CN": "刷新状态",
      "zh-TW": "刷新狀態",
      en: "Refresh",
      ja: "更新",
      ko: "새로고침",
    },
    ping: {
      "zh-CN": "发送 Ping",
      "zh-TW": "發送 Ping",
      en: "Send Ping",
      ja: "Ping 送信",
      ko: "Ping 보내기",
    },
    markdown: {
      "zh-CN": "导出 Markdown",
      "zh-TW": "導出 Markdown",
      en: "Export Markdown",
      ja: "Markdown 出力",
      ko: "Markdown 내보내기",
    },
    readingList: {
      "zh-CN": "导出稍后读",
      "zh-TW": "導出稍後讀",
      en: "Export Reading List",
      ja: "後で読む一覧",
      ko: "읽기 목록 내보내기",
    },
    todoDraft: {
      "zh-CN": "导出待办草稿",
      "zh-TW": "導出待辦草稿",
      en: "Export Todo Draft",
      ja: "TODO 下書き出力",
      ko: "할 일 초안 내보내기",
    },
    running: {
      "zh-CN": "执行中...",
      "zh-TW": "執行中...",
      en: "Running...",
      ja: "実行中...",
      ko: "실행 중...",
    },
    messageReady: {
      "zh-CN": "导出通道可用。",
      "zh-TW": "導出通道可用。",
      en: "Export channel is available.",
      ja: "エクスポートチャネルは利用可能です。",
      ko: "내보내기 채널을 사용할 수 있습니다.",
    },
    messagePingDone: {
      "zh-CN": "Ping 已返回 pong。",
      "zh-TW": "Ping 已返回 pong。",
      en: "Ping returned pong.",
      ja: "Ping は pong を返しました。",
      ko: "Ping 이 pong 을 반환했습니다.",
    },
    messageTaskDone: {
      "zh-CN": "导出任务已完成。",
      "zh-TW": "導出任務已完成。",
      en: "Export task completed.",
      ja: "エクスポートタスクが完了しました。",
      ko: "내보내기 작업이 완료되었습니다.",
    },
    messageNeedSession: {
      "zh-CN": "该任务需要专注记录，先完成一轮 Focus。",
      "zh-TW": "該任務需要專注記錄，先完成一輪 Focus。",
      en: "This task requires a session. Finish one Focus block first.",
      ja: "このタスクには集中記録が必要です。先に Focus を完了してください。",
      ko: "이 작업에는 집중 기록이 필요합니다. 먼저 Focus 를 완료하세요.",
    },
    messageFailed: {
      "zh-CN": "导出通道调用失败。",
      "zh-TW": "導出通道調用失敗。",
      en: "Export channel call failed.",
      ja: "エクスポートチャネルの呼び出しに失敗しました。",
      ko: "내보내기 채널 호출에 실패했습니다.",
    },
    outputTitle: {
      "zh-CN": "最近输出",
      "zh-TW": "最近輸出",
      en: "Latest Output",
      ja: "最新出力",
      ko: "최근 출력",
    },
    emptyOutput: {
      "zh-CN": "这里会显示最近一次任务结果。",
      "zh-TW": "這裡會顯示最近一次任務結果。",
      en: "The latest task result will appear here.",
      ja: "最新の webhook タスク結果をここに表示します。",
      ko: "가장 최근 webhook 작업 결과가 여기에 표시됩니다.",
    },
    modeTitle: {
      "zh-CN": "连接方式",
      "zh-TW": "連接方式",
      en: "Connection Mode",
    },
    modeLocal: {
      "zh-CN": "当前使用本地导出服务。",
      "zh-TW": "目前使用本地導出服務。",
      en: "Using the local export service.",
    },
    modeOfficialOff: {
      "zh-CN": "官方账号：未连接",
      "zh-TW": "官方帳號：未連線",
      en: "Tencent official account: not connected",
    },
    cliDetected: {
      "zh-CN": "本机工具：已检测",
      "zh-TW": "本機工具：已檢測",
      en: "Official CLI: detected",
    },
    cliMissing: {
      "zh-CN": "本机工具：未检测到",
      "zh-TW": "本機工具：未檢測到",
      en: "Official CLI: not found",
    },
    cliAuthenticated: {
      "zh-CN": "本机工具：已登录",
      "zh-TW": "本機工具：已登入",
      en: "Official CLI: authenticated",
    },
    cliLoginRequired: {
      "zh-CN": "本机工具：需要登录",
      "zh-TW": "本機工具：需要登入",
      en: "Official CLI: CodeBuddy login required",
    },
    gatewayReady: {
      "zh-CN": "官方服务：已连通",
      "zh-TW": "官方服務：已連通",
      en: "Official gateway: reachable",
    },
    gatewayMissing: {
      "zh-CN": "官方服务：未配置",
      "zh-TW": "官方服務：未配置",
      en: "Official gateway: not configured",
    },
    gatewayDown: {
      "zh-CN": "官方服务：已配置但未连通",
      "zh-TW": "官方服務：已配置但未連通",
      en: "Official gateway: configured but unreachable",
    },
    gatewayUrl: {
      "zh-CN": "服务地址",
      "zh-TW": "服務位址",
      en: "Gateway URL",
    },
    gatewayHint: {
      "zh-CN": "若要切到官方服务，需要先完成登录并启动对应服务。",
      "zh-TW": "若要切到官方服務，需要先完成登入並啟動對應服務。",
      en: "To switch to the Tencent official path, complete CodeBuddy login and start the official gateway first.",
    },
    rolesTitle: {
      "zh-CN": "当前实际作用",
      "zh-TW": "目前實際作用",
      en: "Current Roles",
    },
    verifyHint: {
      "zh-CN": "验证方法：先点 Ping，再触发导出任务；成功后下方会出现真实返回结果。",
      "zh-TW": "驗證方式：先點 Ping，再觸發導出任務；成功後下方會出現真實返回結果。",
      en: "Verification: ping first, then trigger an export task. Real output appears below on success.",
    },
  };
  return pickText(language, map[key], key);
}

function buildRequestId(prefix: string) {
  return `${prefix}_${Date.now()}`;
}

export function WorkBuddyPanel() {
  const { preferences } = useAppPreferences();
  const language = preferences.language;
  const [health, setHealth] = useState<WorkBuddyHealth | null>(null);
  const [latestSessionId, setLatestSessionId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [lastOutput, setLastOutput] = useState("");

  const refreshStatus = useCallback(async () => {
    setLoading(true);
    try {
      const [healthRes, latestSession] = await Promise.allSettled([
        getWorkBuddyHealth(),
        getLatestSession(),
      ]);

      if (healthRes.status === "fulfilled") {
        setHealth(healthRes.value);
        setMessage(localText(language, "messageReady"));
      }

      if (latestSession.status === "fulfilled") {
        setLatestSessionId(latestSession.value.id);
      } else {
        setLatestSessionId("");
      }
    } catch {
      setMessage(localText(language, "messageFailed"));
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => {
    void refreshStatus();
    // language change should refresh panel copy and session availability.
  }, [refreshStatus]);

  const runWebhook = async (
    eventType: "ping" | "create_task",
    taskType?: WorkBuddyTaskType,
  ) => {
    if (loading) return;
    if (
      eventType === "create_task" &&
      taskType &&
      taskType !== "export_reading_list" &&
      !latestSessionId
    ) {
      setMessage(localText(language, "messageNeedSession"));
      return;
    }

    setLoading(true);
    try {
      const payload =
        eventType === "ping"
          ? {
              event_type: "ping" as const,
              request_id: buildRequestId("wb_ping"),
            }
          : {
              event_type: "create_task" as const,
              request_id: buildRequestId("wb_task"),
              task_type: taskType,
              session_id:
                taskType !== "export_reading_list" ? latestSessionId || undefined : undefined,
              input_payload: {
                output_language: language,
              },
            };

      const result: WorkBuddyWebhookResponse = await sendWorkBuddyWebhook(payload);
      if (result.event_type === "ping") {
        setMessage(localText(language, "messagePingDone"));
        setLastOutput("");
      } else {
        setMessage(localText(language, "messageTaskDone"));
        setLastOutput(result.task?.output_payload?.content ? String(result.task.output_payload.content) : "");
      }
    } catch {
      setMessage(localText(language, "messageFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <div className="flex items-center gap-3">
        <WorkBuddyMark size={20} />
        <p className="af-kicker">{localText(language, "title")}</p>
      </div>
      <p className="mt-2 text-sm text-slate-500">{localText(language, "description")}</p>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-white/85 bg-white/55 p-4">
          <p className="text-sm font-semibold text-slate-800">{localText(language, "statusTitle")}</p>
          <p className="mt-2 text-sm text-slate-600">
            {health?.status === "ok" ? localText(language, "healthy") : "暂不可用"}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {health?.signature_required
              ? localText(language, "signatureOn")
              : localText(language, "signatureOff")}
          </p>
          <p className="mt-3 text-xs text-slate-500">
            {localText(language, "latestSession")}:
            {" "}
            {latestSessionId || localText(language, "noSession")}
          </p>
          <div className="mt-4 rounded-2xl border border-slate-200/80 bg-white/75 p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              {localText(language, "modeTitle")}
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-700">
              {health?.provider_label || localText(language, "modeLocal")}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              {health?.official_tencent_connected
                ? "Tencent official account: connected"
                : localText(language, "modeOfficialOff")}
            </p>
            <div className="mt-3 space-y-1 text-xs text-slate-500">
              <p>
                {health?.official_cli_detected
                  ? `${localText(language, "cliDetected")}${health?.official_cli_version ? ` · ${health.official_cli_version}` : ""}`
                  : localText(language, "cliMissing")}
              </p>
              {health?.official_cli_detected ? (
                <p>
                  {health?.official_cli_authenticated
                    ? localText(language, "cliAuthenticated")
                    : localText(language, "cliLoginRequired")}
                </p>
              ) : null}
              <p>
                {health?.official_gateway_reachable
                  ? localText(language, "gatewayReady")
                  : health?.official_gateway_configured
                    ? localText(language, "gatewayDown")
                    : localText(language, "gatewayMissing")}
              </p>
              {health?.official_gateway_url ? (
                <p>
                  {localText(language, "gatewayUrl")}: {health.official_gateway_url}
                </p>
              ) : null}
              {health?.official_cli_auth_detail ? <p>{health.official_cli_auth_detail}</p> : null}
              {health?.official_gateway_detail ? <p>{health.official_gateway_detail}</p> : null}
            </div>
            <p className="mt-3 text-xs text-slate-500">{localText(language, "gatewayHint")}</p>
          </div>
        </div>

        <div className="rounded-2xl border border-white/85 bg-white/55 p-4">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void refreshStatus()}
              disabled={loading}
              className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? localText(language, "running") : localText(language, "refresh")}
            </button>
            <button
              type="button"
              onClick={() => void runWebhook("ping")}
              disabled={loading}
              className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
            >
              <WorkBuddyMark size={14} />
              {loading ? localText(language, "running") : localText(language, "ping")}
            </button>
            <button
              type="button"
              onClick={() => void runWebhook("create_task", "export_markdown_summary")}
              disabled={loading}
              className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              <WorkBuddyMark size={14} />
              {loading ? localText(language, "running") : localText(language, "markdown")}
            </button>
            <button
              type="button"
              onClick={() => void runWebhook("create_task", "export_reading_list")}
              disabled={loading}
              className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
            >
              <WorkBuddyMark size={14} />
              {loading ? localText(language, "running") : localText(language, "readingList")}
            </button>
            <button
              type="button"
              onClick={() => void runWebhook("create_task", "export_todo_draft")}
              disabled={loading}
              className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
            >
              <WorkBuddyMark size={14} />
              {loading ? localText(language, "running") : localText(language, "todoDraft")}
            </button>
          </div>
          {message ? <p className="mt-3 text-xs text-slate-500">{message}</p> : null}
          <p className="mt-3 text-xs text-slate-500">{localText(language, "verifyHint")}</p>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/85 bg-white/55 p-4">
        <p className="text-sm font-semibold text-slate-800">{localText(language, "rolesTitle")}</p>
        <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
          {(health?.active_roles || []).map((role) => (
            <li key={role} className="flex gap-2">
              <span className="mt-[9px] h-1.5 w-1.5 rounded-full bg-sky-400" />
              <span>{role}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4 rounded-2xl border border-white/85 bg-slate-950 px-4 py-4 text-sm text-slate-100">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
          {localText(language, "outputTitle")}
        </p>
        <pre className="mt-3 whitespace-pre-wrap break-words font-mono text-[12px] leading-6 text-slate-100">
          {lastOutput || localText(language, "emptyOutput")}
        </pre>
      </div>
    </section>
  );
}
