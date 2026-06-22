from __future__ import annotations

from io import BytesIO
from base64 import b64decode
from datetime import datetime, timezone
from zipfile import ZipFile

from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.work_tasks.chinese_proofreading import proofread_chinese_delivery_text
from app.services.work_tasks.office_roundtrip import detect_office_roundtrip_capabilities
from app.services.work_tasks.formal_documents import (
    build_feasibility_study_docx_document,
    build_feasibility_study_word_document,
    build_project_proposal_docx_document,
    build_project_proposal_pdf_document,
    build_project_proposal_pdf_document_with_diagnostics,
    build_research_solution_delivery_pptx_document,
)


def _report() -> ResearchReportResponse:
    return ResearchReportResponse(
        keyword="政务AI解决方案",
        research_focus="面向政务热线和政务服务大厅的 AI 助手、知识库和工单协同平台。",
        output_language="zh-CN",
        research_mode="deep",
        report_title="政务AI解决方案机会研判",
        executive_summary="政务服务和热线场景近三年持续出现数字化、智能问答和工单协同建设需求。",
        consulting_angle="先锁定目标数据局/政务服务中心，再用近三年招采和产品参数反推方案边界。",
        target_accounts=["某市数据局"],
        target_departments=["政务服务中心", "热线管理处"],
        budget_signals=["一期预算 520 万元"],
        tender_timeline=["2026 Q3 招采窗口"],
        strategic_directions=["先做政务AI助手试点，再扩到热线和大厅联动。"],
        benchmark_cases=["政务热线智能问答项目"],
        flagship_products=["政务AI助手平台", "知识库问答平台"],
        source_count=1,
        evidence_density="medium",
        source_quality="medium",
        sources=[
            ResearchSourceOut(
                title="某市政务服务AI助手公开招标公告",
                url="https://ggzy.example.gov.cn/tender/gov-ai",
                domain="ggzy.example.gov.cn",
                snippet=(
                    "2025年公开招标，采购人：某市数据局，预算金额 520万元，包含知识库、智能问答、"
                    "工单协同、API 接口、私有化部署、等保三级。"
                ),
                search_query="政务AI 助手 招标 技术参数",
                source_type="procurement",
                content_status="fetched",
                source_tier="official",
            )
        ],
        generated_at=datetime.now(timezone.utc),
    )


def _supplement() -> dict[str, str]:
    return {
        "project_name": "政务AI助手建设项目",
        "project_owner": "某市数据局",
        "target_customer": "某市数据局",
        "solution_scenario": "政务AI解决方案",
        "vertical_scene": "政务热线 AI 助手",
        "project_region": "华东区域",
        "implementation_window": "2026 Q3-Q4",
        "investment_estimate": "一期预算 520 万元",
        "supplemental_context": "客户希望先做试点。",
        "supplemental_evidence": "公开招标要求支持工单协同。",
        "supplemental_requirements": "重点补预算口径和实施窗口。",
    }


def _branded_supplement() -> dict[str, object]:
    return {
        **_supplement(),
        "brand_template": {
            "template_id": "customer-gov-ai",
            "display_name": "某市数据局正式汇报模板",
            "primary_color": "#1D4ED8",
            "secondary_color": "#047857",
            "accent_color": "#EA580C",
            "logo_text": "某市数据局",
            "confidentiality_label": "客户内部评审稿",
            "footer_text": "某市数据局 · 政务AI助手项目",
        },
        "chart_assets": [
            {
                "asset_id": "budget-stage-chart",
                "title": "预算分阶段投入图",
                "description": "展示一期预算、试点阶段和推广阶段投入节奏。",
                "source": "公开招标公告 + 客户访谈补充",
                "unit": "万元",
                "period": "2026 Q3-Q4",
                "replacement_slot": "chart-budget-stage",
                "data": [
                    {"label": "一期预算", "value": "520"},
                    {"label": "试点阶段", "value": "120"},
                    {"label": "推广阶段", "value": "400"},
                ],
            }
        ],
        "image_assets": [
            {
                "asset_id": "service-hall-flow",
                "title": "政务大厅业务流程示意图",
                "description": "替换为客户授权的大厅服务流程、热线协同或系统架构图。",
                "source": "客户授权素材",
                "unit": "16:9 SVG/PNG",
                "replacement_slot": "image-service-hall-flow",
            }
        ],
        "renderer_strategy": "受控渲染策略：CI 使用 OpenXML 结构校验；客户外发前使用 LibreOffice headless 或人工 Word/PowerPoint 打开门禁。",
    }


