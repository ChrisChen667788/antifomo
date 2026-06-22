from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from hashlib import sha256
import html
import re

from app.schemas.research import (
    ResearchEntityEvidenceOut,
    ResearchMarketIntelligencePackOut,
    ResearchReportDocument,
    ResearchSolutionDeliveryPackOut,
)
from app.services.delivery.document_compilers import (
    compiled_document_sections_for_formal_export,
    select_compiled_document,
)
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.delivery.quantitative_models import quantitative_decision_model_sections_for_formal_export
from app.services.language import localized_text, normalize_output_language
from app.services.research_delivery_quality_service import review_and_improve_formal_document_sections
from app.services.research_solution_intelligence_service import build_solution_delivery_pack
from app.services.work_tasks.chinese_proofreading import proofread_chinese_delivery_text
from app.services.work_tasks.context import _context_list, _context_text
from app.services.work_tasks.office_roundtrip import (
    validate_docx_bytes,
    validate_pdf_bytes,
    validate_pptx_bytes,
)
from app.services.work_tasks.openxml import build_docx_bytes, build_pptx_bytes
from app.services.work_tasks.pdf import _build_simple_pdf


def _normalize_research_delivery_supplement(raw: dict | None) -> dict[str, object]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, object] = {
        "project_name": _context_text(raw.get("project_name")),
        "project_owner": _context_text(raw.get("project_owner")),
        "solution_scenario": _context_text(raw.get("solution_scenario")),
        "target_customer": _context_text(raw.get("target_customer")),
        "vertical_scene": _context_text(raw.get("vertical_scene")),
        "project_region": _context_text(raw.get("project_region")),
        "implementation_window": _context_text(raw.get("implementation_window")),
        "investment_estimate": _context_text(raw.get("investment_estimate")),
        "construction_basis": _context_text(raw.get("construction_basis")),
        "scope_statement": _context_text(raw.get("scope_statement")),
        "expected_benefits": _context_text(raw.get("expected_benefits")),
        "cross_validation_notes": _context_text(raw.get("cross_validation_notes")),
        "supplemental_context": _context_text(raw.get("supplemental_context")),
        "supplemental_evidence": _context_text(raw.get("supplemental_evidence")),
        "supplemental_requirements": _context_text(raw.get("supplemental_requirements")),
    }
    if isinstance(raw.get("brand_template"), dict):
        normalized["brand_template"] = raw.get("brand_template")
    raw_chart_assets = raw.get("chart_assets") if isinstance(raw.get("chart_assets"), list) else raw.get("charts")
    if isinstance(raw_chart_assets, list):
        normalized["chart_assets"] = raw_chart_assets
    raw_image_assets = raw.get("image_assets") if isinstance(raw.get("image_assets"), list) else raw.get("images")
    if isinstance(raw_image_assets, list):
        normalized["image_assets"] = raw_image_assets
    renderer_strategy = " ".join(str(raw.get("renderer_strategy") or "").split()).strip()
    if renderer_strategy:
        normalized["renderer_strategy"] = renderer_strategy[:360]
    return normalized


@dataclass(frozen=True)
class FormalBrandTemplate:
    template_id: str
    display_name: str
    primary_color: str
    secondary_color: str
    accent_color: str
    logo_text: str
    footer_text: str
    confidentiality_label: str
    font_family: str

    def as_dict(self) -> dict[str, str]:
        return {
            "template_id": self.template_id,
            "display_name": self.display_name,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "accent_color": self.accent_color,
            "logo_text": self.logo_text,
            "footer_text": self.footer_text,
            "confidentiality_label": self.confidentiality_label,
            "font_family": self.font_family,
        }


@dataclass(frozen=True)
class FormalMediaAsset:
    asset_id: str
    asset_type: str
    title: str
    description: str
    source: str
    unit: str
    period: str
    replacement_slot: str
    data_rows: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "unit": self.unit,
            "period": self.period,
            "replacement_slot": self.replacement_slot,
            "data_rows": list(self.data_rows),
        }


@dataclass(frozen=True)
class FormalDeliveryAssets:
    brand_template: FormalBrandTemplate
    chart_assets: list[FormalMediaAsset]
    image_assets: list[FormalMediaAsset]
    renderer_strategy: str


@dataclass(frozen=True)
class FormalDocumentRenderPayload:
    title: str
    subtitle: str
    document_kind: str
    meta_rows: list[str]
    sections: list[tuple[str, list[str]]]
    layout_rows: list[str]
    roundtrip_rows: list[str]
    proofreading_rows: list[str]
    visual_fingerprint: str
    brand_template: FormalBrandTemplate
    chart_assets: list[FormalMediaAsset]
    image_assets: list[FormalMediaAsset]
    renderer_strategy: str
    html_content: str
    plain_text: str


def _dedupe_export_rows(values: list[str], *, limit: int = 6, preserve_labels: bool = False) -> list[str]:
    rows: list[str] = []
    for value in values:
        normalized = _context_text(value, preserve_labels=preserve_labels)
        if normalized and normalized not in rows:
            rows.append(normalized)
    return rows[:limit]


_FORMAL_HEX_COLOR_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def _formal_text(value: object, *, preserve_labels: bool = False) -> str:
    return _context_text(value, preserve_labels=preserve_labels)


def _formal_supplement_text(supplement: dict[str, object], key: str, *, preserve_labels: bool = False) -> str:
    return _formal_text(supplement.get(key), preserve_labels=preserve_labels)


def _sanitize_formal_hex_color(value: object, fallback: str) -> str:
    text = _formal_text(value).strip()
    if _FORMAL_HEX_COLOR_RE.match(text):
        return text.lstrip("#").upper()
    return fallback.lstrip("#").upper()


def _formal_brand_template(
    *,
    supplement: dict[str, object],
    context: dict[str, str],
) -> FormalBrandTemplate:
    raw = supplement.get("brand_template")
    raw_brand = raw if isinstance(raw, dict) else {}
    display_name = (
        _formal_text(raw_brand.get("display_name") or raw_brand.get("name"), preserve_labels=True)
        or context.get("target_customer")
        or context.get("project_owner")
        or "Anti-FOMO Professional"
    )
    template_id = (
        _formal_text(raw_brand.get("template_id") or raw_brand.get("id"))
        or re.sub(r"[^a-z0-9_-]+", "-", display_name.lower()).strip("-")
        or "anti-fomo-professional"
    )
    logo_text = _formal_text(raw_brand.get("logo_text") or raw_brand.get("logo"), preserve_labels=True) or display_name[:24]
    return FormalBrandTemplate(
        template_id=template_id[:64],
        display_name=display_name[:80],
        primary_color=_sanitize_formal_hex_color(raw_brand.get("primary_color") or raw_brand.get("primary"), "2563EB"),
        secondary_color=_sanitize_formal_hex_color(raw_brand.get("secondary_color") or raw_brand.get("secondary"), "0F766E"),
        accent_color=_sanitize_formal_hex_color(raw_brand.get("accent_color") or raw_brand.get("accent"), "F97316"),
        logo_text=logo_text[:48],
        footer_text=_formal_text(raw_brand.get("footer_text"), preserve_labels=True)
        or "Anti-FOMO 正式交付 · evidence-first delivery",
        confidentiality_label=_formal_text(raw_brand.get("confidentiality_label"), preserve_labels=True) or "内部评审稿",
        font_family=_formal_text(raw_brand.get("font_family")) or "Microsoft YaHei / PingFang SC / Aptos",
    )


def _formal_asset_data_rows(value: object, *, limit: int = 5) -> list[str]:
    rows: list[str] = []
    if isinstance(value, dict):
        iterable = [f"{key}：{val}" for key, val in value.items()]
    elif isinstance(value, list):
        iterable = []
        for item in value:
            if isinstance(item, dict):
                label = _formal_text(
                    item.get("label")
                    or item.get("name")
                    or item.get("dimension")
                    or item.get("period")
                    or item.get("stage"),
                    preserve_labels=True,
                )
                value_text = _formal_text(
                    item.get("value")
                    or item.get("amount")
                    or item.get("score")
                    or item.get("metric"),
                    preserve_labels=True,
                )
                note = _formal_text(item.get("note") or item.get("description"), preserve_labels=True)
                if label and value_text:
                    iterable.append(f"{label}：{value_text}{f'（{note}）' if note else ''}")
                elif label:
                    iterable.append(label)
                elif value_text:
                    iterable.append(value_text)
            else:
                iterable.append(str(item))
    else:
        iterable = [str(value or "")]
    for item in iterable:
        text = _formal_text(item, preserve_labels=True)
        if text and text not in rows:
            rows.append(text)
        if len(rows) >= limit:
            break
    return rows


