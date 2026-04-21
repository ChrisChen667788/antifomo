import type { ApiTask, FocusAssistantAction } from "@/lib/api";

export const FOCUS_ASSISTANT_RESULT_KEY = "anti_fomo_focus_assistant_latest";
export const FOCUS_ASSISTANT_HISTORY_KEY = "anti_fomo_focus_assistant_history";
const SESSION_ID_KEY = "anti_fomo_session_id";
const MAX_HISTORY = 6;

export interface StoredFocusAssistantResult {
  actionKey: FocusAssistantAction["key"];
  actionTitle: string;
  channelUsed: "workbuddy" | "direct";
  taskType: string;
  taskStatus: string;
  sessionId: string | null;
  goalText: string | null;
  durationMinutes: number | null;
  message: string;
  content: string;
  createdAt: string;
}

export function buildStoredFocusAssistantResult({
  action,
  channelUsed,
  message,
  task,
  sessionId,
  goalText,
  durationMinutes,
}: {
  action: FocusAssistantAction;
  channelUsed: "workbuddy" | "direct";
  message: string;
  task: ApiTask | null;
  sessionId?: string | null;
  goalText?: string | null;
  durationMinutes?: number | null;
}): StoredFocusAssistantResult {
  return {
    actionKey: action.key,
    actionTitle: action.title,
    channelUsed,
    taskType: task?.task_type || action.task_type || action.key,
    taskStatus: task?.status || "done",
    sessionId:
      task?.session_id ||
      sessionId ||
      (typeof window !== "undefined" ? window.localStorage.getItem(SESSION_ID_KEY) : null),
    goalText: goalText || null,
    durationMinutes: durationMinutes || null,
    message,
    content:
      typeof task?.output_payload?.content === "string" ? task.output_payload.content : "",
    createdAt: new Date().toISOString(),
  };
}

export function writeLatestFocusAssistantResult(result: StoredFocusAssistantResult): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(FOCUS_ASSISTANT_RESULT_KEY, JSON.stringify(result));
  } catch {
    // ignore storage write failures in demo mode
  }
}

export function appendFocusAssistantResult(result: StoredFocusAssistantResult): void {
  if (typeof window === "undefined") return;
  try {
    const nextHistory = [result, ...readFocusAssistantHistory()].slice(0, MAX_HISTORY);
    window.localStorage.setItem(FOCUS_ASSISTANT_RESULT_KEY, JSON.stringify(result));
    window.localStorage.setItem(FOCUS_ASSISTANT_HISTORY_KEY, JSON.stringify(nextHistory));
  } catch {
    // ignore storage write failures in demo mode
  }
}

export function readLatestFocusAssistantResult(): StoredFocusAssistantResult | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(FOCUS_ASSISTANT_RESULT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredFocusAssistantResult;
    if (!parsed || typeof parsed !== "object") return null;
    if (!parsed.actionKey || !parsed.actionTitle) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function readFocusAssistantHistory(): StoredFocusAssistantResult[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(FOCUS_ASSISTANT_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StoredFocusAssistantResult[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((entry) => entry && typeof entry === "object" && entry.actionKey && entry.actionTitle);
  } catch {
    return [];
  }
}
