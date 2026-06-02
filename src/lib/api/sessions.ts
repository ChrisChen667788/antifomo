import type { AppLanguage } from "@/lib/preferences";
import { request } from "@/lib/api/client";
import type {
  ApiSession,
  ApiSessionArtifact,
  ApiTodoCalendarImportResult,
  ApiTodoCalendarPreview,
  FocusAssistantAction,
  FocusAssistantExecution,
  FocusAssistantPlan,
} from "@/lib/api/types";

export function startSession(payload: {
  goal_text?: string;
  duration_minutes: number;
  output_language?: AppLanguage;
}) {
  return request("/api/sessions/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function finishSession(
  sessionId: string,
  payload?: {
    output_language?: AppLanguage;
  },
) {
  return request<{ session: ApiSession }>(`/api/sessions/${sessionId}/finish`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  }).then((response) => response.session);
}

export function pauseSession(sessionId: string): Promise<ApiSession> {
  return request<{ session: ApiSession }>(`/api/sessions/${sessionId}/pause`, {
    method: "POST",
  }).then((response) => response.session);
}

export function resumeSession(sessionId: string): Promise<ApiSession> {
  return request<{ session: ApiSession }>(`/api/sessions/${sessionId}/resume`, {
    method: "POST",
  }).then((response) => response.session);
}

export function getSession(sessionId: string): Promise<ApiSession> {
  return request<ApiSession>(`/api/sessions/${sessionId}`);
}

export function getLatestSession(): Promise<ApiSession> {
  return request<ApiSession>("/api/sessions/latest");
}

export function getSessionArtifacts(sessionId: string): Promise<ApiSessionArtifact[]> {
  return request<ApiSessionArtifact[]>(`/api/sessions/${sessionId}/artifacts`);
}

export function previewTodoCalendarImport(
  sessionId: string,
  payload?: {
    output_language?: AppLanguage;
    calendar_name?: string;
    todo_markdown?: string;
  },
): Promise<ApiTodoCalendarPreview> {
  return request<ApiTodoCalendarPreview>(`/api/sessions/${sessionId}/todo-calendar-preview`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function importTodoCalendar(
  sessionId: string,
  payload?: {
    output_language?: AppLanguage;
    calendar_name?: string;
    todo_markdown?: string;
  },
): Promise<ApiTodoCalendarImportResult> {
  return request<ApiTodoCalendarImportResult>(`/api/sessions/${sessionId}/todo-calendar-import`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function createFocusAssistantPlan(payload: {
  goal_text?: string;
  duration_minutes?: number;
  session_id?: string;
  output_language?: AppLanguage;
}): Promise<FocusAssistantPlan> {
  return request<FocusAssistantPlan>("/api/focus-assistant/plan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function executeFocusAssistantAction(payload: {
  action_key: FocusAssistantAction["key"];
  goal_text?: string;
  duration_minutes?: number;
  session_id?: string;
  output_language?: AppLanguage;
  channel?: "workbuddy" | "direct";
}): Promise<FocusAssistantExecution> {
  return request<FocusAssistantExecution>("/api/focus-assistant/execute", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