def _formal_media_asset_from_raw(
    raw: object,
    *,
    asset_type: str,
    index: int,
    context: dict[str, str],
    fallback_title: str,
    fallback_description: str,
    fallback_source: str,
    fallback_data_rows: list[str],
) -> FormalMediaAsset:
    raw_asset = raw if isinstance(raw, dict) else {}
    title = _formal_text(raw_asset.get("title") or raw_asset.get("name"), preserve_labels=True) or fallback_title
    description = (
        _formal_text(raw_asset.get("description") or raw_asset.get("summary") or raw_asset.get("caption"), preserve_labels=True)
        or fallback_description
    )
    data_rows = (
        _formal_asset_data_rows(raw_asset.get("data") or raw_asset.get("values") or raw_asset.get("rows"))
        if raw_asset
        else []
    )
    if not data_rows:
        data_rows = _dedupe_export_rows(fallback_data_rows, limit=5, preserve_labels=True)
    return FormalMediaAsset(
        asset_id=_formal_text(raw_asset.get("asset_id") or raw_asset.get("id")) or f"{asset_type}-{index}",
        asset_type=asset_type,
        title=title,
        description=description,
        source=_formal_text(raw_asset.get("source") or raw_asset.get("data_source"), preserve_labels=True) or fallback_source,
        unit=_formal_text(raw_asset.get("unit"), preserve_labels=True) or ("万元/评分" if asset_type == "chart" else "16:9 可替换素材"),
        period=_formal_text(raw_asset.get("period") or raw_asset.get("time_range"), preserve_labels=True)
        or context.get("implementation_window")
        or "待项目确认",
        replacement_slot=_formal_text(raw_asset.get("replacement_slot") or raw_asset.get("slot"))
        or f"{asset_type}-slot-{index}",
        data_rows=data_rows,
    )


def _formal_delivery_assets(
    *,
    report: ResearchReportDocument,
    supplement: dict[str, object],
    context: dict[str, str],
) -> FormalDeliveryAssets:
    brand_template = _formal_brand_template(supplement=supplement, context=context)
    raw_charts = supplement.get("chart_assets")
    chart_inputs = raw_charts if isinstance(raw_charts, list) else []
    budget_rows = _dedupe_export_rows(list(getattr(report, "budget_signals", []) or []), limit=3, preserve_labels=True)
    chart_assets = [
        _formal_media_asset_from_raw(
            raw,
            asset_type="chart",
            index=index,
            context=context,
            fallback_title="投资估算与实施阶段图",
            fallback_description="用于展示预算口径、实施窗口和关键阶段投入节奏。",
            fallback_source="delivery_supplement.chart_assets",
            fallback_data_rows=[
                f"投资估算：{context.get('investment_estimate', '')}",
                f"实施窗口：{context.get('implementation_window', '')}",
                *budget_rows,
            ],
        )
        for index, raw in enumerate(chart_inputs[:4], start=1)
    ]
    if not chart_assets:
        chart_assets = [
            _formal_media_asset_from_raw(
                {},
                asset_type="chart",
                index=1,
                context=context,
                fallback_title="投资估算与实施阶段图",
                fallback_description="从项目投资估算、实施窗口和预算信号派生，外发前可替换为正式预算分解。",
                fallback_source="report.budget_signals / delivery_supplement",
                fallback_data_rows=[
                    f"投资估算：{context.get('investment_estimate', '')}",
                    f"实施窗口：{context.get('implementation_window', '')}",
                    *budget_rows,
                ],
            ),
            _formal_media_asset_from_raw(
                {},
                asset_type="chart",
                index=2,
                context=context,
                fallback_title="证据覆盖与质量校验图",
                fallback_description="用于展示来源数量、证据密度、来源质量和交付前待核验缺口。",
                fallback_source="research_report.source_diagnostics",
                fallback_data_rows=[
                    f"来源数量：{getattr(report, 'source_count', 0)}",
                    f"证据密度：{getattr(report, 'evidence_density', '')}",
                    f"来源质量：{getattr(report, 'source_quality', '')}",
                    f"目标客户：{context.get('target_customer', '')}",
                ],
            ),
        ]
    raw_images = supplement.get("image_assets")
    image_inputs = raw_images if isinstance(raw_images, list) else []
    image_assets = [
        _formal_media_asset_from_raw(
            raw,
            asset_type="image",
            index=index,
            context=context,
            fallback_title="客户场景或能力架构示意图",
            fallback_description="外发前替换为客户授权素材、系统架构图或实施路线图。",
            fallback_source="delivery_supplement.image_assets",
            fallback_data_rows=[
                f"目标客户：{context.get('target_customer', '')}",
                f"方案场景：{context.get('solution_scenario', '')}",
            ],
        )
        for index, raw in enumerate(image_inputs[:4], start=1)
    ]
    if not image_assets:
        image_assets = [
            _formal_media_asset_from_raw(
                {},
                asset_type="image",
                index=1,
                context=context,
                fallback_title="客户场景与业务流程示意图",
                fallback_description="用于放置客户现状流程、触点分布或业务协同场景，必须替换为可授权素材。",
                fallback_source="manual replacement required",
                fallback_data_rows=[
                    f"目标客户：{context.get('target_customer', '')}",
                    f"垂直场景：{context.get('vertical_scene', '')}",
                ],
            ),
            _formal_media_asset_from_raw(
                {},
                asset_type="image",
                index=2,
                context=context,
                fallback_title="系统架构与实施路线图",
                fallback_description="用于放置能力架构、集成边界或阶段路线图，建议使用可编辑 SVG/PNG。",
                fallback_source="manual replacement required",
                fallback_data_rows=[
                    f"方案场景：{context.get('solution_scenario', '')}",
                    f"实施窗口：{context.get('implementation_window', '')}",
                ],
            ),
        ]
    renderer_strategy = " ".join(str(supplement.get("renderer_strategy") or "").split()).strip() or (
        "受控渲染策略：默认使用 in-repo controlled preview + OpenXML 结构校验；"
        "检测到 LibreOffice CLI 时可升级 headless 往返转换，未配置时不自动调用 GUI Office。"
    )
    return FormalDeliveryAssets(
        brand_template=brand_template,
        chart_assets=chart_assets,
        image_assets=image_assets,
        renderer_strategy=renderer_strategy,
    )


def _report_followup_rows(report: ResearchReportDocument) -> list[str]:
    context = getattr(report, "followup_context", None)
    if context is None:
        return []
    diagnostics = getattr(report, "followup_diagnostics", None)
    rows = [
        f"上一版研报标题：{_context_text(getattr(context, 'followup_report_title', ''))}",
        f"上一版执行摘要：{_context_text(getattr(context, 'followup_report_summary', ''))}",
        f"人工补充新信息：{_context_text(getattr(context, 'supplemental_context', ''))}",
        f"人工补充新证据/待核验线索：{_context_text(getattr(context, 'supplemental_evidence', ''))}",
        f"人工补充新需求：{_context_text(getattr(context, 'supplemental_requirements', ''))}",
    ]
    if diagnostics is not None and getattr(diagnostics, "enabled", False):
        title_resolution = _context_text(getattr(diagnostics, "title_resolution", ""))
        summary_resolution = _context_text(getattr(diagnostics, "summary_resolution", ""))
        resolution_labels = {
            "baseline": "基线生成",
            "reused": "沿用基线",
            "corrected": "已按追问纠偏",
        }
        if title_resolution:
            rows.append(f"标题处理：{resolution_labels.get(title_resolution, title_resolution)}")
        if summary_resolution:
            rows.append(f"摘要处理：{resolution_labels.get(summary_resolution, summary_resolution)}")
        for impact in list(getattr(diagnostics, "impacted_sections", []) or [])[:4]:
            section_title = _context_text(getattr(impact, "section_title", ""))
            impact_label = _context_text(getattr(impact, "impact_label", ""))
            impact_score = int(getattr(impact, "impact_score", 0) or 0)
            next_action = _context_text(getattr(impact, "next_action", ""))
            if section_title:
                rows.append(
                    f"重点影响章节：{section_title}（{impact_label or 'impact'} / {impact_score}）"
                    + (f"；下一步：{next_action}" if next_action else "")
                )
    return [row for row in rows if not row.endswith("：")]


def _formal_document_evidence_links(report: ResearchReportDocument) -> list[ResearchEntityEvidenceOut]:
    rows: list[ResearchEntityEvidenceOut] = []
    seen_urls: set[str] = set()
    for section in report.sections:
        for link in section.evidence_links:
            if not link.url or link.url in seen_urls:
                continue
            seen_urls.add(link.url)
            rows.append(link)
    for source in report.sources:
        if not source.url or source.url in seen_urls:
            continue
        seen_urls.add(source.url)
        rows.append(
            ResearchEntityEvidenceOut(
                title=source.title,
                url=source.url,
                source_label=source.source_label,
                source_tier=source.source_tier,
                anchor_text=source.search_query,
                excerpt=source.snippet,
                confidence_tone="high" if source.source_tier == "official" else "low",
            )
        )
    return rows[:40]


FORMAL_REPORT_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "solution_design": ("解决方案设计建议", "解決方案設計建議", "solution design"),
    "sales_strategy": ("销售策略", "銷售策略", "sales strategy"),
    "bidding_strategy": ("投标规划", "投標規劃", "bidding strategy"),
    "outreach_strategy": ("陌生拜访建议", "陌生拜訪建議", "outreach strategy"),
    "risks": ("风险提示", "風險提示", "risks"),
    "next_actions": ("下一步行动", "下一步行動", "next actions"),
}

_FORMAL_SECTION_NUMERALS = (
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "九",
    "十",
    "十一",
    "十二",
    "十三",
    "十四",
    "十五",
    "十六",
    "十七",
    "十八",
    "十九",
    "二十",
)

_FORMAL_APPENDIX_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_FORMAL_SECTION_PREFIX_RE = re.compile(r"^(?:第?[一二三四五六七八九十]+[、.．]|[0-9]+[、.．])\s*")


def _report_section_rows(
    report: ResearchReportDocument,
    key: str,
    *,
    limit: int = 6,
) -> list[str]:
    aliases = tuple(alias.lower() for alias in FORMAL_REPORT_SECTION_ALIASES.get(key, ()))
    if not aliases:
        return []
    rows: list[str] = []
    for section in report.sections:
        title = _context_text(section.title).lower()
        if not title or not any(alias in title for alias in aliases):
            continue
        rows.extend(_dedupe_export_rows([_context_text(item) for item in section.items], limit=limit))
    return _dedupe_export_rows(rows, limit=limit)


