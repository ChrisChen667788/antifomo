from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.research import ResearchIndustryKnowledgeHitOut
from app.services import industry_skill_library
from app.services.industry_skill_library import (
    build_industry_skill_context,
    build_industry_skill_library,
    build_industry_skill_library_snapshot,
    classify_document_industries,
    classify_document_type,
)
from app.services.industry_knowledge_rag import LocalContentUnit, LocalDocumentAnalysis


def _build_fixture_library(tmp_path, monkeypatch):
    source_root = tmp_path / "行业资讯"
    source_root.mkdir()
    for file_name in (
        "2026中国旅游AI营销白皮书.pdf",
        "政务大模型建设解决方案.pptx",
        "2025金融行业研究报告.pdf",
    ):
        (source_root / file_name).write_bytes(b"fixture")
    (source_root / "._2026中国旅游AI营销白皮书.pdf").write_bytes(b"apple-double")

    def fake_analyze(path, *, ocr_binary=None):
        if "旅游" in path.name:
            text = "景区游客全旅程、AIGC内容生产和营销转化需要结合内容版权与高峰期服务保障，并通过客流、停留和二次消费指标持续复盘。"
        elif "政务" in path.name:
            text = "政务服务需要明确数据分级分类、跨部门授权、等保和绩效评价。"
        else:
            text = "金融机构需关注模型风险、审计留痕、可解释性和人工审批。"
        return LocalDocumentAnalysis(
            extraction_status="full_text_analyzed",
            source_format="pdf",
            total_unit_count=2,
            extracted_unit_count=2,
            content_char_count=len(text),
            units=[LocalContentUnit(ordinal=1, locator="第 1 页", text=text)],
            full_text=text,
        )

    monkeypatch.setattr(industry_skill_library, "analyze_document_content", fake_analyze)
    output_dir = tmp_path / "industry-skills"
    catalog = build_industry_skill_library(source_root=source_root, library_dir=output_dir, workers=1, build_rag=False)
    monkeypatch.setenv("INDUSTRY_SKILL_CATALOG_PATH", str(output_dir / "catalog.json"))
    return catalog, output_dir


def test_classifies_industry_and_document_type_from_file_name_and_reference_text() -> None:
    industries = classify_document_industries("2026中国旅游AI营销白皮书.pdf", "景区游客内容生成与营销转化")
    assert industries[0]["id"] in {"tourism_hospitality", "artificial_intelligence", "media_marketing_entertainment"}
    assert {item["id"] for item in industries} >= {"tourism_hospitality", "artificial_intelligence"}

    document_type = classify_document_type("政务大模型建设解决方案.pptx", "跨部门数据治理实施")
    assert document_type["id"] == "solution"
    assert document_type["label"] == "解决方案"

    cloud_industries = classify_document_industries(
        "ACP实验手册最新.rar",
        "在阿里云创建 VPC、ECS 与 SLB，并配置 HTTPS 负载均衡和 OSS 图片处理。",
    )
    assert cloud_industries[0]["id"] == "artificial_intelligence"


def test_classifies_health_insurance_as_financial_without_spurious_government_match() -> None:
    industries = classify_document_industries(
        "2025中国企业健康保障发展白皮书.pdf",
        "商业保险公司通过团体健康保险、参保和投保服务，为企业员工提供保险产品与保单管理。",
    )

    industry_ids = {item["id"] for item in industries}
    assert "financial_services" in industry_ids
    assert "government_public" not in industry_ids