def test_feasibility_word_export_uses_controlled_layout_numbering_tables_and_header_footer() -> None:
    filename, content, mime_type = build_feasibility_study_word_document(
        _report().model_dump(mode="json"),
        output_language="zh-CN",
        delivery_supplement=_supplement(),
    )

    assert filename.endswith(".doc")
    assert mime_type == "application/msword"
    assert "@page WordSection1" in content
    assert "mso-element:header" in content
    assert "mso-element:footer" in content
    assert "Anti-FOMO 正式交付" in content
    assert "项目元信息" in content
    assert "目录" in content
    assert "交付版式控制清单" in content
    assert "PDF/Word 往返校验清单" in content
    assert "<table" in content
    assert "一、项目概况、研究依据与范围边界" in content
    assert "一、一" not in content
    assert "附录A：人工输入与交叉验证说明" in content
    assert "附录" in content and "量化决策模型摘要" in content


def test_feasibility_docx_export_is_native_openxml_with_roundtrip_and_proofreading_diagnostics() -> None:
    filename, preview_content, content_base64, mime_type, diagnostics = build_feasibility_study_docx_document(
        _report().model_dump(mode="json"),
        output_language="zh-CN",
        delivery_supplement={
            **_supplement(),
            "supplemental_context": "本项目一定可以实现100%提升。",
        },
    )

    assert filename.endswith(".docx")
    assert mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "af-visual-fingerprint" in preview_content
    assert "中文校对清单" in preview_content
    assert diagnostics["renderer"] == "anti-fomo-formal-renderer-v3"
    assert diagnostics["native_docx"] is True
    assert diagnostics["visual_regression"]["fingerprint"]
    assert diagnostics["office_roundtrip"]["status"] == "pass"
    assert any("绝对化" in row for row in diagnostics["proofreading_findings"])

    docx_bytes = b64decode(content_base64)
    assert docx_bytes.startswith(b"PK")
    with ZipFile(BytesIO(docx_bytes)) as archive:
        names = set(archive.namelist())
        assert "word/document.xml" in names
        assert "word/header1.xml" in names
        assert "word/footer1.xml" in names
        assert "word/styles.xml" in names
        assert "word/settings.xml" in names
        assert "word/numbering.xml" in names
        assert "word/theme/theme1.xml" in names
        assert "word/media/image1.png" in names
        document_xml = archive.read("word/document.xml").decode("utf-8")
        document_rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")

    assert "<w:tbl>" in document_xml
    assert 'TOC \\o "1-2"' in document_xml
    assert "<v:roundrect" in document_xml
    assert "rIdImage1" in document_xml
    assert "原生图片嵌入" in document_xml
    assert "media/image1.png" in document_rels
    assert "Anti-FOMO P2.3 专业交付模板" in document_xml
    assert "图表与图片排版占位" in document_xml
    assert "政务AI助手建设项目可行性研究报告" in document_xml
    assert "中文校对清单" in document_xml
    assert "PDF/Word 往返校验清单" in document_xml
    assert "P2.5 复杂样式模板与真实打开验证门禁" in document_xml
    assert "一、项目概况、研究依据与范围边界" in document_xml
    assert "一、一" not in document_xml
    assert "word/numbering.xml" in diagnostics["office_roundtrip"]["complex_template_parts"]
    assert "word/theme/theme1.xml" in diagnostics["office_roundtrip"]["complex_template_parts"]
    assert diagnostics["native_images"] is True
    assert "word/media/image1.png" in diagnostics["native_image_parts"]