def _formal_document_kind_label(document_kind: str) -> str:
    if document_kind == "feasibility_study":
        return "可行性研究报告"
    if document_kind == "project_proposal":
        return "项目建议书"
    return "正式交付文档"


def _clean_formal_section_title(title: str) -> str:
    normalized = _context_text(title)
    normalized = _FORMAL_SECTION_PREFIX_RE.sub("", normalized)
    normalized = re.sub(r"^附[:：]\s*", "", normalized)
    normalized = re.sub(r"^补充[:：]\s*", "", normalized)
    normalized = re.sub(r"^附录[A-ZＡ-Ｚ]?[、:：]?\s*", "", normalized)
    return normalized or "未命名章节"


def _is_formal_appendix_title(raw_title: str, clean_title: str) -> bool:
    if raw_title.startswith(("附", "补充")):
        return True
    appendix_markers = (
        "人工输入与交叉验证说明",
        "专用编译器质量门槛",
        "交付前质量审查",
        "量化决策模型",
        "备选方案加权比选",
        "投标评分项响应矩阵",
        "可研财务三情景",
        "主张—证据",
        "主张-证据",
        "语义挑战者",
        "中文校对",
    )
    return any(marker in clean_title for marker in appendix_markers)


def _number_formal_document_sections(sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    """Apply stable document numbering without duplicating compiler-provided numbers."""
    numbered: list[tuple[str, list[str]]] = []
    main_index = 0
    appendix_index = 0
    for raw_title, rows in sections:
        title = _context_text(raw_title)
        clean_title = _clean_formal_section_title(title)
        if _is_formal_appendix_title(title, clean_title):
            letter = _FORMAL_APPENDIX_LETTERS[min(appendix_index, len(_FORMAL_APPENDIX_LETTERS) - 1)]
            numbered.append((f"附录{letter}：{clean_title}", rows))
            appendix_index += 1
            continue
        numeral = _FORMAL_SECTION_NUMERALS[min(main_index, len(_FORMAL_SECTION_NUMERALS) - 1)]
        numbered.append((f"{numeral}、{clean_title}", rows))
        main_index += 1
    return numbered


def _formal_layout_control_rows(*, document_kind: str, section_count: int) -> list[str]:
    return [
        f"渲染版本：anti-fomo-formal-renderer-v2 / {_formal_document_kind_label(document_kind)}",
        "页面规格：A4；页边距：上 72pt、下 72pt、左 56pt、右 56pt。",
        "标题编号：主章节使用中文序号；补充材料和模型附录使用附录 A/B/C 编号。",
        "表格规则：项目元信息、目录、章节内容和版式清单使用受控表格布局。",
        "页眉页脚：原生 DOCX 写入 Word header/footer 关系；PDF 预览逐页写入页眉页脚。",
        f"章节数量：{section_count}；往返校验需确认章节、编号、表格、证据锚点和附录未丢失。",
    ]


def _formal_roundtrip_checklist(
    *,
    document_kind: str,
    sections: list[tuple[str, list[str]]],
    renderer_strategy: str = "",
) -> list[str]:
    section_titles = [title for title, _rows in sections]
    appendix_count = sum(1 for title in section_titles if title.startswith("附录"))
    rows = [
        f"导出格式：原生 DOCX 与专业 PDF 预览均使用同一章节模型（{_formal_document_kind_label(document_kind)}）。",
        "打开 Word 后检查：标题页、元信息表、目录表、章节编号、附录编号和页眉页脚均可见。",
        "导出 PDF 后检查：章节标题、证据/假设/验证动作、量化模型附录和页脚页码未丢失。",
        f"附录数量：{appendix_count}；附录不得并入正文主章节或丢失编号。",
        "证据锚点：URL、文号、项目编号、source/chunk ID 或待核验动作必须保留在正文或附录。",
        "可替换资产：真实数据图表、客户品牌模板和图片资源替换槽必须在 DOCX/PPTX/PDF 预览中保留名称与来源。",
    ]
    if renderer_strategy:
        rows.append(renderer_strategy)
    return rows


def _formal_media_layout_rows(
    *,
    brand_template: FormalBrandTemplate | None = None,
    chart_assets: list[FormalMediaAsset] | None = None,
    image_assets: list[FormalMediaAsset] | None = None,
) -> list[str]:
    brand = brand_template or FormalBrandTemplate(
        template_id="anti-fomo-professional",
        display_name="Anti-FOMO Professional",
        primary_color="2563EB",
        secondary_color="0F766E",
        accent_color="F97316",
        logo_text="Anti-FOMO",
        footer_text="Anti-FOMO 正式交付 · evidence-first delivery",
        confidentiality_label="内部评审稿",
        font_family="Microsoft YaHei / PingFang SC / Aptos",
    )
    charts = chart_assets or []
    images = image_assets or []
    rows = [
        "专业模板：封面/摘要看板/元信息/可更新目录/正文表格/图表占位/图片占位/校对清单/往返清单必须完整。",
        f"客户品牌模板：{brand.display_name}；Logo 文案：{brand.logo_text}；品牌色：#{brand.primary_color}/#{brand.secondary_color}/#{brand.accent_color}；保密标识：{brand.confidentiality_label}。",
        "P2.4 可替换资产清单：DOCX/PPTX/PDF 预览必须保留资产名称、来源、单位、期间、替换槽和外发校验说明。",
        "P2.5 复杂样式模板与真实打开验证门禁：DOCX 写入 theme/numbering/多级清单，PPTX 写入原生可编辑图表对象和嵌入 workbook；LibreOffice/Word/PowerPoint 打开验证必须通过显式门禁执行。",
    ]
    for index, asset in enumerate(charts, start=1):
        data_summary = "；".join(asset.data_rows[:2]) or asset.description
        rows.append(
            f"真实数据图表 {index}：{asset.title}；{asset.description}；单位：{asset.unit}；期间：{asset.period}；来源：{asset.source}；替换槽：{asset.replacement_slot}；数据摘要：{data_summary}。"
        )
    for index, asset in enumerate(images, start=1):
        rows.append(
            f"可替换图片资源 {index}：{asset.title}；{asset.description}；素材要求：{asset.unit}；来源/授权：{asset.source}；替换槽：{asset.replacement_slot}。"
        )
    rows.extend(
        [
            "图表占位：预算、收益、证据覆盖、方案比选或实施阶段图表必须标注单位、期间、来源和假设。",
            "图片占位：客户场景、能力架构、系统集成或实施路线图必须使用可授权素材，禁止无来源素材。",
            "PDF 排版：导出后检查首页、页眉页脚、章节换页、表格边框、中文字符和证据锚点。",
        ]
    )
    return rows


def _formal_visual_fingerprint(
    *,
    title: str,
    document_kind: str,
    sections: list[tuple[str, list[str]]],
    proofreading_rows: list[str],
    asset_markers: list[str] | None = None,
) -> str:
    seed = "\n".join(
        [
            title,
            document_kind,
            *[section_title for section_title, _rows in sections],
            *proofreading_rows,
            *(asset_markers or []),
        ]
    )
    return sha256(seed.encode("utf-8")).hexdigest()[:16]


def _legacy_formal_section_alias(section_title: str) -> str:
    if not section_title.startswith("附录"):
        return ""
    clean_title = _clean_formal_section_title(section_title)
    return f"附：{clean_title}"


def _formal_artifact_diagnostics(payload: FormalDocumentRenderPayload) -> dict[str, object]:
    return {
        "renderer": "anti-fomo-formal-renderer-v3",
        "native_docx": True,
        "professional_template": "anti-fomo-p2.4-brand-media-template",
        "complex_style_template": "anti-fomo-p2.5-office-openxml-template",
        "native_image_embedding": "p2.6-openxml-media-part",
        "office_validation_gate": "structure_check_default; libreoffice_headless_or_gui_open_explicit_only",
        "brand_template": payload.brand_template.as_dict(),
        "replaceable_assets": {
            "chart_asset_count": len(payload.chart_assets),
            "image_asset_count": len(payload.image_assets),
            "chart_titles": [asset.title for asset in payload.chart_assets],
            "image_titles": [asset.title for asset in payload.image_assets],
        },
        "headless_conversion_strategy": payload.renderer_strategy,
        "visual_regression": {
            "fingerprint": payload.visual_fingerprint,
            "required_markers": [
                "项目元信息",
                "目录",
                "交付版式控制清单",
                "图表与图片排版占位",
                "P2.4 可替换资产清单",
                "客户品牌模板",
                "真实数据图表",
                "可替换图片资源",
                "P2.5 复杂样式模板与真实打开验证门禁",
                "原生可编辑图表对象",
                "原生图片嵌入",
                "中文校对清单",
                "PDF/Word 往返校验清单",
            ],
            "artifact_expectations": [
                "DOCX contains word/theme/theme1.xml and word/numbering.xml",
                "DOCX contains word/media/image1.png and document.xml references rIdImage1",
                "PPTX contains ppt/charts/chart1.xml and ppt/embeddings/chart-data.xlsx",
                "PPTX contains ppt/media/image1.png and slide rels reference rIdImage1",
                "QuickLook or LibreOffice conversion manifest can be generated before external send",
            ],
        },
        "roundtrip_checklist": payload.roundtrip_rows,
        "proofreading_findings": payload.proofreading_rows,
        "section_count": len(payload.sections),
        "appendix_count": sum(1 for title, _rows in payload.sections if title.startswith("附录")),
    }


def _formal_pdf_artifact_diagnostics(payload: FormalDocumentRenderPayload) -> dict[str, object]:
    return {
        "renderer": "anti-fomo-formal-pdf-renderer-v3",
        "controlled_pdf_preview": True,
        "professional_pdf_layout": "in-repo-controlled-preview",
        "professional_template": "anti-fomo-p2.4-brand-media-template",
        "professional_pdf_layout_version": "p2.7-vector-brand-media-image-preview",
        "complex_style_template": "anti-fomo-p2.5-office-openxml-template",
        "pdf_layout_profile": "p2.6-brand-media-grid",
        "native_pdf_image_embedding": "p2.7-pdf-image-xobject",
        "office_validation_gate": "structure_check_default; libreoffice_headless_or_gui_open_explicit_only",
        "brand_template": payload.brand_template.as_dict(),
        "replaceable_assets": {
            "chart_asset_count": len(payload.chart_assets),
            "image_asset_count": len(payload.image_assets),
            "chart_titles": [asset.title for asset in payload.chart_assets],
            "image_titles": [asset.title for asset in payload.image_assets],
        },
        "headless_conversion_strategy": payload.renderer_strategy,
        "visual_regression": {
            "fingerprint": payload.visual_fingerprint,
            "required_markers": [
                "Anti-FOMO 正式交付",
                "P2 controlled export",
                "项目元信息",
                "图表与图片排版占位",
                "P2.4 可替换资产清单",
                "客户品牌模板",
                "真实数据图表",
                "可替换图片资源",
                "P2.5 复杂样式模板与真实打开验证门禁",
                "P2.6 矢量品牌框架",
                "P2.7 原生 PDF 图片对象",
                "中文校对清单",
                "PDF/Word 往返校验清单",
            ],
            "artifact_expectations": [
                "PDF preview carries the same brand/media markers as DOCX",
                "PDF content stream includes vector brand frame and media-grid guide rails",
                "PDF content stream includes native Image XObject /Im1",
                "LibreOffice converted PDF can be compared through scripts/validate_office_roundtrip.py --libreoffice-convert",
                "QuickLook thumbnail manifest can be generated before external send",
            ],
        },
        "roundtrip_checklist": payload.roundtrip_rows,
        "proofreading_findings": payload.proofreading_rows,
        "section_count": len(payload.sections),
        "appendix_count": sum(1 for title, _rows in payload.sections if title.startswith("附录")),
    }


def _build_formal_document_context(
    report_payload: dict,
    *,
    output_language: str,
    delivery_supplement: dict | None,
) -> tuple[ResearchReportDocument, dict[str, object], dict[str, str]]:
    report = ResearchReportDocument.model_validate(report_payload)
    resolved_language = normalize_output_language(output_language or report.output_language)
    supplement = _normalize_research_delivery_supplement(delivery_supplement)
    scope_regions = _context_list(getattr(getattr(report, "source_diagnostics", None), "scope_regions", []), limit=2)
    solution_pack = getattr(report, "solution_delivery_pack", None)
    target_customer = (
        supplement.get("target_customer")
        or next((item.name for item in report.top_target_accounts if getattr(item, "name", "")), "")
        or next((item for item in report.target_accounts if _context_text(item)), "")
    )
    solution_scenario = (
        supplement.get("solution_scenario")
        or _context_text(getattr(solution_pack, "scenario", ""))
        or report.keyword
        or report.report_title
    )
    vertical_scene = (
        supplement.get("vertical_scene")
        or _context_text(getattr(solution_pack, "vertical_scene", ""))
        or report.research_focus
        or ""
    )
    project_owner = (
        supplement.get("project_owner")
        or target_customer
        or localized_text(
            resolved_language,
            {"zh-CN": "待补充业主/建设单位", "zh-TW": "待補充業主/建設單位", "en": "Owner to be confirmed"},
            "待补充业主/建设单位",
        )
    )
    default_project_name = (
        f"{target_customer}{solution_scenario}"
        if target_customer and solution_scenario
        else (
            f"{solution_scenario}建设项目"
            if solution_scenario
            else (
                f"{vertical_scene}建设项目"
                if vertical_scene
                else report.report_title
            )
        )
    )
    context = {
        "project_name": supplement.get("project_name")
        or default_project_name
        or localized_text(
            resolved_language,
            {"zh-CN": "专题研究项目", "zh-TW": "專題研究專案", "en": "Research Project"},
            "专题研究项目",
        ),
        "project_owner": project_owner,
        "target_customer": target_customer or project_owner,
        "solution_scenario": solution_scenario,
        "vertical_scene": vertical_scene,
        "project_region": supplement.get("project_region") or " / ".join(scope_regions) or report.keyword,
        "implementation_window": supplement.get("implementation_window")
        or next((item for item in report.tender_timeline if _context_text(item)), "")
        or localized_text(
            resolved_language,
            {"zh-CN": "建议按年度预算与招采窗口滚动推进", "zh-TW": "建議按年度預算與招採窗口滾動推進", "en": "Plan against annual budget and procurement windows"},
            "建议按年度预算与招采窗口滚动推进",
        ),
        "investment_estimate": supplement.get("investment_estimate")
        or next((item for item in report.budget_signals if _context_text(item)), "")
        or localized_text(
            resolved_language,
            {"zh-CN": "当前需结合公开预算与立项口径进一步测算", "zh-TW": "目前需結合公開預算與立項口徑進一步測算", "en": "Needs further sizing against public budget evidence"},
            "当前需结合公开预算与立项口径进一步测算",
        ),
        "construction_basis": supplement.get("construction_basis")
        or localized_text(
            resolved_language,
            {
                "zh-CN": "依据公开政策、招采公告、行业披露、公众号线索与当前研报结论交叉形成。",
                "zh-TW": "依據公開政策、招採公告、產業披露、公眾號線索與目前研報結論交叉形成。",
                "en": "Built from public policy, procurement notices, industry disclosures, curated WeChat leads, and the current research conclusion.",
            },
            "依据公开政策、招采公告、行业披露、公众号线索与当前研报结论交叉形成。",
        ),
        "scope_statement": supplement.get("scope_statement")
        or next((item for item in report.strategic_directions if _context_text(item)), "")
        or next((item for item in report.project_distribution if _context_text(item)), ""),
        "expected_benefits": supplement.get("expected_benefits")
        or next((item for item in report.five_year_outlook if _context_text(item)), "")
        or next((item for item in report.competition_analysis if _context_text(item)), ""),
        "cross_validation_notes": supplement.get("cross_validation_notes")
        or supplement.get("supplemental_evidence")
        or next((item for item in _report_followup_rows(report) if "新证据" in item), ""),
    }
    return report, supplement, context


def _build_runtime_formal_document_packs(
    report: ResearchReportDocument,
    *,
    context: dict[str, str],
    supplement: dict[str, str],
):
    market_pack = build_market_intelligence_pack(
        report,
        scenario=context.get("solution_scenario", ""),
        target_customer=context.get("target_customer", "") or context.get("project_owner", ""),
        vertical_scene=context.get("vertical_scene", ""),
    )
    solution_pack = build_solution_delivery_pack(
        report,
        scenario=context.get("solution_scenario", ""),
        target_customer=context.get("target_customer", "") or context.get("project_owner", ""),
        vertical_scene=context.get("vertical_scene", ""),
        supplemental_context=supplement.get("supplemental_context", ""),
    )
    return market_pack, solution_pack


def _build_formal_document_sections(
    *,
    report: ResearchReportDocument,
    output_language: str,
    document_kind: str,
    context: dict[str, str],
    supplement: dict[str, str],
) -> tuple[
    list[tuple[str, list[str]]],
    ResearchMarketIntelligencePackOut,
    ResearchSolutionDeliveryPackOut,
]:
    resolved_language = normalize_output_language(output_language or report.output_language)
    official_ratio = round(float(getattr(getattr(report, "source_diagnostics", None), "official_source_ratio", 0.0) or 0.0) * 100)
    evidence_rows = _dedupe_export_rows(
        [
            f"来源数量：{report.source_count}；证据密度：{report.evidence_density}；来源质量：{report.source_quality}；官方源占比：{official_ratio}%",
            context.get("construction_basis", ""),
            supplement.get("supplemental_context", ""),
            supplement.get("supplemental_evidence", ""),
            supplement.get("supplemental_requirements", ""),
            *_report_followup_rows(report),
        ],
        limit=8,
        preserve_labels=True,
    )
    market_pack, solution_pack = _build_runtime_formal_document_packs(
        report,
        context=context,
        supplement=supplement,
    )
    compiled_document = select_compiled_document(
        getattr(solution_pack, "compiled_documents", []) or [],
        document_kind,
    )
    if compiled_document is not None:
        sections = compiled_document_sections_for_formal_export(compiled_document)
        supplemental_rows = _dedupe_export_rows(
            [
                supplement.get("supplemental_context", ""),
                supplement.get("supplemental_evidence", ""),
                supplement.get("supplemental_requirements", ""),
                supplement.get("cross_validation_notes", ""),
                context.get("cross_validation_notes", ""),
                *_report_followup_rows(report),
            ],
            limit=10,
            preserve_labels=True,
        )
        if supplemental_rows:
            sections.insert(1, ("补充：人工输入与交叉验证说明", supplemental_rows))
        quantitative_sections = quantitative_decision_model_sections_for_formal_export(
            solution_pack.quantitative_decision_model
        )
        sections.extend([(title, rows) for title, rows in quantitative_sections if rows])
        return sections, market_pack, solution_pack
    tender_rows = _dedupe_export_rows(
        [
            *[
                f"{item.project_name}（{item.notice_type or '公开线索'} / {item.publish_date or '日期待核验'} / {item.amount or '金额待核验'}）"
                for item in list(getattr(market_pack, "tender_projects", []) or [])[:6]
            ],
            *list(getattr(market_pack, "intelligence_gaps", []) or [])[:3],
        ],
        limit=8,
    )
    product_rows = _dedupe_export_rows(
        [
            *[
                f"{item.name}：{'；'.join((item.technical_parameters or [])[:3]) or item.source_context or '参数待核验'}"
                for item in list(getattr(market_pack, "product_catalog", []) or [])[:6]
            ],
            *[
                f"{section.title}：{'；'.join((section.bullets or [])[:3])}"
                for section in list(getattr(solution_pack, "client_ppt_outline", []) or [])[:3]
            ],
        ],
        limit=10,
    )
    feasibility_sections = [
        (
            localized_text(resolved_language, {"zh-CN": "一、项目概况", "zh-TW": "一、專案概況", "en": "1. Project Overview"}, "一、项目概况"),
            _dedupe_export_rows(
                [
                    f"项目名称：{context['project_name']}",
                    f"建议业主/建设单位：{context['project_owner']}",
                    f"目标客户：{context['target_customer']}",
                    f"项目/方案场景：{context['solution_scenario']}",
                    f"垂直场景：{context['vertical_scene']}",
                    f"建议区域/范围：{context['project_region']}",
                    f"实施窗口：{context['implementation_window']}",
                    f"核心结论：{report.executive_summary}",
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "二、研究依据与交叉验证输入", "zh-TW": "二、研究依據與交叉驗證輸入", "en": "2. Inputs and Cross-Validation"}, "二、研究依据与交叉验证输入"),
            evidence_rows,
        ),
        (
            localized_text(resolved_language, {"zh-CN": "三、建设必要性与需求分析", "zh-TW": "三、建設必要性與需求分析", "en": "3. Need and Demand Analysis"}, "三、建设必要性与需求分析"),
            _dedupe_export_rows(
                [
                    report.consulting_angle,
                    *tender_rows[:4],
                    *report.commercial_summary.account_focus,
                    *report.budget_signals,
                    *report.leadership_focus,
                    *report.key_people,
                ],
                limit=8,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "四、建设目标与范围", "zh-TW": "四、建設目標與範圍", "en": "4. Goals and Scope"}, "四、建设目标与范围"),
            _dedupe_export_rows(
                [
                    context.get("scope_statement", ""),
                    f"项目/方案场景：{context['solution_scenario']}",
                    f"垂直场景：{context['vertical_scene']}",
                    supplement.get("supplemental_requirements", ""),
                    *report.strategic_directions,
                    *report.project_distribution,
                    *report.target_departments,
                ],
                limit=8,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "五、可行性分析", "zh-TW": "五、可行性分析", "en": "5. Feasibility Analysis"}, "五、可行性分析"),
            _dedupe_export_rows(
                [
                    *_report_section_rows(report, "solution_design", limit=6),
                    *product_rows,
                    *report.benchmark_cases,
                    *report.flagship_products,
                    *report.public_contact_channels,
                    *report.account_team_signals,
                ],
                limit=10,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "六、投资估算与综合效益", "zh-TW": "六、投資估算與綜合效益", "en": "6. Investment and Benefits"}, "六、投资估算与综合效益"),
            _dedupe_export_rows(
                [
                    f"投资估算/预算口径：{context['investment_estimate']}",
                    context.get("expected_benefits", ""),
                    *report.budget_signals,
                    *report.five_year_outlook,
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "七、实施路径与保障措施", "zh-TW": "七、實施路徑與保障措施", "en": "7. Implementation and Assurance"}, "七、实施路径与保障措施"),
            _dedupe_export_rows(
                [
                    *report.tender_timeline,
                    *_report_section_rows(report, "sales_strategy", limit=5),
                    *_report_section_rows(report, "bidding_strategy", limit=5),
                    *_report_section_rows(report, "outreach_strategy", limit=5),
                    *_report_section_rows(report, "next_actions", limit=5),
                ],
                limit=10,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "八、风险控制与结论建议", "zh-TW": "八、風險控制與結論建議", "en": "8. Risks and Recommendation"}, "八、风险控制与结论建议"),
            _dedupe_export_rows(
                [
                    *report.competition_analysis,
                    *report.technical_appendix.limitations,
                    *[item.summary for item in report.review_queue],
                    report.commercial_summary.next_action,
                ],
                limit=8,
            ),
        ),
    ]
    proposal_sections = [
        (
            localized_text(resolved_language, {"zh-CN": "一、项目背景", "zh-TW": "一、專案背景", "en": "1. Project Background"}, "一、项目背景"),
            _dedupe_export_rows(
                [
                    f"项目名称：{context['project_name']}",
                    f"建议建设单位：{context['project_owner']}",
                    f"目标客户：{context['target_customer']}",
                    f"项目/方案场景：{context['solution_scenario']}",
                    f"垂直场景：{context['vertical_scene']}",
                    f"建议建设区域：{context['project_region']}",
                    report.executive_summary,
                    context.get("construction_basis", ""),
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "二、建设目标", "zh-TW": "二、建設目標", "en": "2. Objectives"}, "二、建设目标"),
            _dedupe_export_rows(
                [
                    context.get("scope_statement", ""),
                    f"项目/方案场景：{context['solution_scenario']}",
                    f"垂直场景：{context['vertical_scene']}",
                    supplement.get("supplemental_requirements", ""),
                    *report.strategic_directions,
                    *report.target_departments,
                    *product_rows[:4],
                ],
                limit=8,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "三、建设内容与方案设计", "zh-TW": "三、建設內容與方案設計", "en": "3. Scope and Solution"}, "三、建设内容与方案设计"),
            _dedupe_export_rows(
                [
                    *_report_section_rows(report, "solution_design", limit=6),
                    *product_rows,
                    *report.benchmark_cases,
                    *report.flagship_products,
                    *report.ecosystem_partners,
                ],
                limit=10,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "四、实施计划", "zh-TW": "四、實施計畫", "en": "4. Implementation Plan"}, "四、实施计划"),
            _dedupe_export_rows(
                [
                    f"建议实施窗口：{context['implementation_window']}",
                    *report.tender_timeline,
                    *_report_section_rows(report, "next_actions", limit=5),
                    *_report_section_rows(report, "sales_strategy", limit=5),
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "五、投资测算与预期效益", "zh-TW": "五、投資測算與預期效益", "en": "5. Investment and Outcomes"}, "五、投资测算与预期效益"),
            _dedupe_export_rows(
                [
                    f"建议投资口径：{context['investment_estimate']}",
                    context.get("expected_benefits", ""),
                    *report.budget_signals,
                    *report.five_year_outlook,
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "六、组织协同与风险提示", "zh-TW": "六、組織協同與風險提示", "en": "6. Organization and Risks"}, "六、组织协同与风险提示"),
            _dedupe_export_rows(
                [
                    *report.account_team_signals,
                    *report.public_contact_channels,
                    *report.competition_analysis,
                    *report.technical_appendix.limitations,
                    *[item.summary for item in report.review_queue],
                ],
                limit=10,
            ),
        ),
        (
            localized_text(resolved_language, {"zh-CN": "七、交叉验证附注", "zh-TW": "七、交叉驗證附註", "en": "7. Cross-Validation Notes"}, "七、交叉验证附注"),
            _dedupe_export_rows(
                [
                    supplement.get("cross_validation_notes", ""),
                    context.get("cross_validation_notes", ""),
                    *evidence_rows,
                ],
                limit=8,
                preserve_labels=True,
            ),
        ),
    ]
    sections = feasibility_sections if document_kind == "feasibility_study" else proposal_sections
    quantitative_sections = quantitative_decision_model_sections_for_formal_export(
        solution_pack.quantitative_decision_model
    )
    sections.extend([(title, rows) for title, rows in quantitative_sections if rows])
    return sections, market_pack, solution_pack


