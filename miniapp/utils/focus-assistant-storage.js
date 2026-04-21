const STORAGE_KEY = "anti_fomo_focus_assistant_latest";
const HISTORY_KEY = "anti_fomo_focus_assistant_history";
const SESSION_ID_KEY = "anti_fomo_session_id";
const MAX_HISTORY = 6;

function buildLatestFocusAssistantResult({
  action,
  channelUsed,
  message,
  task,
  sessionId,
  goalText,
  durationMinutes
}) {
  let fallbackSessionId = "";
  try {
    fallbackSessionId = wx.getStorageSync(SESSION_ID_KEY) || "";
  } catch {
    fallbackSessionId = "";
  }

  return {
    actionKey: action.key,
    actionTitle: action.title,
    channelUsed,
    taskType: (task && task.task_type) || action.task_type || action.key,
    taskStatus: (task && task.status) || "done",
    sessionId: (task && task.session_id) || sessionId || fallbackSessionId || "",
    goalText: goalText || "",
    durationMinutes: durationMinutes || null,
    message: message || "",
    content:
      task && task.output_payload && typeof task.output_payload.content === "string"
        ? task.output_payload.content
        : "",
    createdAt: new Date().toISOString()
  };
}

function setLatestFocusAssistantResult(result) {
  try {
    wx.setStorageSync(STORAGE_KEY, result);
  } catch {
    // ignore storage write failures in demo mode
  }
}

function appendFocusAssistantResult(result) {
  try {
    const nextHistory = [result].concat(getFocusAssistantHistory()).slice(0, MAX_HISTORY);
    wx.setStorageSync(STORAGE_KEY, result);
    wx.setStorageSync(HISTORY_KEY, nextHistory);
  } catch {
    // ignore storage write failures in demo mode
  }
}

function getLatestFocusAssistantResult() {
  try {
    const result = wx.getStorageSync(STORAGE_KEY);
    if (!result || typeof result !== "object") return null;
    if (!result.actionKey || !result.actionTitle) return null;
    return result;
  } catch {
    return null;
  }
}

function getFocusAssistantHistory() {
  try {
    const result = wx.getStorageSync(HISTORY_KEY);
    if (!Array.isArray(result)) return [];
    return result.filter((entry) => entry && typeof entry === "object" && entry.actionKey && entry.actionTitle);
  } catch {
    return [];
  }
}

module.exports = {
  STORAGE_KEY,
  HISTORY_KEY,
  buildLatestFocusAssistantResult,
  setLatestFocusAssistantResult,
  appendFocusAssistantResult,
  getLatestFocusAssistantResult,
  getFocusAssistantHistory
};
