import type { AppLanguage } from "@/lib/preferences";
import type { ApiTask } from "@/lib/api/type-contracts/tasks";

export interface ApiSessionArtifactItem {
  id: string;
  item_id?: string | null;
  position: number;
  included_reason?: string | null;
  title_snapshot: string;
  source_url_snapshot?: string | null;
  created_at: string;
}

export interface ApiSessionArtifact {
  id: string;
  work_task_id: string;
  session_id?: string | null;
  artifact_type: string;
  markdown: string;
  created_at: string;
  items: ApiSessionArtifactItem[];
}

export interface ApiSessionMetrics {
  new_content_count: number;
  deep_read_count: number;
  later_count: number;
  skip_count: number;
}

export interface ApiSessionItem {
  id: string;
  title: string | null;
  source_domain: string | null;
  short_summary: string | null;
  action_suggestion: string | null;
  score_value: number | null;
  tags: string[];
}

export interface ApiSession {
  id: string;
  goal_text: string | null;
  output_language?: AppLanguage;
  duration_minutes: number;
  start_time: string;
  current_window_started_at?: string | null;
  paused_at?: string | null;
  elapsed_seconds?: number;
  remaining_seconds?: number;
  end_time?: string | null;
  status: string;
  summary_text: string | null;
  metrics: ApiSessionMetrics;
  items: ApiSessionItem[];
}

export interface ApiTodoCalendarEvent {
  title: string;
  notes: string;
  start_time: string;
  end_time: string;
}

export interface ApiTodoCalendarPreview {
  calendar_name: string;
  summary_title: string;
  task_count: number;
  tasks: string[];
  events: ApiTodoCalendarEvent[];
  markdown: string;
}

export interface ApiTodoCalendarImportResult {
  calendar_name: string;
  imported_count: number;
  imported_titles: string[];
}

export interface FocusAssistantAction {
  key:
    | "reading_digest"
    | "session_markdown_summary"
    | "todo_draft"
    | "focus_reference_bundle"
    | "personal_wechat_auto_send";
  title: string;
  description: string;
  available: boolean;
  reason?: string | null;
  task_type?: string | null;
  session_required?: boolean;
  steps: string[];
  handoff_prompt?: string | null;
}

export interface FocusAssistantPlan {
  goal_text?: string | null;
  duration_minutes?: number | null;
  output_language: AppLanguage;
  latest_session_id?: string | null;
  latest_session_status?: string | null;
  focus_reference_count: number;
  focus_reference_ids: string[];
  focus_reference_titles: string[];
  summary: string;
  actions: FocusAssistantAction[];
  blocked_actions: FocusAssistantAction[];
  guardrails: string[];
}

export interface FocusAssistantExecution {
  accepted: boolean;
  action_key: FocusAssistantAction["key"];
  channel_used: "workbuddy" | "direct";
  message: string;
  task: ApiTask | null;
}