def _build_formal_document_html(
    *,
    title: str,
    subtitle: str,
    meta_rows: list[str],
    sections: list[tuple[str, list[str]]],
    document_kind: str,
    proofreading_rows: list[str],
    visual_fingerprint: str,
    brand_template: FormalBrandTemplate,
    chart_assets: list[FormalMediaAsset],
    image_assets: list[FormalMediaAsset],
    renderer_strategy: str,
) -> str:
    layout_rows = _formal_layout_control_rows(document_kind=document_kind, section_count=len(sections))
    roundtrip_rows = _formal_roundtrip_checklist(
        document_kind=document_kind,
        sections=sections,
        renderer_strategy=renderer_strategy,
    )
    media_layout_rows = _formal_media_layout_rows(
        brand_template=brand_template,
        chart_assets=chart_assets,
        image_assets=image_assets,
    )
    blocks = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8' />",
        "<style>",
        "@page WordSection1{size:595.3pt 841.9pt;margin:72pt 56pt 72pt 56pt;mso-header:afHeader;mso-footer:afFooter;}",
        "div.WordSection1{page:WordSection1;}",
        "body{font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif;color:#0f172a;line-height:1.65;background:#ffffff;}",
        "h1{font-size:28px;margin:0 0 8px;text-align:center;font-weight:700;}h2{font-size:18px;margin:22px 0 10px;color:#0f172a;border-bottom:1px solid #cbd5e1;padding-bottom:4px;}p{margin:0;}",
        "table{width:100%;border-collapse:collapse;margin:8px 0 18px;table-layout:fixed;}th,td{border:1px solid #cbd5e1;padding:7px 9px;vertical-align:top;}th{background:#eef6ff;font-weight:700;color:#0f172a;}",
        ".subtitle{color:#475569;font-size:13px;margin-bottom:18px;text-align:center;}.meta-label{width:24%;font-weight:700;background:#f8fbff;}",
        ".section{margin-top:16px;page-break-inside:auto;}.row-index{width:44px;text-align:center;color:#475569;background:#f8fafc;}.toc-index{width:52px;text-align:center;color:#475569;background:#f8fafc;}",
        ".control{font-size:12px;color:#334155;}.header,.footer{font-size:10px;color:#64748b;border:0;margin:0;}.footer{text-align:center;}",
        "</style></head><body><div class='WordSection1'>",
        f"<div style='mso-element:header' id='afHeader'><p class='header'>{html.escape(brand_template.logo_text)} · Anti-FOMO 正式交付 · {html.escape(_formal_document_kind_label(document_kind))} · {html.escape(title)}</p></div>",
        f"<div style='mso-element:footer' id='afFooter'><p class='footer'>P2 controlled export · P2.4 brand/media · {html.escape(brand_template.confidentiality_label)} · 页 <span style='mso-field-code:\" PAGE \"'></span> / <span style='mso-field-code:\" NUMPAGES \"'></span> · 证据锚点随正文保留</p></div>",
        f"<meta name='af-visual-fingerprint' content='{html.escape(visual_fingerprint, quote=True)}' />",
        f"<h1>{html.escape(title)}</h1>",
        f"<p class='subtitle'>{html.escape(subtitle)}</p>",
        "<h2>项目元信息</h2><table class='meta'>",
    ]
    for row in meta_rows:
        text = _context_text(row, preserve_labels=True)
        if not text:
            continue
        if "：" in text:
            label, value = text.split("：", 1)
        elif ":" in text:
            label, value = text.split(":", 1)
        else:
            label, value = "说明", text
        plain_text = f"{label.strip()}：{value.strip()}"
        blocks.append(
            f"<tr data-plain='{html.escape(plain_text, quote=True)}'><td class='meta-label'>{html.escape(label.strip())}</td><td>{html.escape(value.strip())}</td></tr>"
        )
    blocks.append("</table>")
    blocks.append("<h2>目录</h2><table class='toc'>")
    blocks.append("<tr><th class='toc-index'>序号</th><th>章节</th></tr>")
    for index, (section_title, _rows) in enumerate(sections, start=1):
        alias = _legacy_formal_section_alias(section_title)
        blocks.append(
            f"<tr data-original-title='{html.escape(alias, quote=True)}'><td class='toc-index'>{index}</td><td>{html.escape(section_title)}</td></tr>"
        )
    blocks.append("</table>")
    blocks.append("<h2>图表与图片排版占位</h2><table class='control'>")
    blocks.append("<tr><th class='row-index'>序号</th><th>专业排版要求</th></tr>")
    for index, row in enumerate(media_layout_rows, start=1):
        blocks.append(f"<tr><td class='row-index'>{index}</td><td>{html.escape(row)}</td></tr>")
    blocks.append("</table>")
    blocks.append("<h2>交付版式控制清单</h2><table class='control'>")
    blocks.append("<tr><th class='row-index'>序号</th><th>控制项</th></tr>")
    for index, row in enumerate(layout_rows, start=1):
        blocks.append(f"<tr><td class='row-index'>{index}</td><td>{html.escape(row)}</td></tr>")
    blocks.append("</table>")
    for section_title, rows in sections:
        alias = _legacy_formal_section_alias(section_title)
        blocks.append(
            f"<div class='section'><h2 data-original-title='{html.escape(alias, quote=True)}'>{html.escape(section_title)}</h2><table>"
        )
        blocks.append("<tr><th class='row-index'>序号</th><th>内容 / 证据 / 验证动作</th></tr>")
        for index, row in enumerate([row for row in rows if _context_text(row)], start=1):
            blocks.append(f"<tr><td class='row-index'>{index}</td><td>{html.escape(row)}</td></tr>")
        blocks.append("</table></div>")
    blocks.append("<h2>中文校对清单</h2><table class='control'>")
    blocks.append("<tr><th class='row-index'>序号</th><th>问题 / 建议</th></tr>")
    for index, row in enumerate(proofreading_rows, start=1):
        blocks.append(f"<tr><td class='row-index'>{index}</td><td>{html.escape(row)}</td></tr>")
    blocks.append("</table>")
    blocks.append("<h2>PDF/Word 往返校验清单</h2><table class='control'>")
    blocks.append("<tr><th class='row-index'>序号</th><th>校验项</th></tr>")
    for index, row in enumerate(roundtrip_rows, start=1):
        blocks.append(f"<tr><td class='row-index'>{index}</td><td>{html.escape(row)}</td></tr>")
    blocks.append("</table>")
    blocks.append("</div></body></html>")
    return "\n".join(blocks)


