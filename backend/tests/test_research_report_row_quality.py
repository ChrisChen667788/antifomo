from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.research import ResearchEntityEvidenceOut, ResearchReportResponse, ResearchReportSectionOut
from app.services.llm_parser import ResearchReportResult
from app.services.research import report_row_quality
from app.services.research.report_delivery_runtime import merge_result_with_intelligence, sanitize_report_response_fields
from app.services.research.scope_entity_runtime_dependencies import scope_entity_runtime_functions


def test_row_quality_filters_budget_noise_and_keeps_actionable_rows() -> None:
    assert report_row_quality.is_actionable_budget_row("上海数据集团采购项目预算 1200 万元，7 月启动招标")
    assert not report_row_quality.is_actionable_budget_row("中国经济开局良好，同比增长 5%")
    assert not report_row_quality.is_actionable_budget_row("当前证据不足，建议补充采购公告")
    assert not report_row_quality.is_actionable_budget_row("”中国移动云能力中心计划采购部通建组组长李玉华说")


def test_summary_fact_rows_filters_guidance_and_source_artifacts() -> None:
    rows = report_row_quality.summary_fact_rows(
        [
            "上海数据集团：7 月预算复核",
            "建议补充政府采购、公共资源交易、上市公告和行业媒体对",
            "当前证据不足，待补充",
            "报告共计：公开线索 1 条，代表样本",
        ],
        limit=3,
    )

    assert rows == ["上海数据集团：7 月预算复核"]


def test_looks_like_insufficient_covers_localized_and_english_markers() -> None:
    assert report_row_quality.looks_like_insufficient("当前证据不足，待补充")
    assert report_row_quality.looks_like_insufficient("Current evidence is insufficient")
    assert not report_row_quality.looks_like_insufficient("预算窗口已经明确")


def test_structured_field_sanitizer_rejects_web_fragments_and_semantically_empty_rows() -> None:
    sanitize = scope_entity_runtime_functions().sanitize_report_field_rows

    assert sanitize(
        "tender_timeline",
        [
            "明确信息公示、异议处置、纠错救济等规则",
            "2026 年下半年启动采购意向和公开招标",
        ],
    ) == ["2026 年下半年启动采购意向和公开招标"]
    assert sanitize(
        "budget_signals",
        ["中国政府采购网 其在市政务云平台的建设成果上扩容人工智能分析能力"],
    ) == []
    assert sanitize(
        "key_people",
        [
            "副省长主任：全省一朵云正式点亮_政务_数据_服务",
            "省国资委主任：全省一朵云正式点亮",
            "李秀斌局长：公开部署数字政府建设任务",
        ],
    ) == ["李秀斌局长：公开部署数字政府建设任务"]
    assert sanitize(
        "five_year_outlook",
        [
            "构建全省首个政务智能体应用矩阵 Sep 24, 2025",
            "未来五年将从单点试点走向平台统建与持续运营",
        ],
    ) == ["未来五年将从单点试点走向平台统建与持续运营"]
    assert sanitize(
        "client_peer_moves",
        [
            "各区人民政府",
            "无锡市数据局启动政务智能体应用矩阵建设",
        ],
    ) == ["无锡市数据局启动政务智能体应用矩阵建设"]
    assert sanitize(
        "project_distribution",
        [
            "上海：公开线索 5 条，代表样本 某政策网页",
            "无锡：政务智能体应用矩阵已落地并进入场景扩展阶段",
        ],
    ) == ["无锡：政务智能体应用矩阵已落地并进入场景扩展阶段"]
    assert sanitize(
        "target_departments",
        [
            "在省数据局：全省一朵云正式点亮_政务_数据_服务",
            "数据管理/大数据管理机构与政务信息中心：高概率技术归口",
            "无锡市数据局：统筹政务智能体应用矩阵建设",
        ],
    ) == ["无锡市数据局：统筹政务智能体应用矩阵建设"]
    assert sanitize(
        "account_team_signals",
        [
            "无锡市数据局：政务智能体应用矩阵建设（Yahoo Search）",
            "省数据集团：组建政务云运营团队",
            "无锡市数据局：公开组建政务智能体场景统筹团队",
        ],
    ) == ["无锡市数据局：公开组建政务智能体场景统筹团队"]
    assert sanitize(
        "benchmark_cases",
        ["随着由无锡市数据局统筹、无锡市城运中心牵头构建的政务智能体矩阵正式落地"],
    ) == ["由无锡市数据局统筹、无锡市城运中心牵头构建的政务智能体矩阵正式落地"]
    assert sanitize(
        "five_year_outlook",
        ["根据规划，省政务云未来将持续升级并形成全省一朵云体系…"],
    ) == []


