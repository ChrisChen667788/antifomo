export interface ApiResearchTenderProject {
  project_name: string;
  buyer: string;
  region: string;
  industry_or_scene: string;
  notice_type: string;
  publish_date: string;
  amount: string;
  winning_vendor: string;
  bidder_candidates?: string[];
  tender_agency?: string;
  project_code?: string;
  buyer_contact?: string;
  source_title: string;
  source_url: string;
  source_tier: "official" | "media" | "aggregate";
  relevance_score: number;
  extracted_requirements: string[];
  technical_parameters: string[];
}

export interface ApiResearchProductRequirement {
  name: string;
  category: string;
  source_context: string;
  evidence_urls: string[];
  linked_projects: string[];
  technical_parameters: string[];
}

export interface ApiResearchMarketIntelligencePack {
  lookback_years: number;
  window_start: string;
  window_end: string;
  source_scope_summary: string;
  source_support_score?: number;
  validated_source_count?: number;
  ambiguous_source_count?: number;
  rejected_source_count?: number;
  corrective_queries?: string[];
  tender_projects: ApiResearchTenderProject[];
  tender_keywords: string[];
  product_catalog: ApiResearchProductRequirement[];
  technical_parameter_catalog: ApiResearchProductRequirement[];
  external_source_queries: string[];
  intelligence_gaps: string[];
  export_markdown: string;
}

export interface ApiResearchSolutionOutlineSection {
  title: string;
  bullets: string[];
}

export interface ApiResearchDeliveryCompiledSection {
  title: string;
  purpose: string;
  bullets: string[];
  evidence: string[];
  assumptions: string[];
  validation_actions: string[];
}

export interface ApiResearchDeliveryCompiledDocument {
  framework:
    | "solution_design_compiler_v1"
    | "consulting_report_compiler_v1"
    | "project_proposal_compiler_v1"
    | "feasibility_study_compiler_v1";
  document_kind: "solution_design" | "consulting_report" | "project_proposal" | "feasibility_study";
  title: string;
  audience: string;
  purpose: string;
  evidence_policy: string;
  sections: ApiResearchDeliveryCompiledSection[];
  assumptions: string[];
  validation_actions: string[];
  quality_gates: string[];
  export_markdown: string;
}

export interface ApiResearchDecisionCriterionScore {
  criterion_key: string;
  label: string;
  weight_percent: number;
  score: number;
  rationale: string;
}

export interface ApiResearchDecisionAlternativeOption {
  option_id: string;
  name: string;
  summary: string;
  weighted_score: number;
  rank: number;
  criterion_scores: ApiResearchDecisionCriterionScore[];
  decision_rationale: string;
  assumptions: string[];
  validation_actions: string[];
}

export interface ApiResearchTenderScoreResponseItem {
  score_item: string;
  weight_percent: number;
  response_strategy: string;
  mapped_sections: string[];
  evidence_refs: string[];
  owner: string;
  risk_level: "high" | "medium" | "low";
  validation_action: string;
}

export interface ApiResearchFinancialScenario {
  scenario_key: "pessimistic" | "base" | "optimistic";
  label: string;
  capex_cny?: number | null;
  annual_opex_cny?: number | null;
  annual_benefit_cny?: number | null;
  tco_3y_cny?: number | null;
  net_benefit_3y_cny?: number | null;
  payback_months?: number | null;
  npv_3y_cny?: number | null;
  irr_percent?: number | null;
  roi_percent?: number | null;
  confidence: "high" | "medium" | "low";
  assumptions: string[];
}

export interface ApiResearchSensitivityVariable {
  variable_key: string;
  label: string;
  base_value?: number | null;
  low_value?: number | null;
  high_value?: number | null;
  unit: string;
  impact_summary: string;
  validation_action: string;
}

export interface ApiResearchQuantitativeDecisionModel {
  framework: "delivery_quantitative_decision_model_v1";
  status: "ready" | "assumption_required" | "blocked";
  recommended_option_id: string;
  summary: string;
  alternative_options: ApiResearchDecisionAlternativeOption[];
  tender_score_response_matrix: ApiResearchTenderScoreResponseItem[];
  financial_scenarios: ApiResearchFinancialScenario[];
  sensitivity_variables: ApiResearchSensitivityVariable[];
  assumptions: string[];
  validation_actions: string[];
  export_markdown: string;
}

