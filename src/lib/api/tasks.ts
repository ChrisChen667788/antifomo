import { request } from "@/lib/api/client";
import type {
  ApiTask,
  WorkBuddyHealth,
  WorkBuddyWebhookResponse,
} from "@/lib/api/types";

export function getWorkBuddyHealth(): Promise<WorkBuddyHealth> {
  return request<WorkBuddyHealth>("/api/workbuddy/health");
}

export function sendWorkBuddyWebhook(payload: {
  event_type: "ping" | "create_task";
  request_id?: string;
  task_type?:
    | "export_markdown_summary"
    | "export_reading_list"
    | "export_todo_draft"
    | "export_knowledge_markdown"
    | "export_research_report_markdown"
    | "export_research_report_word"
    | "export_research_report_pdf"
    | "export_feasibility_study_word"
    | "export_feasibility_study_pdf"
    | "export_project_proposal_word"
    | "export_project_proposal_pdf"
    | "export_research_market_intelligence_markdown"
    | "export_research_solution_delivery_markdown"
    | "export_exec_brief"
    | "export_sales_brief"
    | "export_outreach_draft"
    | "export_watchlist_digest";
  session_id?: string;
  input_payload?: Record<string, unknown>;
  callback?: { url?: string; headers?: Record<string, string> };
}): Promise<WorkBuddyWebhookResponse> {
  return request<WorkBuddyWebhookResponse>("/api/workbuddy/webhook", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createTask(payload: {
  task_type:
    | "export_markdown_summary"
    | "export_reading_list"
    | "export_todo_draft"
    | "export_knowledge_markdown"
    | "export_research_report_markdown"
    | "export_research_report_word"
    | "export_research_report_pdf"
    | "export_feasibility_study_word"
    | "export_feasibility_study_pdf"
    | "export_project_proposal_word"
    | "export_project_proposal_pdf"
    | "export_research_market_intelligence_markdown"
    | "export_research_solution_delivery_markdown"
    | "export_exec_brief"
    | "export_sales_brief"
    | "export_outreach_draft"
    | "export_watchlist_digest";
  session_id?: string;
  input_payload?: Record<string, unknown>;
}): Promise<ApiTask> {
  return request<ApiTask>("/api/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTask(taskId: string): Promise<ApiTask> {
  return request<ApiTask>(`/api/tasks/${taskId}`);
}
