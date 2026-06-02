export interface ApiTask {
  id: string;
  task_type: string;
  status: string;
  session_id?: string | null;
  input_payload?: Record<string, unknown> | null;
  output_payload?: {
    content?: string;
    [key: string]: unknown;
  } | null;
  error_message?: string | null;
}

export interface ApiTaskBriefingContextAccount {
  slug: string;
  name: string;
  objective: string;
  value_hypothesis: string;
  next_meeting_goal: string;
  why_now: string[];
  stakeholders: Array<{
    name: string;
    role: string;
    priority: string;
    next_move: string;
  }>;
  close_plan: Array<{
    title: string;
    owner: string;
    due_window: string;
    exit_criteria: string;
  }>;
  pipeline_risks: Array<{
    title: string;
    severity: string;
    detail: string;
    mitigation: string;
  }>;
}

export interface ApiTaskBriefingContext {
  account?: ApiTaskBriefingContextAccount | null;
  top_accounts: Array<{
    slug: string;
    name: string;
    budget_probability: number;
    next_best_action: string;
  }>;
  top_opportunities: Array<{
    title: string;
    account_name: string;
    budget_probability: number;
    next_step: string;
  }>;
  top_alerts: Array<{
    title: string;
    severity: string;
    summary: string;
    account_name: string;
    recommended_action: string;
  }>;
  review_queue: Array<{
    id: string;
    title: string;
    severity: string;
    summary: string;
    account_name: string;
    recommended_action: string;
    resolution_status: string;
  }>;
}

export interface WorkBuddyHealth {
  status: string;
  signature_required: boolean;
  integration_mode?: string;
  official_tencent_connected?: boolean;
  provider_label?: string;
  requested_mode?: string;
  official_cli_detected?: boolean;
  official_cli_version?: string | null;
  official_cli_authenticated?: boolean;
  official_cli_auth_detail?: string | null;
  official_gateway_configured?: boolean;
  official_gateway_reachable?: boolean;
  official_gateway_url?: string | null;
  official_gateway_status_code?: number | null;
  official_gateway_detail?: string | null;
  active_roles?: string[];
}

export interface WorkBuddyWebhookResponse {
  accepted: boolean;
  event_type: "ping" | "create_task";
  request_id: string | null;
  message: string;
  signature_check: string | null;
  task: ApiTask | null;
  callback: {
    attempted: boolean;
    ok: boolean | null;
    status_code: number | null;
    detail: string | null;
  };
}