def test_filters_cross_industry_rag_hits_when_query_has_a_specific_vertical_scope() -> None:
    scope = industry_skill_library._query_scope_industries("医疗人工智能临床辅助决策")
    medical_hit = ResearchIndustryKnowledgeHitOut(
        passage_id="medical",
        document_id="doc_medical",
        title="医疗 AI 应用报告.pdf",
        document_type="industry_report",
        document_type_label="行业报告",
        industry="artificial_intelligence",
        locator="第 2 页",
        snippet="医疗 AI 可辅助临床决策，仍需医生复核。",
        match_modes=["vector"],
    )
    finance_hit = ResearchIndustryKnowledgeHitOut(
        passage_id="finance",
        document_id="doc_finance",
        title="AI 金融应用报告.pdf",
        document_type="industry_report",
        document_type_label="行业报告",
        industry="artificial_intelligence",
        locator="第 8 页",
        snippet="AI 保险模型与信贷风控正在扩展。",
        match_modes=["vector"],
    )

    assert industry_skill_library._is_scope_compatible_retrieval_hit(medical_hit, scope_industries=scope)
    assert not industry_skill_library._is_scope_compatible_retrieval_hit(finance_hit, scope_industries=scope)


def test_reference_preview_redacts_contact_details_and_skips_cover_noise() -> None:
    document = {
        "document_id": "doc_example",
        "file_name": "文旅行业报告.pdf",
        "document_type": "industry_report",
        "document_type_label": "行业报告",
        "published_year": 2026,
        "excerpt": "联络人：张三 0755-82969261，邮箱 analyst@example.com。感谢您下载本报告。",
    }

    reference = industry_skill_library._reference_out(document, 8)
    assert "82969261" not in reference.excerpt
    assert "analyst@example.com" not in reference.excerpt
    assert "感谢您下载" not in reference.excerpt
    assert industry_skill_library._reference_highlight(document) == ""


def test_builds_auditable_local_catalog_and_industry_skills(tmp_path, monkeypatch) -> None:
    catalog, output_dir = _build_fixture_library(tmp_path, monkeypatch)

    assert catalog["summary"]["source_file_count"] == 3
    assert catalog["summary"]["apple_double_file_count"] == 1
    assert catalog["summary"]["extracted_count"] == 3
    assert any(skill["industry"] == "tourism_hospitality" for skill in catalog["skills"])
    assert (output_dir / "catalog.json").is_file()
    assert (output_dir / "classification-report.md").is_file()
    assert (output_dir / "skills" / "tourism_hospitality.md").is_file()

    snapshot = build_industry_skill_library_snapshot(query="文旅 AIGC 景区")
    assert snapshot.status == "available"
    assert snapshot.document_count == 3
    assert any(skill.industry == "tourism_hospitality" for skill in snapshot.suggested_skills)
    assert all(skill.industry != "cross_industry" for skill in snapshot.suggested_skills)
    assert all("/" not in reference.title for skill in snapshot.suggested_skills for reference in skill.references)


def test_builds_context_with_explicit_selection_without_promoting_local_references_to_evidence(tmp_path, monkeypatch) -> None:
    catalog, _ = _build_fixture_library(tmp_path, monkeypatch)
    tourism_skill_id = next(skill["skill_id"] for skill in catalog["skills"] if skill["industry"] == "tourism_hospitality")

    context = build_industry_skill_context(
        scenario="景区 AIGC 导览",
        vertical_scene="文旅营销与数字人导览",
        selected_skill_ids=[tourism_skill_id],
    )

    assert context.status == "available"
    assert [skill.skill_id for skill in context.selected_skills] == [tourism_skill_id]
    assert context.source_document_count >= 1
    assert context.selected_skills[0].references
    assert context.selected_skills[0].reference_highlights
    assert "项目事实" in context.selected_skills[0].references[0].verification_note
    assert context.retrieval_strategy == "baseline_hybrid"


def test_industry_skill_endpoint_returns_catalog_without_source_paths(tmp_path, monkeypatch) -> None:
    _build_fixture_library(tmp_path, monkeypatch)

    with TestClient(app) as client:
        response = client.get("/api/research/industry-skills", params={"query": "政务大模型", "limit": 3})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available"
    assert payload["suggested_skills"]
    assert "source_root" not in payload
    assert str(tmp_path) not in response.text