def test_feasibility_docx_export_includes_brand_template_and_replaceable_assets() -> None:
    filename, preview_content, content_base64, mime_type, diagnostics = build_feasibility_study_docx_document(
        _report().model_dump(mode="json"),
        output_language="zh-CN",
        delivery_supplement=_branded_supplement(),
    )

    assert filename.endswith(".docx")
    assert mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "客户品牌模板：某市数据局正式汇报模板" in preview_content
    assert "P2.4 可替换资产清单" in preview_content
    assert "真实数据图表 1：预算分阶段投入图" in preview_content
    assert "可替换图片资源 1：政务大厅业务流程示意图" in preview_content
    assert diagnostics["professional_template"] == "anti-fomo-p2.4-brand-media-template"
    assert diagnostics["brand_template"]["template_id"] == "customer-gov-ai"
    assert diagnostics["brand_template"]["primary_color"] == "1D4ED8"
    assert diagnostics["replaceable_assets"]["chart_asset_count"] == 1
    assert diagnostics["replaceable_assets"]["image_asset_count"] == 1
    assert "LibreOffice headless" in diagnostics["headless_conversion_strategy"]
    assert "P2.4 可替换资产清单" in diagnostics["visual_regression"]["required_markers"]
    assert "P2.5 复杂样式模板与真实打开验证门禁" in diagnostics["visual_regression"]["required_markers"]
    assert diagnostics["office_roundtrip"]["status"] == "pass"
    assert "word/numbering.xml" in diagnostics["complex_template_parts"]
    assert "word/theme/theme1.xml" in diagnostics["complex_template_parts"]

    with ZipFile(BytesIO(b64decode(content_base64))) as archive:
        names = set(archive.namelist())
        assert "word/numbering.xml" in names
        assert "word/theme/theme1.xml" in names
        assert "word/media/image1.png" in names
        document_xml = archive.read("word/document.xml").decode("utf-8")
        document_rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")
        header_xml = archive.read("word/header1.xml").decode("utf-8")
        footer_xml = archive.read("word/footer1.xml").decode("utf-8")

    assert "某市数据局正式汇报模板" in document_xml
    assert "P2.4 客户品牌与可替换资产模板" in document_xml
    assert "预算分阶段投入图" in document_xml
    assert "政务大厅业务流程示意图" in document_xml
    assert "原生图片嵌入" in document_xml
    assert "rIdImage1" in document_rels
    assert "chart-budget-stage" in document_xml
    assert "image-service-hall-flow" in document_xml
    assert "某市数据局" in header_xml
    assert "客户内部评审稿" in footer_xml
    assert diagnostics["native_images"] is True
    assert "word/media/image1.png" in diagnostics["native_image_parts"]


def test_project_proposal_docx_export_preserves_native_layout_contract() -> None:
    filename, preview_content, content_base64, mime_type, diagnostics = build_project_proposal_docx_document(
        _report().model_dump(mode="json"),
        output_language="zh-CN",
        delivery_supplement=_supplement(),
    )

    assert filename.endswith(".docx")
    assert mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "项目建议书" in preview_content
    assert "图表与图片排版占位" in diagnostics["visual_regression"]["required_markers"]
    assert diagnostics["office_roundtrip"]["status"] == "pass"
    assert diagnostics["native_images"] is True
    with ZipFile(BytesIO(b64decode(content_base64))) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "政务AI助手建设项目项目建议书" in document_xml
    assert "原生 DOCX 与专业 PDF 预览均使用同一章节模型" in document_xml
    assert "原生图片嵌入" in document_xml