def _build_formal_document_plaintext(
    *,
    title: str,
    subtitle: str,
    meta_rows: list[str],
    sections: list[tuple[str, list[str]]],
    document_kind: str,
    proofreading_rows: list[str],
    visual_fingerprint: str,
    brand_template: FormalBrandTemplate,
    chart_assets: list[FormalMediaAsset],
    image_assets: list[FormalMediaAsset],
    renderer_strategy: str,
) -> str:
    media_layout_rows = _formal_media_layout_rows(
        brand_template=brand_template,
        chart_assets=chart_assets,
        image_assets=image_assets,
    )
    lines = [
        f"[页眉] Anti-FOMO 正式交付 · {_formal_document_kind_label(document_kind)} · {title} · 品牌：{brand_template.logo_text}",
        title,
        "",
        subtitle,
        "",
        "项目元信息",
        f"视觉回归指纹：{visual_fingerprint}",
    ]
    lines.extend([f"- {row}" for row in meta_rows if _context_text(row)])
    lines.extend(["", "目录"])
    lines.extend([
        f"{index}. {section_title}{f'（原：{_legacy_formal_section_alias(section_title)}）' if _legacy_formal_section_alias(section_title) else ''}"
        for index, (section_title, _rows) in enumerate(sections, start=1)
    ])
    lines.extend(["", "图表与图片排版占位"])
    lines.extend([f"- {row}" for row in media_layout_rows])
    lines.extend(["", "交付版式控制清单"])
    lines.extend([
        f"- {row}"
        for row in _formal_layout_control_rows(document_kind=document_kind, section_count=len(sections))
    ])
    for section_title, rows in sections:
        lines.extend(["", section_title])
        lines.extend([f"- {row}" for row in rows if _context_text(row)])
    lines.extend(["", "中文校对清单"])
    lines.extend([f"- {row}" for row in proofreading_rows])
    lines.extend(["", "PDF/Word 往返校验清单"])
    lines.extend([
        f"- {row}"
        for row in _formal_roundtrip_checklist(
            document_kind=document_kind,
            sections=sections,
            renderer_strategy=renderer_strategy,
        )
    ])
    lines.append(
        f"[页脚] P2 controlled export · P2.4 brand/media · {brand_template.confidentiality_label} · {_formal_document_kind_label(document_kind)} · 证据锚点随正文保留"
    )
    return "\n".join(lines).strip()