export interface ApiResearchAdvisoryArtifact {
  artifact_type: "client_brief" | "bidding_prep_memo" | "execution_materials";
  title: string;
  audience: string;
  purpose: string;
  source_policy: string;
  markdown: string;
  review_checklist: string[];
}

export interface ApiResearchDeliveryQualityMetric {
  key: string;
  label: string;
  score: number;
  threshold: number;
  status: "pass" | "watch" | "fail";
  summary: string;
  gaps: string[];
  improvement_actions: string[];
}

export interface ApiResearchDeliverySelfReview {
  triggered: boolean;
  before_score: number;
  after_score: number;
  actions: string[];
  added_sections: string[];
  notes: string[];
}

export interface ApiResearchDeliveryNumericFact {
  metric: string;
  raw_value: string;
  normalized_value?: number | null;
  normalized_unit: string;
  context: string;
}

export interface ApiResearchDeliveryEvidenceAnchor {
  evidence_id: string;
  title: string;
  url: string;
  source_label?: string | null;
  source_tier: "official" | "media" | "aggregate";
  anchor_text: string;
  excerpt: string;
  document_ref: string;
  entities: string[];
  numeric_facts: ApiResearchDeliveryNumericFact[];
}

export interface ApiResearchDeliveryClaimEvidenceRelation {
  evidence_id: string;
  relation_type: "supports" | "conflicts" | "background" | "needs_validation";
  score: number;
  rationale: string;
}

export interface ApiResearchDeliveryClaim {
  claim_id: string;
  section_title: string;
  claim_type: "fact" | "numeric" | "recommendation" | "procurement" | "compliance" | "assumption";
  text: string;
  confidence: "high" | "medium" | "low";
  entities: string[];
  numeric_facts: ApiResearchDeliveryNumericFact[];
  evidence_relations: ApiResearchDeliveryClaimEvidenceRelation[];
  verification_status: "supported" | "conflicted" | "background_only" | "needs_validation";
}

export interface ApiResearchDeliveryConsistencyIssue {
  issue_id: string;
  issue_type: "entity_role_conflict" | "entity_not_supported" | "numeric_conflict" | "numeric_unit_mismatch";
  severity: "high" | "medium" | "low";
  claim_ids: string[];
  summary: string;
  details: string[];
}

export interface ApiResearchDeliveryEvidenceLedger {
  framework: "delivery_claim_evidence_ledger_v1";
  claim_count: number;
  evidence_count: number;
  supported_claim_count: number;
  conflicted_claim_count: number;
  background_only_claim_count: number;
  needs_validation_claim_count: number;
  high_confidence_claim_count: number;
  high_confidence_supported_count: number;
  claim_coverage_percent: number;
  high_confidence_coverage_percent: number;
  entity_consistency_score: number;
  numeric_consistency_score: number;
  status: "pass" | "watch" | "fail";
  claims: ApiResearchDeliveryClaim[];
  evidence: ApiResearchDeliveryEvidenceAnchor[];
  consistency_issues: ApiResearchDeliveryConsistencyIssue[];
}

export interface ApiResearchDeliverySemanticChallengeIssue {
  issue_id: string;
  issue_type:
    | "scope_drift"
    | "cross_section_conflict"
    | "unsupported_high_confidence_claim"
    | "source_contamination"
    | "entity_conflict"
    | "numeric_conflict"
    | "template_language"
    | "missing_gold_sample_review";
  severity: "high" | "medium" | "low";
  section_title: string;
  claim_ids: string[];
  summary: string;
  evidence: string[];
  suggested_action: string;
}