def test_structured_field_sanitizer_rejects_source_titles_and_placeholder_entities() -> None:
    sanitize = scope_entity_runtime_functions().sanitize_report_field_rows

    assert sanitize(
        "target_departments",
        [
            "中国移动云能力中心计划采购部：中国移动云能力中心积极助推长三角一体化|政务云|江浙沪_网易订阅",
            "政府办公室：江苏省人民政府 政府办公室(厅)文件 省政府办公厅关于印发数字政府规划的通知",
            "数据局或大数据管理部门：负责数据目录、共享交换和算法模型纳管",
            "政府采购中心或采购执行部门：负责采购意向与公告时点",
            "苏州市信息中心：苏州市信息中心关于苏州市级政务云数据中台项目招标公告",
        ],
    ) == []
    assert sanitize(
        "strategic_directions",
        [
            "江苏省人民政府 最新公报 省政府办公厅关于印发数字政府规划的通知",
            "规划期限为2021-2025年，展望至2035年",
            "未来重点推进政务知识库、模型治理与跨部门场景一体化建设",
        ],
    ) == ["未来重点推进政务知识库、模型治理与跨部门场景一体化建设"]
    assert sanitize(
        "five_year_outlook",
        [
            "构建全省首个政务智能体应用矩阵 AI助力政务服务温暖升级",
            "某咨询公司关于业务系统升级项目公开招标公告",
            "未来五年将从单点智能体走向平台统建与持续运营",
        ],
    ) == ["未来五年将从单点智能体走向平台统建与持续运营"]
    assert sanitize(
        "client_peer_moves",
        [
            "中共江苏省委：江苏省人民政府办公厅关于印发数字政府规划的通知",
            "山东是国内第一家省级政府：数字政府建设再迎利好 - 郑州市科技局",
            "无锡市数据局：启动政务智能体应用矩阵建设并进入跨部门试点",
        ],
    ) == ["无锡市数据局：启动政务智能体应用矩阵建设并进入跨部门试点"]
    assert sanitize("ecosystem_partners", ["浙江信镧建设工程咨询有限公司"]) == []
    assert sanitize(
        "benchmark_cases",
        [
            "由无锡市数据局统筹、无锡市城运中心牵头构建的 江苏省 首个 政务 智能 体应用矩阵正式落地",
            "由无锡市数据局统筹、无锡市城运中心牵头构建的江苏省首个政务智能体应用矩阵正式落地",
            "郑东新区落地一网统管N项智慧应用",
            "整合大模型信息，展示名称、简介、重点示范行业、算力要求和适用场景",
            "江苏省数据局 市县动态 澄之窗上线AI导服平台，打造智慧政务新标杆",
        ],
    ) == ["由无锡市数据局统筹、无锡市城运中心牵头构建的江苏省首个政务智能体应用矩阵正式落地"]
    assert sanitize(
        "flagship_products",
        [
            "上海一网通办：对应智能审、在线帮办、知识库运营和算法模型纳管场景",
            "加强一网通办平台告知承诺制事项管理，优化信用管理和批后核查",
            "推进长三角数据共享交换平台支撑区域内公共数据高效流通",
        ],
    ) == ["上海一网通办：对应智能审、在线帮办、知识库运营和算法模型纳管场景"]


def test_model_rows_are_not_overwritten_by_lower_quality_extracted_rows() -> None:
    parsed = ResearchReportResult(
        strategic_directions=["未来重点推进政务知识库、模型治理与跨部门场景一体化建设"],
    )

    merged = merge_result_with_intelligence(
        parsed,
        {
            "strategic_directions": [
                "江苏省人民政府 最新公报 省政府办公厅关于印发数字政府规划的通知"
            ]
        },
    )

    assert merged.strategic_directions == ["未来重点推进政务知识库、模型治理与跨部门场景一体化建设"]


def test_final_field_sanitization_synchronizes_sections_and_filters_rejected_links() -> None:
    valid_link = ResearchEntityEvidenceOut(
        title="无锡政务智能体应用矩阵",
        url="https://www.wuxi.gov.cn/ai",
        source_label="无锡市政府",
        source_tier="official",
    )
    invalid_link = ResearchEntityEvidenceOut(
        title="错误页面！中国政府采购网",
        url="https://www.ccgp.gov.cn/error",
        source_label="中国政府采购网",
        source_tier="official",
    )
    report = ResearchReportResponse(
        keyword="长三角政务人工智能",
        report_title="长三角政务人工智能调研",
        executive_summary="聚焦可核验的政务人工智能需求。",
        consulting_angle="用于需求分析。",
        source_count=2,
        generated_at=datetime.now(timezone.utc),
        tender_timeline=["明确信息公示、异议处置、纠错救济等规则"],
        client_peer_moves=["各区人民政府"],
        sections=[
            ResearchReportSectionOut(
                title="招标时间预测",
                items=["明确信息公示、异议处置、纠错救济等规则"],
                evidence_links=[valid_link, invalid_link],
                evidence_count=2,
                evidence_quota=1,
                meets_evidence_quota=True,
            ),
            ResearchReportSectionOut(
                title="行业资讯判断",
                items=["无锡政务智能体应用矩阵进入场景扩展阶段。"],
                evidence_links=[valid_link, invalid_link],
                evidence_count=2,
                evidence_quota=1,
                meets_evidence_quota=True,
            ),
        ],
    )

    cleaned = sanitize_report_response_fields(
        report,
        allowed_source_urls={valid_link.url},
    )

    assert cleaned.tender_timeline == []
    assert cleaned.client_peer_moves == []
    assert [section.title for section in cleaned.sections] == ["行业资讯判断"]
    assert cleaned.sections[0].evidence_links == [valid_link]
    assert cleaned.sections[0].evidence_count == 1