def _build_formal_document_render_payload(
    *,
    report_payload: dict,
    output_language: str,
    document_kind: str,
    delivery_supplement: dict | None,
) -> FormalDocumentRenderPayload:
    report, supplement, context = _build_formal_document_context(
        report_payload,
        output_language=output_language,
        delivery_supplement=delivery_supplement,
    )
    resolved_language = normalize_output_language(output_language or report.output_language)
    title = (
        f"{context['project_name']}可行性研究报告"
        if document_kind == "feasibility_study"
        else f"{context['project_name']}项目建议书"
    )
    subtitle = localized_text(
        resolved_language,
        {
            "zh-CN": "基于当前研报、公开来源与人工补充信息交叉整理",
            "zh-TW": "基於目前研報、公開來源與人工補充資訊交叉整理",
            "en": "Compiled from the current research report, public sources, and manual supplements.",
        },
        "基于当前研报、公开来源与人工补充信息交叉整理",
    )
    meta_rows = _dedupe_export_rows(
        [
            f"项目名称：{context['project_name']}",
            f"建议业主/建设单位：{context['project_owner']}",
            f"目标客户：{context['target_customer']}",
            f"项目/方案场景：{context['solution_scenario']}",
            f"垂直场景：{context['vertical_scene']}",
            f"建议区域：{context['project_region']}",
            f"实施窗口：{context['implementation_window']}",
            f"投资估算：{context['investment_estimate']}",
            f"来源数量：{report.source_count}",
            supplement.get("cross_validation_notes", ""),
        ],
        limit=8,
        preserve_labels=True,
    )
    sections, market_pack, solution_pack = _build_formal_document_sections(
        report=report,
        output_language=resolved_language,
        document_kind=document_kind,
        context=context,
        supplement=supplement,
    )
    sections, _delivery_quality = review_and_improve_formal_document_sections(
        sections,
        review_target=document_kind,
        source_support_score=max(
            int(getattr(market_pack, "source_support_score", 0) or 0),
            int(getattr(solution_pack, "source_support_score", 0) or 0),
        ),
        grounded_count=len(list(getattr(solution_pack, "grounding_checks", []) or [])),
        checklist_count=len(list(getattr(solution_pack, "review_checklist", []) or [])),
        evidence_note_count=len(list(getattr(solution_pack, "intelligence_summary", []) or []))
        + len(list(getattr(market_pack, "intelligence_gaps", []) or [])),
        evidence_links=_formal_document_evidence_links(report),
        expected_entities=_dedupe_export_rows(
            [
                context["target_customer"],
                context["project_owner"],
                *report.target_accounts[:3],
            ],
            limit=5,
        ),
        expected_scope_terms=_dedupe_export_rows(
            [
                context["solution_scenario"],
                context["vertical_scene"],
                context["target_customer"],
                context["project_owner"],
                context["project_region"],
                *report.target_accounts[:3],
            ],
            limit=8,
        ),
    )
    sections = _number_formal_document_sections(sections)
    delivery_assets = _formal_delivery_assets(
        report=report,
        supplement=supplement,
        context=context,
    )
    media_layout_rows = _formal_media_layout_rows(
        brand_template=delivery_assets.brand_template,
        chart_assets=delivery_assets.chart_assets,
        image_assets=delivery_assets.image_assets,
    )
    proofread_lines = [
        title,
        subtitle,
        *meta_rows,
        *media_layout_rows,
        *[section_title for section_title, _rows in sections],
        *[row for _section_title, rows in sections for row in rows],
    ]
    proofreading_rows = proofread_chinese_delivery_text(proofread_lines)
    layout_rows = _formal_layout_control_rows(document_kind=document_kind, section_count=len(sections))
    roundtrip_rows = _formal_roundtrip_checklist(
        document_kind=document_kind,
        sections=sections,
        renderer_strategy=delivery_assets.renderer_strategy,
    )
    visual_fingerprint = _formal_visual_fingerprint(
        title=title,
        document_kind=document_kind,
        sections=sections,
        proofreading_rows=proofreading_rows,
        asset_markers=[
            delivery_assets.brand_template.display_name,
            delivery_assets.brand_template.logo_text,
            delivery_assets.renderer_strategy,
            *[asset.title for asset in delivery_assets.chart_assets],
            *[asset.title for asset in delivery_assets.image_assets],
        ],
    )
    html_content = _build_formal_document_html(
        title=title,
        subtitle=subtitle,
        meta_rows=meta_rows,
        sections=sections,
        document_kind=document_kind,
        proofreading_rows=proofreading_rows,
        visual_fingerprint=visual_fingerprint,
        brand_template=delivery_assets.brand_template,
        chart_assets=delivery_assets.chart_assets,
        image_assets=delivery_assets.image_assets,
        renderer_strategy=delivery_assets.renderer_strategy,
    )
    plain_text = _build_formal_document_plaintext(
        title=title,
        subtitle=subtitle,
        meta_rows=meta_rows,
        sections=sections,
        document_kind=document_kind,
        proofreading_rows=proofreading_rows,
        visual_fingerprint=visual_fingerprint,
        brand_template=delivery_assets.brand_template,
        chart_assets=delivery_assets.chart_assets,
        image_assets=delivery_assets.image_assets,
        renderer_strategy=delivery_assets.renderer_strategy,
    )
    return FormalDocumentRenderPayload(
        title=title,
        subtitle=subtitle,
        document_kind=document_kind,
        meta_rows=meta_rows,
        sections=sections,
        layout_rows=layout_rows,
        roundtrip_rows=roundtrip_rows,
        proofreading_rows=proofreading_rows,
        visual_fingerprint=visual_fingerprint,
        brand_template=delivery_assets.brand_template,
        chart_assets=delivery_assets.chart_assets,
        image_assets=delivery_assets.image_assets,
        renderer_strategy=delivery_assets.renderer_strategy,
        html_content=html_content,
        plain_text=plain_text,
    )


