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

export interface ApiResearchSolutionDeliveryPack {
  scenario: string;
  target_customer: string;
  vertical_scene: string;
  source_support_score?: number;
  evidence_policy?: string;
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
  review_checklist: string[];
  next_steps: string[];
  export_markdown: string;
}