export interface ApiResearchDeliverySemanticChallenge {
  framework: "delivery_semantic_challenger_v1";
  status: "pass" | "watch" | "fail";
  overall_score: number;
  issue_count: number;
  high_severity_count: number;
  scope_drift_count: number;
  cross_section_conflict_count: number;
  golden_sample_id: string;
  golden_sample_title: string;
  golden_sample_alignment_score: number;
  issues: ApiResearchDeliverySemanticChallengeIssue[];
  recommended_actions: string[];
}

export interface ApiResearchDeliveryQualityProfile {
  framework: "china_tech_delivery_review_v1";
  framework_label: string;
  review_target: "solution_delivery" | "project_proposal" | "feasibility_study";
  overall_score: number;
  status: "pass" | "watch" | "fail";
  metrics: ApiResearchDeliveryQualityMetric[];
  strengths: string[];
  gaps: string[];
  required_axes: string[];
  missing_axes: string[];
  evidence_ledger?: ApiResearchDeliveryEvidenceLedger;
  semantic_challenge?: ApiResearchDeliverySemanticChallenge;
  self_review: ApiResearchDeliverySelfReview;
}

export interface ApiResearchSolutionArchitectureBlueprintSection {
  title: string;
  purpose: string;
  components: string[];
  evidence: string[];
  open_questions: string[];
}

export interface ApiResearchSolutionArchitectureReadiness {
  framework: "solution_architecture_readiness_v1";
  framework_label: string;
  overall_score: number;
  status: "ready" | "watch" | "blocked";
  summary: string;
  metrics: ApiResearchDeliveryQualityMetric[];
  blueprint_sections: ApiResearchSolutionArchitectureBlueprintSection[];
  non_functional_requirements: string[];
  integration_risks: string[];
  assumptions: string[];
  validation_actions: string[];
  stakeholder_questions: string[];
}

export interface ApiResearchCustomerScenario {
  name: string;
  target_customer: string;
  primary_roles: string[];
  pain_points: string[];
  desired_outcomes: string[];
  success_metrics: string[];
  evidence: string[];
}

export interface ApiResearchSolutionStakeholder {
  role: string;
  influence: "high" | "medium" | "low";
  likely_concerns: string[];
  decision_questions: string[];
  required_materials: string[];
}

export interface ApiResearchSolutionDecisionCriterion {
  criterion: string;
  why_it_matters: string;
  evidence: string[];
  validation_action: string;
}

export interface ApiResearchSolutionCapabilityArchitectureMapping {
  business_capability: string;
  application_services: string[];
  data_dependencies: string[];
  model_dependencies: string[];
  integration_surfaces: string[];
  security_constraints: string[];
  evidence: string[];
  validation_actions: string[];
}

export interface ApiResearchSolutionArchitectureDecisionRecord {
  decision: string;
  context: string;
  options: string[];
  selected_direction: string;
  tradeoffs: string[];
  risks: string[];
  validation_evidence: string[];
}

export interface ApiResearchSolutionIntegrationDependency {
  dependency: string;
  source_system: string;
  api_or_data_contract: string;
  auth_boundary: string;
  deployment_assumption: string;
  operational_owner: string;
  risk_level: "high" | "medium" | "low";
  validation_action: string;
  evidence: string[];
}

export interface ApiResearchSolutionArchitectWorkbench {
  framework: "solution_architect_workbench_v1";
  framework_label: string;
  customer_scenarios: ApiResearchCustomerScenario[];
  stakeholders: ApiResearchSolutionStakeholder[];
  decision_criteria: ApiResearchSolutionDecisionCriterion[];
  capability_architecture_matrix: ApiResearchSolutionCapabilityArchitectureMapping[];
  architecture_decision_records: ApiResearchSolutionArchitectureDecisionRecord[];
  integration_dependencies: ApiResearchSolutionIntegrationDependency[];
  next_meeting_agenda: string[];
}

export interface ApiResearchArchitectureAdrTableRow {
  decision: string;
  context: string;
  selected_direction: string;
  options: string[];
  tradeoffs: string[];
  risks: string[];
  validation_evidence: string[];
  owner: string;
  status: "draft" | "review_ready" | "confirmed";
}