def _build_formal_document_bundle(
    *,
    report_payload: dict,
    output_language: str,
    document_kind: str,
    delivery_supplement: dict | None,
) -> tuple[str, str, str]:
    payload = _build_formal_document_render_payload(
        report_payload=report_payload,
        output_language=output_language,
        document_kind=document_kind,
        delivery_supplement=delivery_supplement,
    )
    return payload.title, payload.html_content, payload.plain_text


def build_feasibility_study_word_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str]:
    title, html_content, _ = _build_formal_document_bundle(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="feasibility_study",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in title if ch.isalnum() or ch in {" ", "-", "_"}) or "feasibility-study"
    return f"{filename_seed[:48].replace(' ', '_')}.doc", html_content, "application/msword"


def build_feasibility_study_docx_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str, str, dict[str, object]]:
    payload = _build_formal_document_render_payload(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="feasibility_study",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in payload.title if ch.isalnum() or ch in {" ", "-", "_"}) or "feasibility-study"
    docx_bytes = build_docx_bytes(
        title=payload.title,
        subtitle=payload.subtitle,
        document_kind_label=_formal_document_kind_label(payload.document_kind),
        meta_rows=payload.meta_rows,
        sections=payload.sections,
        layout_rows=payload.layout_rows,
        roundtrip_rows=payload.roundtrip_rows,
        proofreading_rows=payload.proofreading_rows,
        brand_template=payload.brand_template.as_dict(),
        chart_assets=[asset.as_dict() for asset in payload.chart_assets],
        image_assets=[asset.as_dict() for asset in payload.image_assets],
        renderer_strategy=payload.renderer_strategy,
    )
    diagnostics = _formal_artifact_diagnostics(payload)
    office_roundtrip = validate_docx_bytes(
        docx_bytes,
        required_texts=[
            payload.title,
            "Anti-FOMO P2.3 专业交付模板",
            "图表与图片排版占位",
            "P2.4 可替换资产清单",
            "客户品牌模板",
            "真实数据图表",
            "可替换图片资源",
            "P2.5 复杂样式模板与真实打开验证门禁",
            "原生图片嵌入",
            "中文校对清单",
            "PDF/Word 往返校验清单",
        ],
    )
    diagnostics["office_roundtrip"] = office_roundtrip
    diagnostics["complex_template_parts"] = office_roundtrip.get("complex_template_parts", [])
    diagnostics["native_images"] = bool(office_roundtrip.get("native_images"))
    diagnostics["native_image_parts"] = office_roundtrip.get("native_image_parts", [])
    return (
        f"{filename_seed[:48].replace(' ', '_')}.docx",
        payload.html_content,
        b64encode(docx_bytes).decode("ascii"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        diagnostics,
    )


def build_feasibility_study_pdf_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str, str]:
    filename, plain_text, content_base64, mime_type, _diagnostics = build_feasibility_study_pdf_document_with_diagnostics(
        report_payload,
        output_language=output_language,
        delivery_supplement=delivery_supplement,
    )
    return filename, plain_text, content_base64, mime_type


def build_feasibility_study_pdf_document_with_diagnostics(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str, str, dict[str, object]]:
    payload = _build_formal_document_render_payload(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="feasibility_study",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in payload.title if ch.isalnum() or ch in {" ", "-", "_"}) or "feasibility-study"
    pdf_bytes = _build_simple_pdf(
        payload.plain_text.splitlines(),
        header=f"Anti-FOMO 正式交付 · 可行性研究报告 · {payload.title}",
        footer="P2 controlled export · 页 {page}/{total} · 证据锚点随正文保留",
        layout_profile="p2.6-brand-media-grid",
    )
    diagnostics = _formal_pdf_artifact_diagnostics(payload)
    diagnostics["office_roundtrip"] = validate_pdf_bytes(pdf_bytes)
    return (
        f"{filename_seed[:48].replace(' ', '_')}.pdf",
        payload.plain_text,
        b64encode(pdf_bytes).decode("ascii"),
        "application/pdf",
        diagnostics,
    )


def build_research_market_intelligence_markdown(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str]:
    report = ResearchReportDocument.model_validate(report_payload)
    supplement = _normalize_research_delivery_supplement(delivery_supplement)
    pack = build_market_intelligence_pack(
        report,
        scenario=supplement.get("solution_scenario", ""),
        target_customer=supplement.get("target_customer", "") or supplement.get("project_owner", ""),
        vertical_scene=supplement.get("vertical_scene", ""),
    )
    filename_seed = "".join(
        ch
        for ch in (
            supplement.get("solution_scenario")
            or supplement.get("vertical_scene")
            or supplement.get("target_customer")
            or report.keyword
            or "market-intelligence"
        )
        if ch.isalnum() or ch in {" ", "-", "_"}
    ).strip().replace(" ", "_")
    if not filename_seed:
        filename_seed = "market-intelligence"
    return f"{filename_seed[:48]}-intelligence-pack.md", pack.export_markdown


def build_research_solution_delivery_markdown(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str]:
    report = ResearchReportDocument.model_validate(report_payload)
    supplement = _normalize_research_delivery_supplement(delivery_supplement)
    pack = build_solution_delivery_pack(
        report,
        scenario=supplement.get("solution_scenario", ""),
        target_customer=supplement.get("target_customer", "") or supplement.get("project_owner", ""),
        vertical_scene=supplement.get("vertical_scene", ""),
        supplemental_context=supplement.get("supplemental_context", ""),
    )
    filename_seed = "".join(
        ch
        for ch in (
            supplement.get("solution_scenario")
            or supplement.get("vertical_scene")
            or supplement.get("target_customer")
            or report.keyword
            or "solution-delivery"
        )
        if ch.isalnum() or ch in {" ", "-", "_"}
    ).strip().replace(" ", "_")
    if not filename_seed:
        filename_seed = "solution-delivery"
    return f"{filename_seed[:48]}-solution-delivery.md", pack.export_markdown


