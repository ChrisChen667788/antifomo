export interface ApiResearchSectionEvidencePack {
  section_title: string;
  status: "ready" | "degraded" | "needs_evidence";
  support_score: number;
  evidence_count: number;
  official_evidence_count: number;
  quota_gap: number;
  source_titles: string[];
  risks: string[];
  next_steps: string[];
}

export interface ApiResearchSectionRetrievalHit {
  chunk_id: string;
  document_id: string;
  document_type: string;
  title: string;
  snippet: string;
  field_key: string;
  label: string;
  source_tier: "official" | "media" | "aggregate";
  source_url: string;
  score: number;
  matched_terms: string[];
  match_modes: string[];
}

export interface ApiResearchSectionRetrievalPack {
  section_title: string;
  query: string;
  target_axes: string[];
  status: "ready" | "degraded" | "needs_evidence";
  hit_count: number;
  official_hit_count: number;
  support_score: number;
  hits: ApiResearchSectionRetrievalHit[];
  missing_terms: string[];
  next_steps: string[];
}

export interface ApiResearchRetrievalIndexRebuildResult {
  user_id: string;
  schema_version: number;
  total_chunks: number;
  indexed_chunks: number;
  start_offset: number;
  next_offset: number;
  completed: boolean;
  batch_commits: number;
  source_counts: Record<string, number>;
  backend: string;
  checkpoint_status: "idle" | "running" | "completed" | "failed" | string;
  message: string;
}

export interface ApiResearchRetrievalIndexStatus {
  user_id: string;
  schema_version: number;
  backend: string;
  checkpoint_status: "idle" | "running" | "completed" | "failed" | string;
  total_chunks: number;
  indexed_chunks: number;
  next_offset: number;
  progress_percent: number;
  persisted_chunk_count: number;
  parent_link_count: number;
  orphan_child_count: number;
  remaining_chunks: number;
  persisted_reuse_percent: number;
  checkpoint_resume_ready: boolean;
  cache_health: "cold" | "warming" | "warm" | "stale";
  recovery_mode: "none" | "resume" | "reset_recommended";
  recovery_recommendation: string;
  source_counts: Record<string, number>;
  document_type_counts: Record<string, number>;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
}

export interface ApiResearchRetrievalIndexSearchHit {
  chunk_id: string;
  document_id: string;
  document_type: string;
  title: string;
  snippet: string;
  field_key: string;
  label: string;
  source_tier: "official" | "media" | "aggregate";
  source_url: string;
  parent_chunk_id: string;
  topic_id: string;
  topic_name: string;
  region: string;
  industry: string;
  score: number;
  matched_terms: string[];
  match_modes: string[];
  metadata: Record<string, unknown>;
}

export interface ApiResearchRetrievalIndexSearchResult {
  query: string;
  hit_count: number;
  hits: ApiResearchRetrievalIndexSearchHit[];
  runtime_strategy_status: "ready" | "degraded" | "fallback";
  runtime_strategy_config: Record<string, unknown>;
  runtime_strategy_warnings: string[];
}