export interface ApiResearchArchitectureDependencyWorkshopItem {
  dependency: string;
  owner: string;
  risk_level: "high" | "medium" | "low";
  source_system: string;
  required_inputs: string[];
  workshop_questions: string[];
  expected_decision: string;
  validation_action: string;
  evidence: string[];
}

export interface ApiResearchArchitectureStakeholderBrief {
  title: string;
  audience: string;
  summary: string;
  key_messages: string[];
  stakeholder_questions: string[];
  required_materials: string[];
  decision_criteria: string[];
}

export interface ApiResearchArchitectureWorkshopAgendaItem {
  topic: string;
  owner: string;
  duration_minutes: number;
  questions: string[];
  expected_outputs: string[];
  source_refs: string[];
}

export interface ApiResearchSolutionArchitectureExportBundle {
  framework: "solution_architecture_export_bundle_v1";
  framework_label: string;
  adr_table: ApiResearchArchitectureAdrTableRow[];
  dependency_workshop_checklist: ApiResearchArchitectureDependencyWorkshopItem[];
  stakeholder_brief: ApiResearchArchitectureStakeholderBrief;
  customer_technical_workshop_agenda: ApiResearchArchitectureWorkshopAgendaItem[];
  export_markdown: string;
}

export interface ApiResearchQualityAttributeScenario {
  scenario_id: string;
  quality_attribute: "availability" | "reliability" | "security" | "performance" | "cost" | "operability" | "maintainability" | "ai_risk";
  business_source: string;
  stimulus: string;
  environment: string;
  artifact: string;
  response: string;
  response_measure: string;
  priority: "high" | "medium" | "low";
  status: "draft" | "confirmed" | "validated";
  evidence: string[];
  acceptance_test_ids: string[];
}

export interface ApiResearchArchitectureOption {
  option_id: string;
  option_type: "baseline" | "pilot" | "target";
  name: string;
  description: string;
  benefits: string[];
  tradeoffs: string[];
  evidence: string[];
  assumptions: string[];
}

export interface ApiResearchArchitectureDecisionRecordV2 {
  adr_id: string;
  title: string;
  status: "proposed" | "accepted" | "validated" | "rejected";
  context: string;
  drivers: string[];
  options: ApiResearchArchitectureOption[];
  selected_option_id: string;
  evidence: string[];
  assumptions: string[];
  consequences: string[];
  rollback_conditions: string[];
  validation_action_ids: string[];
  owner: string;
  due_date: string;
  risk_level: "high" | "medium" | "low";
}

export interface ApiResearchATAMUtilityNode {
  node_id: string;
  quality_attribute: string;
  scenario_ids: string[];
  priority: "high" | "medium" | "low";
  difficulty: "high" | "medium" | "low";
}

export interface ApiResearchATAMFinding {
  finding_id: string;
  finding_type: "risk" | "non_risk" | "sensitivity_point" | "tradeoff_point" | "risk_theme";
  title: string;
  details: string;
  scenario_ids: string[];
  adr_ids: string[];
  owner: string;
}

export interface ApiResearchATAMAssessment {
  framework: "atam_utility_tree_v1";
  utility_tree: ApiResearchATAMUtilityNode[];
  findings: ApiResearchATAMFinding[];
  risk_theme_count: number;
  high_risk_count: number;
}

export interface ApiResearchC4Element {
  element_id: string;
  name: string;
  element_type: "person" | "software_system" | "container" | "component" | "deployment_node";
  description: string;
  technology: string;
  business_scenario_ids: string[];
  data_assets: string[];
  interfaces: string[];
  responsibility_boundary: string;
  quality_scenario_ids: string[];
  deployment_target: string;
}

export interface ApiResearchC4Relationship {
  source_id: string;
  target_id: string;
  description: string;
  interface: string;
  data_flow: string;
}

export interface ApiResearchC4View {
  view_id: string;
  level: "context" | "container" | "component" | "dynamic" | "deployment";
  title: string;
  audience: string;
  element_ids: string[];
  relationships: ApiResearchC4Relationship[];
}

