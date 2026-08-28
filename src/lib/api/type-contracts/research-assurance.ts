export type ApiResearchAssuranceStatus = "pass" | "watch" | "blocked";

export interface ApiResearchAssuranceMetric {
  key: string;
  label: string;
  observed: string;
  target: string;
  status: ApiResearchAssuranceStatus;
  summary: string;
}

export interface ApiResearchAssuranceRound {
  index: number;
  version: string;
  key: string;
  label: string;
  status: ApiResearchAssuranceStatus;
  score: number;
  summary: string;
  metrics: ApiResearchAssuranceMetric[];
  next_actions: string[];
}

export interface ApiResearchAssuranceSnapshot {
  generated_at: string;
  program_version: string;
  status: ApiResearchAssuranceStatus;
  score: number;
  report_sample_size: number;
  valid_report_count: number;
  invalid_report_count: number;
  rounds: ApiResearchAssuranceRound[];
  summary_lines: string[];
  next_actions: string[];
}
