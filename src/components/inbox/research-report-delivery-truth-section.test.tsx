import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResearchReportDeliveryTruthSection } from "@/components/inbox/research-report-delivery-truth-section";
import type { ApiResearchReport } from "@/lib/api/types";

describe("ResearchReportDeliveryTruthSection", () => {
  it("shows an account card and plain-language evidence boundary", () => {
    const report = {
      delivery_truth: {
        framework: "research_delivery_truth_v1",
        status: "provisional",
        delivery_mode: "account_pursuit",
        formal_delivery_allowed: false,
        customer_material_allowed: false,
        section_confidence_cap: "low",
        decisive_reasons: ["引用仍需补齐，当前仅限内部候选推进。"],
        blocking_gate_keys: ["citation"],
        next_action: "补齐采购公告原文后重新生成正式版本。",
      },
      research_evidence_gate: {
        framework: "research_evidence_gate_v1",
        enforced: true,
        status: "evidence_gap",
        passed: false,
        formal_report_allowed: false,
        solution_delivery_allowed: false,
        minimum_source_count: 8,
        minimum_official_source_count: 3,
        minimum_unique_domain_count: 5,
        minimum_question_coverage_percent: 80,
        candidate_source_count: 8,
        accepted_source_count: 8,
        ambiguous_source_count: 0,
        rejected_source_count: 0,
        official_source_count: 3,
        unique_domain_count: 5,
        question_coverage_percent: 90,
        local_target_proof_count: 1,
        local_decision_source_count: 2,
        external_benchmark_count: 1,
        blockers: [],
        warnings: [],
        next_actions: [],
      },
      account_pursuit_pack: {
        framework: "account_pursuit_research_v1",
        status: "ready",
        summary: "已锁定本地账户。",
        verified_account_count: 1,
        market_scan_actions: [],
        blockers: [],
        cards: [{
          account_name: "上海市文化和旅游局",
          account_role: "采购人",
          status: "verified",
          confidence: "high",
          current_signal: "已发布智慧场馆人工智能采购意向。",
          signal_kind: "procurement",
          procurement_stage: "intent",
          budget_signal: "金额待公开确认。",
          incumbent_or_partner: "待核验",
          facts: [],
          inferences: [],
          evidence_links: [{ title: "采购意向", url: "https://sh.gov.cn/procurement" }],
          next_proof_sources: [],
          next_action: "核验采购范围和业务归口。",
          timebox: "10 个工作日",
        }],
      },
      commercial_bid_pack: {
        framework: "commercial_bid_engineering_v1",
        status: "ready_for_review",
        account_name: "上海市文化和旅游局",
        buyer_map: [{ role: "采购人", organization: "上海市文化和旅游局", status: "verified", evidence_links: [], next_proof: "核验采购公告" }],
        budget_route: "待核验",
        procurement_calendar: [],
        competitor_or_incumbent_evidence: [],
        partner_role_fit: [],
        qualification_plan: [],
        win_themes: [],
        loss_risks: [],
        no_bid_triggers: ["采购范围与能力不匹配时暂停投入。"],
        next_actions: ["组织会前需求澄清。"],
        blockers: [],
      },
      solution_delivery_pack: {
        customer_architecture_traceability: {
          framework: "customer_architecture_traceability_v1",
          status: "assumption_required",
          target_account: "上海市文化和旅游局",
          facts: [],
          assumptions: [{ item_id: "a1", component: "数据", classification: "assumption", statement: "数据边界待确认", evidence_links: [], customer_material_allowed: false, validation_action: "确认接口" }],
          benchmarks: [],
          recommendations: [],
          current_estate_questions: ["确认现有系统和数据边界。"],
          option_tradeoff_questions: [],
          blockers: ["现有系统仍为假设。"],
        },
      },
    } as unknown as ApiResearchReport;

    render(<ResearchReportDeliveryTruthSection report={report} />);

    expect(screen.getByText("候选材料")).toBeInTheDocument();
    expect(screen.getAllByText("上海市文化和旅游局").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("暂缓条件：采购范围与能力不匹配时暂停投入。")).toBeInTheDocument();
    expect(screen.getByText("需确认客户现状")).toBeInTheDocument();
  });
});