export interface ApiResearchWellArchitectedCheck {
  check_id: string;
  pillar: "reliability" | "security" | "performance" | "cost" | "operations" | "ai_data" | "ai_model" | "ai_content" | "ai_supply_chain" | "ai_human_oversight" | "ai_continuous_monitoring";
  status: "pass" | "watch" | "blocked";
  question: string;
  finding: string;
  evidence: string[];
  action: string;
  owner: string;
}

export interface ApiResearchArchitectureTraceabilityLink {
  requirement_id: string;
  business_requirement: string;
  capability: string;
  component_ids: string[];
  data_assets: string[];
  interfaces: string[];
  deployment_node_ids: string[];
  risk_ids: string[];
  acceptance_test_ids: string[];
}

export interface ApiResearchArchitectureDecisionEngineering {
  framework: "qaw_atam_c4_decision_engineering_v1";
  status: "ready_for_review" | "workshop_only" | "blocked";
  summary: string;
  quality_attribute_scenarios: ApiResearchQualityAttributeScenario[];
  atam: ApiResearchATAMAssessment;
  adrs: ApiResearchArchitectureDecisionRecordV2[];
  c4_elements: ApiResearchC4Element[];
  c4_views: ApiResearchC4View[];
  well_architected_checks: ApiResearchWellArchitectedCheck[];
  traceability_links: ApiResearchArchitectureTraceabilityLink[];
  traceability_coverage_percent: number;
  orphan_component_count: number;
  high_risk_decision_count: number;
  workshop_questions: string[];
  blockers: string[];
}

export interface ApiResearchExecutableValidationCheck {
  check_id: string;
  category: "api_contract" | "representative_data_flow" | "capacity_cost" | "threat_model" | "access_boundary" | "failure_recovery" | "observability" | "rollback" | "customer_confirmation";
  scenario_ids: string[];
  adr_ids: string[];
  input_spec: Record<string, unknown>;
  execution_method: string;
  command: string;
  owner: string;
  due_date: string;
  threshold: string;
  artifact_path: string;
  artifact_sha256: string;
  status: "planned" | "running" | "passed" | "failed" | "human_pending" | "blocked";
  result_summary: string;
  external_evidence_required: boolean;
}

export interface ApiResearchMinimumPrototype {
  prototype_id: string;
  kind: "vertical_simulator" | "executable_prototype";
  scope: string;
  command: string;
  linked_scenario_ids: string[];
  linked_adr_ids: string[];
  status: "not_run" | "passed" | "failed";
  artifact_path: string;
  artifact_sha256: string;
  result_summary: string;
}

export interface ApiResearchAcceptanceEvidence {
  audience: "customer" | "internal";
  confirmed_findings: string[];
  assumptions: string[];
  limitations: string[];
  disputes: string[];
  pending_validations: string[];
  artifact_paths: string[];
}

export interface ApiResearchProofOfArchitecture {
  framework: "proof_of_architecture_v1";
  status: "machine_pass" | "human_pending" | "blocked";
  summary: string;
  checks: ApiResearchExecutableValidationCheck[];
  prototypes: ApiResearchMinimumPrototype[];
  customer_evidence: ApiResearchAcceptanceEvidence;
  internal_evidence: ApiResearchAcceptanceEvidence;
  scenario_test_coverage_percent: number;
  high_risk_decision_evidence_percent: number;
  blockers: string[];
}

export interface ApiResearchCustomerArchitectureTraceabilityItem {
  item_id: string;
  component: string;
  classification: "fact" | "assumption" | "benchmark" | "recommendation";
  statement: string;
  evidence_links: Array<{
    title: string;
    url: string;
    source_label?: string | null;
    source_tier?: "official" | "media" | "aggregate";
    anchor_text?: string | null;
    excerpt?: string;
  }>;
  customer_material_allowed: boolean;
  validation_action: string;
}

export interface ApiResearchCustomerArchitectureTraceability {
  framework: "customer_architecture_traceability_v1";
  status: "ready_for_workshop" | "assumption_required" | "blocked";
  target_account: string;
  facts: ApiResearchCustomerArchitectureTraceabilityItem[];
  assumptions: ApiResearchCustomerArchitectureTraceabilityItem[];
  benchmarks: ApiResearchCustomerArchitectureTraceabilityItem[];
  recommendations: ApiResearchCustomerArchitectureTraceabilityItem[];
  current_estate_questions: string[];
  option_tradeoff_questions: string[];
  blockers: string[];
}

