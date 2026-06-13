from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


DATASET_PATH = Path(__file__).resolve().parents[3] / "evaluation" / "research_golden_v1.json"

ExpectedBehavior = Literal["answer", "guard", "refuse"]


class ResearchEvaluationCaseSpec(BaseModel):
    case_id: str = Field(min_length=3, max_length=80)
    keyword: str = Field(min_length=2, max_length=160)
    research_focus: str = Field(min_length=2, max_length=320)
    regions: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    required_terms: list[str] = Field(default_factory=list)
    reference_answer_terms: list[str] = Field(default_factory=list)
    expected_source_domains: list[str] = Field(default_factory=list)
    expected_source_urls: list[str] = Field(default_factory=list)
    expected_behavior: ExpectedBehavior | None = None
    language: Literal["zh-CN", "zh-TW", "en"] = "zh-CN"


class ResearchEvaluationSuiteSpec(BaseModel):
    suite_id: str
    category: str
    expected_methodology: str
    default_expected_behavior: ExpectedBehavior = "answer"
    preferred_source_tiers: list[Literal["official", "media", "aggregate"]] = Field(default_factory=list)
    required_sections: list[str] = Field(default_factory=list)
    metric_targets: dict[str, float] = Field(default_factory=dict)
    cases: list[ResearchEvaluationCaseSpec]


class ResearchEvaluationDatasetManifest(BaseModel):
    dataset_id: str
    version: str
    status: Literal["draft", "curated", "locked"] = "draft"
    description: str = ""
    expected_case_count: int = Field(ge=1)
    required_metrics: list[str]
    suites: list[ResearchEvaluationSuiteSpec]


class ResearchEvaluationCase(BaseModel):
    case_id: str
    dataset_id: str
    dataset_version: str
    curation_status: Literal["draft", "curated", "locked"]
    suite_id: str
    category: str
    keyword: str
    research_focus: str
    language: Literal["zh-CN", "zh-TW", "en"]
    expected_methodology: str
    expected_behavior: ExpectedBehavior
    regions: list[str]
    entities: list[str]
    required_terms: list[str]
    reference_answer_terms: list[str]
    expected_source_domains: list[str]
    expected_source_urls: list[str]
    preferred_source_tiers: list[str]
    required_sections: list[str]
    metric_targets: dict[str, float]


def load_research_evaluation_dataset(path: Path = DATASET_PATH) -> tuple[ResearchEvaluationDatasetManifest, list[ResearchEvaluationCase]]:
    manifest = ResearchEvaluationDatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))
    cases: list[ResearchEvaluationCase] = []
    seen_ids: set[str] = set()
    for suite in manifest.suites:
        for case in suite.cases:
            if case.case_id in seen_ids:
                raise ValueError(f"duplicate research evaluation case_id: {case.case_id}")
            seen_ids.add(case.case_id)
            cases.append(
                ResearchEvaluationCase(
                    case_id=case.case_id,
                    dataset_id=manifest.dataset_id,
                    dataset_version=manifest.version,
                    curation_status=manifest.status,
                    suite_id=suite.suite_id,
                    category=suite.category,
                    keyword=case.keyword,
                    research_focus=case.research_focus,
                    language=case.language,
                    expected_methodology=suite.expected_methodology,
                    expected_behavior=case.expected_behavior or suite.default_expected_behavior,
                    regions=list(case.regions),
                    entities=list(case.entities),
                    required_terms=list(case.required_terms),
                    reference_answer_terms=list(case.reference_answer_terms),
                    expected_source_domains=list(case.expected_source_domains),
                    expected_source_urls=list(case.expected_source_urls),
                    preferred_source_tiers=list(suite.preferred_source_tiers),
                    required_sections=list(suite.required_sections),
                    metric_targets=dict(suite.metric_targets),
                )
            )
    if len(cases) != manifest.expected_case_count:
        raise ValueError(
            f"research evaluation dataset expected {manifest.expected_case_count} cases, found {len(cases)}"
        )
    return manifest, cases