def build_research_solution_delivery_pptx_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str, str, dict[str, object]]:
    report, supplement, context = _build_formal_document_context(
        report_payload,
        output_language=output_language,
        delivery_supplement=delivery_supplement,
    )
    pack = build_solution_delivery_pack(
        report,
        scenario=_formal_supplement_text(supplement, "solution_scenario"),
        target_customer=_formal_supplement_text(supplement, "target_customer")
        or _formal_supplement_text(supplement, "project_owner"),
        vertical_scene=_formal_supplement_text(supplement, "vertical_scene"),
        supplemental_context=_formal_supplement_text(supplement, "supplemental_context"),
    )
    title = (
        _formal_supplement_text(supplement, "project_name")
        or _formal_supplement_text(supplement, "solution_scenario")
        or _formal_supplement_text(supplement, "vertical_scene")
        or report.report_title
        or "solution-delivery"
    )
    delivery_assets = _formal_delivery_assets(
        report=report,
        supplement=supplement,
        context=context,
    )
    deck_title = f"{title}对客汇报PPT"
    slides = [
        (section.title, list(section.bullets or []))
        for section in list(getattr(pack, "client_ppt_outline", []) or [])
        if _context_text(getattr(section, "title", ""))
    ]
    if not slides:
        slides = [("方案交付概览", list(getattr(pack, "intelligence_summary", []) or [])[:5])]
    pptx_bytes = build_pptx_bytes(
        title=deck_title,
        subtitle="Anti-FOMO P2.3 editable PPTX template · P2.4 customer brand/media",
        slides=slides,
        brand_template=delivery_assets.brand_template.as_dict(),
        chart_assets=[asset.as_dict() for asset in delivery_assets.chart_assets],
        image_assets=[asset.as_dict() for asset in delivery_assets.image_assets],
    )
    filename_seed = "".join(ch for ch in deck_title if ch.isalnum() or ch in {" ", "-", "_"}) or "solution-delivery"
    preview = "\n".join(
        [
            deck_title,
            "",
            "PPTX 可编辑导出预览",
            f"客户品牌模板：{delivery_assets.brand_template.display_name} / {delivery_assets.brand_template.logo_text}",
            "P2.4 可替换资产清单",
            "P2.5 原生可编辑图表对象",
            *[f"- 真实数据图表：{asset.title}（{asset.source}）" for asset in delivery_assets.chart_assets[:3]],
            *[f"- 可替换图片资源：{asset.title}（{asset.source}）" for asset in delivery_assets.image_assets[:3]],
            *[f"- {title}: {'；'.join(rows[:3])}" for title, rows in slides[:8]],
        ]
    ).strip()
    diagnostics = {
        "renderer": "anti-fomo-pptx-renderer-v1",
        "slide_count": len(slides) + 1,
        "editable_text_boxes": True,
        "professional_template": "anti-fomo-p2.4-brand-media-pptx-template",
        "complex_style_template": "anti-fomo-p2.5-office-openxml-template",
        "office_validation_gate": "structure_check_default; libreoffice_headless_or_gui_open_explicit_only",
        "brand_template": delivery_assets.brand_template.as_dict(),
        "replaceable_assets": {
            "chart_asset_count": len(delivery_assets.chart_assets),
            "image_asset_count": len(delivery_assets.image_assets),
            "chart_titles": [asset.title for asset in delivery_assets.chart_assets],
            "image_titles": [asset.title for asset in delivery_assets.image_assets],
        },
        "headless_conversion_strategy": delivery_assets.renderer_strategy,
        "visual_regression": {
            "fingerprint": sha256((deck_title + "\n" + "\n".join(title for title, _rows in slides)).encode("utf-8")).hexdigest()[:16],
            "required_markers": [
                "Anti-FOMO P2.3 editable PPTX template",
                "P2.4 可替换资产清单",
                "客户品牌模板",
                "真实数据图表",
                "可替换图片资源",
                "原生可编辑图表对象",
            "P2.5 Native Editable Chart",
            "原生图片嵌入",
            "图表占位",
            "图片占位",
            "client_ppt_outline",
            ],
            "artifact_expectations": [
                "PPTX contains ppt/charts/chart1.xml",
                "PPTX contains ppt/embeddings/chart-data.xlsx",
                "slide rels reference rIdChart1 as native editable chart",
                "PPTX contains ppt/media/image1.png and slide rels reference rIdImage1",
            ],
        },
    }
    office_roundtrip = validate_pptx_bytes(
        pptx_bytes,
        required_texts=[
            deck_title,
            "Anti-FOMO P2.3 editable PPTX template",
            "P2.4 customer brand/media",
            "客户品牌模板",
            "真实数据图表",
            "可替换图片资源",
            "P2.5 Native Editable Chart",
            "原生图片嵌入",
            "图表占位",
            "图片占位",
        ],
    )
    diagnostics["office_roundtrip"] = office_roundtrip
    diagnostics["native_editable_charts"] = bool(office_roundtrip.get("native_editable_charts"))
    diagnostics["native_chart_parts"] = office_roundtrip.get("native_chart_parts", [])
    diagnostics["embedded_workbooks"] = office_roundtrip.get("embedded_workbooks", [])
    diagnostics["native_images"] = bool(office_roundtrip.get("native_images"))
    diagnostics["native_image_parts"] = office_roundtrip.get("native_image_parts", [])
    return (
        f"{filename_seed[:48].replace(' ', '_')}.pptx",
        preview,
        b64encode(pptx_bytes).decode("ascii"),
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        diagnostics,
    )


def build_project_proposal_word_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str]:
    title, html_content, _ = _build_formal_document_bundle(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="project_proposal",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in title if ch.isalnum() or ch in {" ", "-", "_"}) or "project-proposal"
    return f"{filename_seed[:48].replace(' ', '_')}.doc", html_content, "application/msword"


def build_project_proposal_docx_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str, str, dict[str, object]]:
    payload = _build_formal_document_render_payload(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="project_proposal",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in payload.title if ch.isalnum() or ch in {" ", "-", "_"}) or "project-proposal"
    docx_bytes = build_docx_bytes(
        title=payload.title,
        subtitle=payload.subtitle,
        document_kind_label=_formal_document_kind_label(payload.document_kind),
        meta_rows=payload.meta_rows,
        sections=payload.sections,
        layout_rows=payload.layout_rows,
        roundtrip_rows=payload.roundtrip_rows,
        proofreading_rows=payload.proofreading_rows,
        brand_template=payload.brand_template.as_dict(),
        chart_assets=[asset.as_dict() for asset in payload.chart_assets],
        image_assets=[asset.as_dict() for asset in payload.image_assets],
        renderer_strategy=payload.renderer_strategy,
    )
    diagnostics = _formal_artifact_diagnostics(payload)
    office_roundtrip = validate_docx_bytes(
        docx_bytes,
        required_texts=[
            payload.title,
            "Anti-FOMO P2.3 专业交付模板",
            "图表与图片排版占位",
            "P2.4 可替换资产清单",
            "客户品牌模板",
            "真实数据图表",
            "可替换图片资源",
            "P2.5 复杂样式模板与真实打开验证门禁",
            "原生图片嵌入",
            "中文校对清单",
            "PDF/Word 往返校验清单",
        ],
    )
    diagnostics["office_roundtrip"] = office_roundtrip
    diagnostics["complex_template_parts"] = office_roundtrip.get("complex_template_parts", [])
    diagnostics["native_images"] = bool(office_roundtrip.get("native_images"))
    diagnostics["native_image_parts"] = office_roundtrip.get("native_image_parts", [])
    return (
        f"{filename_seed[:48].replace(' ', '_')}.docx",
        payload.html_content,
        b64encode(docx_bytes).decode("ascii"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        diagnostics,
    )


def build_project_proposal_pdf_document(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str, str]:
    filename, plain_text, content_base64, mime_type, _diagnostics = build_project_proposal_pdf_document_with_diagnostics(
        report_payload,
        output_language=output_language,
        delivery_supplement=delivery_supplement,
    )
    return filename, plain_text, content_base64, mime_type


def build_project_proposal_pdf_document_with_diagnostics(
    report_payload: dict,
    *,
    output_language: str = "zh-CN",
    delivery_supplement: dict | None = None,
) -> tuple[str, str, str, str, dict[str, object]]:
    payload = _build_formal_document_render_payload(
        report_payload=report_payload,
        output_language=output_language,
        document_kind="project_proposal",
        delivery_supplement=delivery_supplement,
    )
    filename_seed = "".join(ch for ch in payload.title if ch.isalnum() or ch in {" ", "-", "_"}) or "project-proposal"
    pdf_bytes = _build_simple_pdf(
        payload.plain_text.splitlines(),
        header=f"Anti-FOMO 正式交付 · 项目建议书 · {payload.title}",
        footer="P2 controlled export · 页 {page}/{total} · 证据锚点随正文保留",
        layout_profile="p2.6-brand-media-grid",
    )
    diagnostics = _formal_pdf_artifact_diagnostics(payload)
    diagnostics["office_roundtrip"] = validate_pdf_bytes(pdf_bytes)
    return (
        f"{filename_seed[:48].replace(' ', '_')}.pdf",
        payload.plain_text,
        b64encode(pdf_bytes).decode("ascii"),
        "application/pdf",
        diagnostics,
    )