export interface ApiResearchIndustrySkillReference {
  document_id: string;
  title: string;
  document_type: string;
  document_type_label: string;
  published_year?: number | null;
  excerpt: string;
  relevance_score: number;
  verification_note: string;
}

export interface ApiResearchIndustryKnowledgeBase {
  status: "ready" | "partial" | "unavailable" | "not_built";
  generated_at?: string | null;
  document_count: number;
  full_text_document_count: number;
  ocr_document_count: number;
  ocr_pending_count: number;
  unsupported_count: number;
  passage_count: number;
  keyword_index_status: string;
  vector_index_status: string;
  vector_model: string;
  requested_vector_model: string;
  vector_fallback_reason: string;
  hybrid_search_enabled: boolean;
  warnings: string[];
}

export interface ApiResearchIndustryKnowledgeHit {
  passage_id: string;
  document_id: string;
  title: string;
  document_type: string;
  document_type_label: string;
  industry: string;
  locator: string;
  snippet: string;
  match_modes: Array<"keyword" | "vector">;
  keyword_rank?: number | null;
  vector_rank?: number | null;
  vector_score: number;
  fused_score: number;
  verification_note: string;
}

export interface ApiResearchIndustryKnowledgeSearch extends ApiResearchIndustryKnowledgeBase {
  query: string;
  strategy: ApiResearchIndustryKnowledgeStrategyKey;
  strategy_label: string;
  keyword_hit_count: number;
  vector_hit_count: number;
  rerank_requested: boolean;
  rerank_applied: boolean;
  rerank_backend: string;
  rerank_model: string;
  rerank_top_k: number;
  rerank_notes: string[];
  hits: ApiResearchIndustryKnowledgeHit[];
}

export type ApiResearchIndustryKnowledgeStrategyKey =
  | "baseline_hybrid"
  | "prefilter_weighted_hybrid"
  | "prefilter_weighted_rerank";

export interface ApiResearchIndustryKnowledgeRetrievalStrategy {
  key: ApiResearchIndustryKnowledgeStrategyKey;
  label: string;
  description: string;
  default: boolean;
  lexical_prefilter: boolean;
  title_bm25_weight: number;
  rerank_enabled: boolean;
  rerank_top_k: number;
}

export interface ApiResearchIndustryKnowledgeBenchmarkMetric {
  key: "recall_at_10" | "ndcg_at_10" | "citation_hit_rate" | "human_review_score" | "latency_ms";
  label: string;
  value?: number | null;
  baseline_value?: number | null;
  delta?: number | null;
  available: boolean;
  note: string;
}

export interface ApiResearchIndustryKnowledgeBenchmarkCaseResult {
  case_id: string;
  query: string;
  strategy: ApiResearchIndustryKnowledgeStrategyKey;
  result_document_ids: string[];
  retrieved_references: Array<{
    document_id: string;
    title: string;
    locator: string;
    snippet: string;
    match_modes: string[];
  }>;
  recall_at_10: number;
  ndcg_at_10: number;
  citation_hit_rate: number;
  human_review_score?: number | null;
  latency_ms: number;
  rerank_applied: boolean;
  rerank_backend: string;
  rerank_model: string;
  review_note: string;
}

export interface ApiResearchIndustryKnowledgeBenchmarkArm {
  strategy: ApiResearchIndustryKnowledgeStrategyKey;
  label: string;
  role: "baseline" | "candidate";
  case_count: number;
  metrics: ApiResearchIndustryKnowledgeBenchmarkMetric[];
  rerank_applied_case_count: number;
  rerank_backend: string;
  rerank_model: string;
  cases: ApiResearchIndustryKnowledgeBenchmarkCaseResult[];
}