def test_solution_delivery_pptx_export_contains_editable_text_shapes() -> None:
    filename, preview_content, content_base64, mime_type, diagnostics = build_research_solution_delivery_pptx_document(
        _report().model_dump(mode="json"),
        output_language="zh-CN",
        delivery_supplement=_supplement(),
    )

    assert filename.endswith(".pptx")
    assert mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert "PPTX 可编辑导出预览" in preview_content
    assert diagnostics["renderer"] == "anti-fomo-pptx-renderer-v1"
    assert diagnostics["editable_text_boxes"] is True
    assert diagnostics["visual_regression"]["fingerprint"]

    pptx_bytes = b64decode(content_base64)
    assert pptx_bytes.startswith(b"PK")
    with ZipFile(BytesIO(pptx_bytes)) as archive:
        names = set(archive.namelist())
        assert "ppt/presentation.xml" in names
        assert "ppt/theme/theme1.xml" in names
        assert "ppt/charts/chart1.xml" in names
        assert "ppt/charts/_rels/chart1.xml.rels" in names
        assert "ppt/embeddings/chart-data.xlsx" in names
        assert "ppt/media/image1.png" in names
        assert "ppt/slides/slide1.xml" in names
        assert "ppt/slides/slide2.xml" in names
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        slide_rels = archive.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")

    assert "<p:txBody>" in slide_xml
    assert "<a:t>" in slide_xml
    assert "Anti-FOMO P2.3 editable PPTX" in slide_xml
    assert "图表占位" in slide_xml
    assert "图片占位" in slide_xml
    assert "原生图片嵌入" in slide_xml
    assert "rIdImage1" in slide_rels
    assert diagnostics["native_editable_charts"] is True
    assert diagnostics["native_images"] is True
    assert "ppt/charts/chart1.xml" in diagnostics["native_chart_parts"]
    assert "ppt/embeddings/chart-data.xlsx" in diagnostics["embedded_workbooks"]
    assert "ppt/media/image1.png" in diagnostics["native_image_parts"]
    assert diagnostics["office_roundtrip"]["status"] == "pass"


def test_solution_delivery_pptx_export_applies_brand_and_media_assets() -> None:
    filename, preview_content, content_base64, mime_type, diagnostics = build_research_solution_delivery_pptx_document(
        _report().model_dump(mode="json"),
        output_language="zh-CN",
        delivery_supplement=_branded_supplement(),
    )

    assert filename.endswith(".pptx")
    assert mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert "客户品牌模板：某市数据局正式汇报模板" in preview_content
    assert "P2.4 可替换资产清单" in preview_content
    assert diagnostics["professional_template"] == "anti-fomo-p2.4-brand-media-pptx-template"
    assert diagnostics["brand_template"]["logo_text"] == "某市数据局"
    assert diagnostics["replaceable_assets"]["chart_asset_count"] == 1
    assert diagnostics["replaceable_assets"]["image_asset_count"] == 1
    assert "真实数据图表" in diagnostics["visual_regression"]["required_markers"]
    assert "P2.5 Native Editable Chart" in diagnostics["visual_regression"]["required_markers"]
    assert diagnostics["native_editable_charts"] is True
    assert diagnostics["office_roundtrip"]["status"] == "pass"

    with ZipFile(BytesIO(b64decode(content_base64))) as archive:
        names = set(archive.namelist())
        assert "ppt/charts/chart1.xml" in names
        assert "ppt/charts/_rels/chart1.xml.rels" in names
        assert "ppt/embeddings/chart-data.xlsx" in names
        assert "ppt/media/image1.png" in names
        theme_xml = archive.read("ppt/theme/theme1.xml").decode("utf-8")
        slide_xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        slide_rels = archive.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
        chart_xml = archive.read("ppt/charts/chart1.xml").decode("utf-8")
        embedded_xlsx = archive.read("ppt/embeddings/chart-data.xlsx")

    assert "某市数据局正式汇报模板" in theme_xml
    assert "1D4ED8" in theme_xml
    assert "客户品牌模板：某市数据局正式汇报模板" in slide_xml
    assert "预算分阶段投入图" in slide_xml
    assert "政务大厅业务流程示意图" in slide_xml
    assert "P2.4 customer brand/media" in slide_xml
    assert "P2.5 Native Editable Chart" in slide_xml
    assert "原生图片嵌入" in slide_xml
    assert "rIdChart1" in slide_rels
    assert "rIdImage1" in slide_rels
    assert "预算分阶段投入图" in chart_xml
    assert embedded_xlsx.startswith(b"PK")
    assert diagnostics["native_images"] is True
    assert "ppt/media/image1.png" in diagnostics["native_image_parts"]


def test_chinese_proofreading_flags_delivery_quality_risks() -> None:
    rows = proofread_chinese_delivery_text(
        [
            "本项目一定可以实现100%提升。",
            "建议采购方 在2026年完成预算评审。",
            "数据口径待核验。",
        ]
    )

    assert any("绝对化" in row for row in rows)
    assert any("中文词间多余空格" in row for row in rows)
    assert any("待核验" in row for row in rows)


