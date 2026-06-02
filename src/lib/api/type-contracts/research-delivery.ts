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
  feasibility_outline: ApiResearchSolutionOutlineSection[];
  project_proposal_outline: ApiResearchSolutionOutlineSection[];
  client_ppt_outline: ApiResearchSolutionOutlineSection[];
  advisory_artifacts: ApiResearchAdvisoryArtifact[];
  solution_quality_profile?: ApiResearchDeliveryQualityProfile;
  project_proposal_quality_profile?: ApiResearchDeliveryQualityProfile;
  architecture_readiness?: ApiResearchSolutionArchitectureReadiness;
  architect_workbench?: ApiResearchSolutionArchitectWorkbench;
  review_checklist: string[];
  next_steps: string[];
  export_markdown: string;
}