export interface ApiResearchIndustryKnowledgeBenchmarkPromotion {
  decision: "promote" | "hold" | "block";
  candidate_strategy: string;
  reasons: string[];
  required_human_review_case_count: number;
  completed_human_review_case_count: number;
}

export interface ApiResearchIndustryKnowledgeRetrievalBenchmark {
  benchmark_id: string;
  dataset_version: string;
  dataset_sha256: string;
  benchmark_digest: string;
  generated_at: string;
  knowledge_base_generated_at?: string | null;
  knowledge_base_generation_id: string;
  status: "ready" | "partial" | "unavailable";
  case_count: number;
  strategies: ApiResearchIndustryKnowledgeRetrievalStrategy[];
  arms: ApiResearchIndustryKnowledgeBenchmarkArm[];
  promotion: ApiResearchIndustryKnowledgeBenchmarkPromotion;
  artifact_path: string;
  review_template_path: string;
  review_artifact_path: string;
  review_sample_directory: string;
  warnings: string[];
}

export type ApiResearchIndustryKnowledgeRetrievalAssuranceStatus = "pass" | "watch" | "blocked";

export interface ApiResearchIndustryKnowledgeRetrievalAssuranceMetric {
  key: string;
  label: string;
  observed: string;
  target: string;
  status: ApiResearchIndustryKnowledgeRetrievalAssuranceStatus;
  note: string;
}

export interface ApiResearchIndustryKnowledgeRetrievalAssuranceEvidence {
  label: string;
  path: string;
  exists: boolean;
  status: ApiResearchIndustryKnowledgeRetrievalAssuranceStatus;
  summary: string;
}

export interface ApiResearchIndustryKnowledgeRetrievalAssuranceRound {
  index: number;
  version: string;
  key: string;
  title: string;
  status: ApiResearchIndustryKnowledgeRetrievalAssuranceStatus;
  summary: string;
  metrics: ApiResearchIndustryKnowledgeRetrievalAssuranceMetric[];
  next_actions: string[];
  evidence: ApiResearchIndustryKnowledgeRetrievalAssuranceEvidence[];
}

export interface ApiResearchIndustryKnowledgeRetrievalAssuranceSnapshot {
  program_version: string;
  generated_at: string;
  status: ApiResearchIndustryKnowledgeRetrievalAssuranceStatus;
  score: number;
  current_default_strategy: string;
  candidate_strategy: string;
  promotion_decision: "promote" | "hold" | "block";
  benchmark_id: string;
  dataset_sha256: string;
  benchmark_digest: string;
  knowledge_base_generation_id: string;
  case_count: number;
  pass_count: number;
  watch_count: number;
  blocked_count: number;
  rounds: ApiResearchIndustryKnowledgeRetrievalAssuranceRound[];
  artifacts: ApiResearchIndustryKnowledgeRetrievalAssuranceEvidence[];
  next_actions: string[];
  warnings: string[];
}

export interface ApiResearchIndustryKnowledgeRetrievalApprovalTemplate {
  schema_version: string;
  benchmark_id: string;
  dataset_sha256: string;
  knowledge_base_generation_id: string;
  benchmark_digest: string;
  candidate_strategy: string;
  decision: "pending" | "approved" | "rejected";
  approved_by: string;
  approver_role: string;
  approved_at: string;
  attestation: string;
  separation_attestation: string;
  notes: string;
  instructions: string[];
}

export interface ApiResearchIndustryKnowledgeRetrievalEvidenceTemplates {
  benchmark_id: string;
  dataset_sha256: string;
  knowledge_base_generation_id: string;
  candidate_strategy: string;
  approval_template_path: string;
  shadow_template_path: string;
  drift_template_path: string;
  warnings: string[];
}

export interface ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshot {
  program_version: string;
  generated_at: string;
  status: ApiResearchIndustryKnowledgeRetrievalAssuranceStatus;
  score: number;
  parent_program_version: string;
  parent_status: ApiResearchIndustryKnowledgeRetrievalAssuranceStatus;
  current_default_strategy: string;
  candidate_strategy: string;
  benchmark_digest: string;
  evidence_chain_digest: string;
  case_count: number;
  pass_count: number;
  watch_count: number;
  blocked_count: number;
  rounds: ApiResearchIndustryKnowledgeRetrievalAssuranceRound[];
  artifacts: ApiResearchIndustryKnowledgeRetrievalAssuranceEvidence[];
  next_actions: string[];
  warnings: string[];
}