def test_project_proposal_pdf_preview_preserves_roundtrip_checklist_and_pdf_header_footer() -> None:
    filename, preview_content, content_base64, mime_type = build_project_proposal_pdf_document(
        _report().model_dump(mode="json"),
        output_language="zh-CN",
        delivery_supplement=_supplement(),
    )

    assert filename.endswith(".pdf")
    assert mime_type == "application/pdf"
    assert preview_content.startswith("[页眉] Anti-FOMO 正式交付")
    assert "项目元信息" in preview_content
    assert "目录" in preview_content
    assert "图表与图片排版占位" in preview_content
    assert "交付版式控制清单" in preview_content
    assert "PDF/Word 往返校验清单" in preview_content
    assert "页眉页脚" in preview_content
    assert "一、项目背景、编制依据与立项必要性" in preview_content
    assert "一、一" not in preview_content
    assert "[页脚] P2 controlled export" in preview_content
    assert b64decode(content_base64).startswith(b"%PDF-1.4")


def test_project_proposal_pdf_diagnostics_include_office_roundtrip_and_professional_layout() -> None:
    filename, preview_content, content_base64, mime_type, diagnostics = build_project_proposal_pdf_document_with_diagnostics(
        _report().model_dump(mode="json"),
        output_language="zh-CN",
        delivery_supplement=_supplement(),
    )

    assert filename.endswith(".pdf")
    assert mime_type == "application/pdf"
    assert "图表与图片排版占位" in preview_content
    assert diagnostics["renderer"] == "anti-fomo-formal-pdf-renderer-v3"
    assert diagnostics["professional_pdf_layout"] == "in-repo-controlled-preview"
    assert diagnostics["professional_template"] == "anti-fomo-p2.4-brand-media-template"
    assert diagnostics["professional_pdf_layout_version"] == "p2.7-vector-brand-media-image-preview"
    assert diagnostics["pdf_layout_profile"] == "p2.6-brand-media-grid"
    assert diagnostics["native_pdf_image_embedding"] == "p2.7-pdf-image-xobject"
    assert "P2.5 复杂样式模板与真实打开验证门禁" in diagnostics["visual_regression"]["required_markers"]
    assert "P2.6 矢量品牌框架" in diagnostics["visual_regression"]["required_markers"]
    assert "P2.7 原生 PDF 图片对象" in diagnostics["visual_regression"]["required_markers"]
    assert diagnostics["replaceable_assets"]["chart_asset_count"] >= 1
    assert "受控渲染策略" in diagnostics["headless_conversion_strategy"]
    assert diagnostics["office_roundtrip"]["status"] == "pass"
    assert diagnostics["office_roundtrip"]["page_count"] >= 1
    assert diagnostics["office_roundtrip"]["has_vector_layout"] is True
    assert diagnostics["office_roundtrip"]["has_native_image"] is True
    assert "vector_brand_frame_present" in diagnostics["office_roundtrip"]["professional_layout_checks"]
    assert "native_pdf_image_present" in diagnostics["office_roundtrip"]["professional_layout_checks"]
    pdf_bytes = b64decode(content_base64)
    assert b" re f" in pdf_bytes
    assert b" re S" in pdf_bytes
    assert b"/Subtype /Image" in pdf_bytes
    assert b"/Im1 Do" in pdf_bytes
    assert pdf_bytes.rstrip().endswith(b"%%EOF")


def test_office_roundtrip_capability_detection_is_safe_and_non_gui() -> None:
    capabilities = detect_office_roundtrip_capabilities()

    assert "automated_mode" in capabilities
    assert capabilities["automated_mode"] in {
        "libreoffice_headless",
        "quicklook_thumbnail_optional",
        "structure_only",
    }
    assert "microsoft_word_app" in capabilities
    assert "microsoft_powerpoint_app" in capabilities
    assert "headless_conversion" in capabilities
    assert "real_open_validation_gate" in capabilities
    assert capabilities["real_open_validation_gate"]["policy"].startswith("never_launch_gui_in_tests")
