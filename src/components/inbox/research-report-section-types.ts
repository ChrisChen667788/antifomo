import type { ApiResearchReport } from "@/lib/api/types";

export type ReportToneMeta = {
  label: string;
  className: string;
  note?: string;
};

export type ReportScoreBucket = {
  label: string;
  className: string;
};

export type ResearchReportSource = ApiResearchReport["sources"][number];
export type ResearchReportCoreEntity = NonNullable<ApiResearchReport["entity_graph"]>["entities"][number];

export type ResearchPipelineStageSummary = {
  key: string;
  label: string;
  value: number;
  summary: string;
};

export type RetrievalRoutingCard = {
  title: string;
  value: string;
  detail: string;
  tone: string;
};