export interface ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates {
  program_version: string;
  benchmark_digest: string;
  incident_register_path: string;
  revocation_record_path: string;
  audit_handoff_path: string;
  created_paths: string[];
  warnings: string[];
  template_summaries: Record<string, string>;
}

export interface ApiResearchIndustryKnowledgeDeliveryReview {
  benchmark_id: string;
  case_id: string;
  query: string;
  source_report_title: string;
  source_report_digest: string;
  generated_at: string;
  artifacts: Array<{
    strategy: ApiResearchIndustryKnowledgeStrategyKey;
    strategy_label: string;
    report_artifact_path: string;
  }>;
  warnings: string[];
}

export interface ApiResearchIndustrySkill {
  skill_id: string;
  name: string;
  industry: string;
  industry_label: string;
  description: string;
  document_count: number;
  full_content_document_count: number;
  document_type_counts: Record<string, number>;
  selection_reason: string;
  guidance: string[];
  quality_checklist: string[];
  learned_outline: string[];
  reference_highlights: string[];
  references: ApiResearchIndustrySkillReference[];
}

export interface ApiResearchIndustrySkillContext {
  status: "available" | "not_selected" | "unavailable";
  catalog_version: string;
  query: string;
  retrieval_strategy: ApiResearchIndustryKnowledgeStrategyKey;
  retrieval_strategy_label: string;
  rerank_applied: boolean;
  rerank_backend: string;
  selected_skills: ApiResearchIndustrySkill[];
  source_document_count: number;
  guidance_summary: string[];
  knowledge_base: ApiResearchIndustryKnowledgeBase;
  retrieval_hits: ApiResearchIndustryKnowledgeHit[];
  warnings: string[];
}

export interface ApiResearchIndustrySkillLibrary {
  status: "available" | "unavailable";
  catalog_version: string;
  generated_at?: string | null;
  document_count: number;
  skill_count: number;
  available_industries: string[];
  knowledge_base: ApiResearchIndustryKnowledgeBase;
  suggested_skills: ApiResearchIndustrySkill[];
  warnings: string[];
}

export interface ApiResearchSolutionDeliveryPack {
  scenario: string;
  target_customer: string;
  vertical_scene: string;
  source_support_score?: number;
  evidence_policy?: string;
  industry_skill_context?: ApiResearchIndustrySkillContext;
  grounding_checks?: string[];
  clarification_questions: string[];
  intelligence_summary: string[];
  compiled_documents?: ApiResearchDeliveryCompiledDocument[];
  quantitative_decision_model?: ApiResearchQuantitativeDecisionModel;
  feasibility_outline: ApiResearchSolutionOutlineSection[];
  project_proposal_outline: ApiResearchSolutionOutlineSection[];
  client_ppt_outline: ApiResearchSolutionOutlineSection[];
  advisory_artifacts: ApiResearchAdvisoryArtifact[];
  evidence_ledger?: ApiResearchDeliveryEvidenceLedger;
  semantic_challenge?: ApiResearchDeliverySemanticChallenge;
  solution_quality_profile?: ApiResearchDeliveryQualityProfile;
  project_proposal_quality_profile?: ApiResearchDeliveryQualityProfile;
  architecture_readiness?: ApiResearchSolutionArchitectureReadiness;
  architect_workbench?: ApiResearchSolutionArchitectWorkbench;
  architecture_export_bundle?: ApiResearchSolutionArchitectureExportBundle;
  architecture_decision_engineering?: ApiResearchArchitectureDecisionEngineering;
  proof_of_architecture?: ApiResearchProofOfArchitecture;
  customer_architecture_traceability?: ApiResearchCustomerArchitectureTraceability;
  review_checklist: string[];
  next_steps: string[];
  export_markdown: string;
}
