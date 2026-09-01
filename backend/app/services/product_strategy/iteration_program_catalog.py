from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.product_strategy.catalog import canonical_digest, effective_evidence_status, iso


ITERATION_PROGRAM_VERSION = "2.10.3-2.11.7"
PROJECT_SCOPE = "anti-fomo"
OBSERVED_AT = datetime(2026, 8, 31, tzinfo=UTC)
EXPIRES_AT = OBSERVED_AT + timedelta(days=14)
INITIALIZATION_EVENT_KEY = "anti-fomo:2.10.3-2.11.7:explicit-user-instruction"


def instruction_evidence() -> dict[str, Any]:
    return {
        "kind": "user_instruction",
        "actor_identity_status": "unverified",
        "scope": "product_strategy_iteration_program_only",
        "instruction": "继续按最新版迭代方案，完成后续15个版本的开发任务，并以竞品、验收、性能和双端发布证据持续校准。",
        "recorded_at": iso(OBSERVED_AT),
        "authorization_scope": "允许定义、实现和验证受治理的产品策略迭代控制平面；不构成外部执行、Office/视觉验收、生产发布或独立审计批准。",
        "does_not_approve_artifact_acceptance": True,
        "does_not_authorize_execution": True,
        "does_not_approve_release": True,
        "requires_human_evidence_review": True,
    }


def _agent_source(
    *,
    product_key: str,
    vendor: str,
    product_name: str,
    source_title: str,
    source_url: str,
    vendor_claim: str,
    claimed_capabilities: list[str],
    current_model_signal: str,
    lesson: str,
    anti_fomo_decision: str,
) -> dict[str, Any]:
    payload = {
        "catalog_key": f"{product_key}:official-agent-source",
        "product_key": product_key,
        "vendor": vendor,
        "product_name": product_name,
        "source_title": source_title,
        "source_url": source_url,
        "source_kind": "official_product_or_documentation",
        "vendor_claim": vendor_claim,
        "claimed_capabilities": claimed_capabilities,
        "current_model_signal": current_model_signal,
        "lesson": lesson,
        "anti_fomo_decision": anti_fomo_decision,
        "observed_at": iso(OBSERVED_AT),
        "expires_at": iso(EXPIRES_AT),
        "evidence_tier": "vendor_claim",
        "evidence_status": "vendor_claim_unverified",
    }
    return {**payload, "source_digest": canonical_digest(payload)}


AGENT_SOURCES: tuple[dict[str, Any], ...] = (
    _agent_source(
        product_key="openai_codex",
        vendor="OpenAI",
        product_name="Codex",
        source_title="OpenAI Codex 产品页",
        source_url="https://openai.com/codex/",
        vendor_claim="官方产品页将 Codex 描述为可在并行工作区和云环境中处理功能、重构、迁移、测试及持续工程任务的编码智能体。",
        claimed_capabilities=["并行代理工作流", "代码变更", "测试与评审", "后台任务"],
        current_model_signal="截至 2026-08-31，官方公开的前沿通用系列为 GPT-5.6 Sol/Terra/Luna；Codex 亦提供 GPT-5.3-Codex 专用模型。",
        lesson="复杂代理工作应把任务边界、变更、验证和交接显式化。",
        anti_fomo_decision="integrate: 采用可审查任务上下文、变更证据和交接包；不复制代码/终端自主执行。",
    ),
    _agent_source(
        product_key="anthropic_claude_code",
        vendor="Anthropic",
        product_name="Claude Code",
        source_title="Claude Code 官方入门文档",
        source_url="https://docs.anthropic.com/en/docs/claude-code/getting-started",
        vendor_claim="官方文档将 Claude Code 描述为可在开发机终端中协助阅读、修改和运行项目工作的编码代理，并提供企业平台部署路径。",
        claimed_capabilities=["终端工作流", "项目上下文", "代码修改", "企业平台部署"],
        current_model_signal="截至 2026-08-31，Anthropic 官方将 Claude Opus 5 定位为 Claude Pro 的最强模型，并强调长运行 Agent、编码和专业工作。",
        lesson="本地代理权限必须和项目目录、身份、审计与人工批准相绑定。",
        anti_fomo_decision="explicitly_not_copy: 不开放任意终端、代码或本地文件写入；仅保留提案、dry-run 和回放边界。",
    ),
    _agent_source(
        product_key="google_gemini_enterprise",
        vendor="Google Cloud",
        product_name="Gemini Enterprise Agent Platform",
        source_title="Gemini Enterprise Agent Platform 官方文档",
        source_url="https://docs.cloud.google.com/gemini-enterprise-agent-platform/agents",
        vendor_claim="官方文档描述其提供代理构建、托管运行时、身份、策略、注册表、评估、可观测性和工具访问治理。",
        claimed_capabilities=["代理身份", "工具注册", "策略治理", "评估与可观测性"],
        current_model_signal="截至 2026-08-31，Google 官方模型卡列出 Gemini 3.7 Flash（复杂 Agent 任务规模化）与 Gemini 3.1 Pro（复杂任务）等当前系列。",
        lesson="代理生命周期应包含身份、工具清单、离线评估和运行观测，而非只关注生成结果。",
        anti_fomo_decision="build: 签名技能台账、权限预览、离线评估和不可越权的发布关联。",
    ),
    _agent_source(
        product_key="microsoft_copilot_studio",
        vendor="Microsoft",
        product_name="Microsoft Copilot Studio",
        source_title="Copilot Studio 官方文档",
        source_url="https://learn.microsoft.com/microsoft-copilot-studio",
        vendor_claim="官方文档描述其可构建、测试、评估、发布和监控代理与工作流，并通过策略、连接器和审计控制治理。",
        claimed_capabilities=["低代码代理", "测试评估", "发布审批", "连接器治理与审计"],
        current_model_signal="Copilot Studio 是模型可配置的企业 Agent 平台；本次不把单一底座模型固定为产品能力结论。",
        lesson="设计应先定义数据、工具、渠道、禁止动作、评估与发布审批。",
        anti_fomo_decision="build: 以版本级验收包、工具权限预览、人工审批和审计交接加强当前差异化链路。",
    ),
    _agent_source(
        product_key="qwen_agent",
        vendor="阿里云 / Qwen",
        product_name="Qwen-Agent",
        source_title="Qwen-Agent 官方仓库与文档",
        source_url="https://github.com/QwenLM/Qwen-Agent",
        vendor_claim="官方仓库将 Qwen-Agent 描述为基于指令遵循、工具使用、规划和记忆能力构建 LLM 应用的框架，并提供浏览器、代码解释器等示例。",
        claimed_capabilities=["工具调用", "规划", "记忆", "浏览器与代码解释器示例"],
        current_model_signal="Qwen-Agent 官方仓库在 2026-02-16 记录 Qwen3.5 开源与 Agent 示例；具体部署模型需按本地任务重新评测。",
        lesson="开源工具调用框架的灵活性需要用明确的生产安全边界约束。",
        anti_fomo_decision="integrate: 保持模型可替换和工具协议兼容评估；不把未沙箱化工具示例当作生产能力。",
    ),
    _agent_source(
        product_key="coze",
        vendor="字节跳动 / 扣子",
        product_name="扣子（Coze）",
        source_title="扣子官方产品说明",
        source_url="https://docs.coze.cn/what_is_coze",
        vendor_claim="官方说明描述扣子可从自然语言需求出发，让 Agent 拆解需求、生成代码、预览并部署相关成果。",
        claimed_capabilities=["Agent 编排", "自然语言构建", "代码生成", "预览与部署"],
        current_model_signal="扣子是多模型 Agent 平台；本次只记录平台工作流，不把可选底座模型混同为扣子自身能力。",
        lesson="从构想到部署的流畅体验不能跳过来源、权限和变更审查。",
        anti_fomo_decision="explicitly_not_copy: 不将一键部署或无审查自动化引入 Anti-FOMO；构建可复核的提案和验收差异。",
    ),
    _agent_source(
        product_key="manus",
        vendor="Manus",
        product_name="Manus API / Agent",
        source_title="Manus API v2 官方文档",
        source_url="https://open.manus.ai/docs/v2/introduction",
        vendor_claim="官方文档描述其 API 可创建与管理智能体任务、编排多步骤工作流、上传文件、接收 webhook，并使用内建或自定义技能。",
        claimed_capabilities=["多步骤任务", "项目上下文", "文件与 webhook", "自定义技能"],
        current_model_signal="Manus API v2 未在本次官方来源中承诺固定单一底座模型；因此保持 unknown，不作模型强弱推断。",
        lesson="通用任务代理的价值必须伴随任务、技能、文件、回调与权限的可追溯记录。",
        anti_fomo_decision="build: 为外部结果回传和未来技能集成保留可审查上下文包；不自动触发外部动作。",
    ),
)


def _iteration(
    *,
    version: str,
    sequence: int,
    slug: str,
    title: str,
    workstream: str,
    decision: str,
    purpose: str,
    scope_boundary: str,
    dependencies: list[str],
    delivery_artifacts: list[str],
    acceptance_criteria: list[str],
    external_evidence_requirements: list[str],
    source_basis: list[str],
) -> dict[str, Any]:
    payload = {
        "iteration_key": f"{version}:{slug}",
        "project_scope": PROJECT_SCOPE,
        "version": version,
        "sequence": sequence,
        "title": title,
        "workstream": workstream,
        "decision": decision,
        "purpose": purpose,
        "scope_boundary": scope_boundary,
        "implementation_status": "planning_control_plane_implemented",
        "feature_implementation_status": "gated_or_pending_evidence",
        "external_evidence_status": "pending",
        "acceptance_status": "hold",
        "dependencies": dependencies,
        "source_basis": source_basis,
        "delivery_artifacts": delivery_artifacts,
        "acceptance_criteria": acceptance_criteria,
        "external_evidence_requirements": external_evidence_requirements,
        "can_auto_accept": False,
        "can_auto_execute": False,
        "can_auto_approve_release": False,
        "requires_human_evidence_review": True,
        "production_status": "not_authorized",
        "revision": 1,
    }
    return {**payload, "revision_digest": canonical_digest(payload)}


ITERATION_DEFINITIONS: tuple[dict[str, Any], ...] = (
    _iteration(
        version="2.10.3", sequence=1, slug="approved-execution-proposals", title="受批准的执行提案", workstream="execution_governance", decision="defer",
        purpose="把外部或本地动作先固化为可审查、可拒绝、可回放的执行提案，而不是启动自动执行。",
        scope_boundary="不调用外部系统、不写入本地文件、不运行终端命令，也不把用户指令视为执行批准。",
        dependencies=["2.10.1 决策上下文包", "2.10.2 HOLD 验收模板"],
        delivery_artifacts=["执行提案包", "权限与影响预览", "dry-run 记录", "撤销计划"],
        acceptance_criteria=["提案绑定固定上下文与来源摘要", "风险、幂等键和回滚方案在执行前可见", "无具名批准时执行状态保持 hold"],
        external_evidence_requirements=["具名授权人与执行者职责分离", "受控 dry-run", "回放和回滚证据"],
        source_basis=["2.10.0 WorkBuddy/DuMate/QClaw 决策", "OpenAI Codex", "Manus API"],
    ),
    _iteration(
        version="2.10.4", sequence=2, slug="source-change-review", title="产品策略来源变更复核", workstream="competitive_evidence", decision="build",
        purpose="把官方来源的更新时间、摘要指纹、过期和差异转为人工复核队列。",
        scope_boundary="采集到的网页变动只产生复核信号；不得覆盖人工卡片、不得自动改写路线图或发布状态。",
        dependencies=["2.10.0 竞品能力证据台账"],
        delivery_artifacts=["来源寄存器", "摘要指纹", "变更差异报告", "人工复核队列"],
        acceptance_criteria=["每条官方来源具观察时间、到期时间和摘要", "抓取失败明确为 unknown", "来源过期明确为 stale", "无自动卡片或发布变更"],
        external_evidence_requirements=["官方来源可访问性复核", "人工语义复核与决策签署"],
        source_basis=["2.10.0 官方来源台账", "Gemini Enterprise", "Microsoft Copilot Studio"],
    ),
    _iteration(
        version="2.10.5", sequence=3, slug="office-evidence-receipts", title="Office 交付物证据收据", workstream="artifact_evidence", decision="build",
        purpose="为 DOCX/PPTX 等交付物建立文件、版本、渲染和证据摘要的可复核收据。",
        scope_boundary="不把文件存在、模板生成或单元测试误称为 Office 验收；不得绕过 2.10.2 HOLD。",
        dependencies=["2.10.2 交付物验收与修订差异"],
        delivery_artifacts=["文件摘要收据", "版本血缘", "Office 检查记录", "缺失项清单"],
        acceptance_criteria=["输入、输出、版本和来源摘要可追溯", "Office 证据缺失时始终 HOLD", "未验证声明显式展示"],
        external_evidence_requirements=["真实 Office 应用处理记录", "独立复核人结果"],
        source_basis=["千问办公决策上下文包", "Microsoft Copilot Studio"],
    ),
    _iteration(
        version="2.10.6", sequence=4, slug="visual-evidence-review", title="视觉验收证据与修订差异", workstream="artifact_evidence", decision="build",
        purpose="将浏览器、移动视口和 Office 渲染视觉检查连接到有摘要的验收记录。",
        scope_boundary="浏览器截图是界面证据，不等同于物理真机、Office 渲染或人工验收；不自动转为 accepted。",
        dependencies=["2.10.5 Office 交付物证据收据"],
        delivery_artifacts=["桌面浏览器截图", "移动视口截图", "视觉检查清单", "字段级修订差异"],
        acceptance_criteria=["截图标注运行环境和时间", "视觉缺口可定位到版本和字段", "缺少人工视觉结论时保持 HOLD"],
        external_evidence_requirements=["真实 Office 渲染", "具名人工视觉复核"],
        source_basis=["2.10.2 视觉门禁", "Manus 交付物主张"],
    ),
    _iteration(
        version="2.10.7", sequence=5, slug="human-acceptance-record", title="具名人工验收记录", workstream="acceptance_governance", decision="build",
        purpose="将拒绝、退回、批准和复核范围记录为独立、人可归属的验收事件。",
        scope_boundary="匿名指令、自动测试和来源摘要都不能伪装成具名验收或发布批准。",
        dependencies=["2.10.5 Office 证据", "2.10.6 视觉证据"],
        delivery_artifacts=["验收决定记录", "复核意见", "职责分离证明", "退回修订链"],
        acceptance_criteria=["验收人与执行人角色可区分", "决定绑定同一版本摘要", "拒绝后不能被 seed 覆盖"],
        external_evidence_requirements=["实名审核/批准记录", "同摘要的独立复核"],
        source_basis=["2.10.2 HOLD 门禁", "Microsoft Copilot Studio 治理"],
    ),
    _iteration(
        version="2.10.8", sequence=6, slug="release-evidence-bridge", title="发布证据桥接", workstream="release_assurance", decision="build",
        purpose="把产品策略交付物的证据状态以只读方式关联现有 release-readiness。",
        scope_boundary="不改变 baseline_hybrid、不重写 release-readiness，且不能用产品策略完成度替代外部发布证据。",
        dependencies=["2.9.5 release-evidence closure", "2.10.7 人工验收记录"],
        delivery_artifacts=["只读发布证据链接", "门禁差距摘要", "审计交接索引"],
        acceptance_criteria=["所有链接保留前置摘要", "当前 blocked 状态仍可见", "没有自动升级生产默认"],
        external_evidence_requirements=["真实 Cross Encoder 队列", "影子运行、漂移、回滚和独立审计证据"],
        source_basis=["2.9.5 发布证据闭环", "2.10.2 HOLD 门禁"],
    ),
    _iteration(
        version="2.10.9", sequence=7, slug="agent-skill-inventory", title="Agent 技能与模型边界台账", workstream="agent_governance", decision="build",
        purpose="记录模型、技能、工具和高风险动作的范围、版本、来源和禁止动作。",
        scope_boundary="不安装、运行或授权第三方 Agent/技能；模型营销主张不构成性能或安全证明。",
        dependencies=["2.10.3 执行提案", "2.10.4 来源变更复核"],
        delivery_artifacts=["模型/技能清单", "能力与风险声明", "禁止动作清单", "版本和来源摘要"],
        acceptance_criteria=["每项标明厂商主张或本地验证等级", "技能权限最小化", "禁止项在接口和界面可见"],
        external_evidence_requirements=["供应商版本复核", "安全评审与签名/完整性证明"],
        source_basis=["Gemini Enterprise", "Qwen-Agent", "Claude Code"],
    ),
    _iteration(
        version="2.11.0", sequence=8, slug="tool-permission-dry-run", title="工具权限预览与受控 dry-run", workstream="agent_governance", decision="build",
        purpose="将工具调用限制为可预览的范围、参数、预算、幂等和回滚方案。",
        scope_boundary="无具名批准时不得执行工具、写入文件、发送消息或使用外部凭据。",
        dependencies=["2.10.3 执行提案", "2.10.9 技能台账"],
        delivery_artifacts=["工具权限预览", "dry-run 回执", "预算限制", "失败闭环"],
        acceptance_criteria=["allowlist 和参数可审查", "dry-run 不产生外部副作用", "失败默认阻断后续动作"],
        external_evidence_requirements=["受控真实环境 dry-run", "权限/身份审计"],
        source_basis=["Gemini Enterprise Agent Platform", "Microsoft Copilot Studio"],
    ),
    _iteration(
        version="2.11.1", sequence=9, slug="replay-rollback-rehearsal", title="回放与回滚演练", workstream="agent_governance", decision="build",
        purpose="为被批准的变更设计可重放事件、失败定位和可验证回滚路径。",
        scope_boundary="没有副作用隔离与回滚演练，不得把模拟回放表述为可恢复的生产执行。",
        dependencies=["2.11.0 工具权限预览"],
        delivery_artifacts=["事件回放包", "幂等键", "回滚演练报告", "异常处置记录"],
        acceptance_criteria=["回放关联上下文与版本摘要", "回滚不覆盖人工记录", "错误路径可审计"],
        external_evidence_requirements=["隔离环境演练", "独立回滚复核"],
        source_basis=["Langhub 回滚主张", "Google 代理可观测性"],
    ),
    _iteration(
        version="2.11.2", sequence=10, slug="performance-cost-evidence", title="性能与成本证据基线", workstream="quality_assurance", decision="build",
        purpose="统一记录接口延迟、前端体验、检索质量、成本假设与可复现实验条件。",
        scope_boundary="本地一次运行、模拟数据或浏览器截图不等同于生产 SLA、客户效果或模型基准结论。",
        dependencies=["2.9.5 固定检索队列", "2.11.1 回放与回滚"],
        delivery_artifacts=["性能报告", "环境指纹", "实验输入摘要", "回归阈值"],
        acceptance_criteria=["每个数字注明环境和样本", "真实模型不可用时明确标注", "指标回退可比较"],
        external_evidence_requirements=["真实 Cross Encoder 应用", "固定样本、>=30 shadow、漂移和回滚证据"],
        source_basis=["2.9.5 retrieval assurance", "Gemini/Microsoft 评估主张"],
    ),
    _iteration(
        version="2.11.3", sequence=11, slug="responsive-evidence", title="桌面浏览器与移动视口证据", workstream="quality_assurance", decision="build",
        purpose="让公开功能展示带有可重复的桌面浏览器、移动视口和性能采集说明。",
        scope_boundary="移动视口截图必须标为浏览器模拟，不得称为物理真机或原生客户端测试。",
        dependencies=["2.10.6 视觉验收证据", "2.11.2 性能基线"],
        delivery_artifacts=["截图清单", "视口元数据", "性能 JSON", "捕获操作说明"],
        acceptance_criteria=["capture 失败显式报错", "资产与代码版本可关联", "无虚构真机标签"],
        external_evidence_requirements=["需要时补充物理设备测试与人工视觉签字"],
        source_basis=["2.10.2 视觉门禁", "公开演示资产待办"],
    ),
    _iteration(
        version="2.11.4", sequence=12, slug="agent-landscape-refresh", title="国内外模型与 Agent 能力观察", workstream="competitive_evidence", decision="build",
        purpose="将国内外强模型/Agent 的官方能力、治理策略与 Anti-FOMO 差异化决策写成可刷新台账。",
        scope_boundary="厂商产品页、仓库和文档只记录为 vendor_claim；不做未经许可的基准、价格、市场份额或安全认证结论。",
        dependencies=["2.10.4 来源变更复核", "2.10.9 技能台账"],
        delivery_artifacts=["官方来源矩阵", "能力/风险/非目标对照", "差异决策", "14 天失效期"],
        acceptance_criteria=["每项有 URL、摘要、观察和到期时间", "产品优劣势区分本地实现与厂商主张", "竞品不自动生成执行或发布权限"],
        external_evidence_requirements=["持续官方来源复核", "独立性能/安全评测（如需声明）"],
        source_basis=[source["product_name"] for source in AGENT_SOURCES],
    ),
    _iteration(
        version="2.11.5", sequence=13, slug="customer-feedback-evidence", title="真实任务与反馈证据闭环", workstream="customer_validation", decision="defer",
        purpose="将真实任务、用户反馈、qrels、专家盲评和客户验证纳入可审计的产品改进输入。",
        scope_boundary="不会伪造客户、专家、反馈或业务结果；匿名示例和 fixture 不能升级为客户验证。",
        dependencies=["2.11.2 性能基线", "2.11.4 Agent 能力观察"],
        delivery_artifacts=["任务样本协议", "反馈表", "盲评包", "qrels 与改进差异"],
        acceptance_criteria=["同意、脱敏和用途边界明确", "真实/模拟数据可区分", "结论可追溯到样本"],
        external_evidence_requirements=["真实用户/客户授权", "专家盲评与 qrels", "独立审核"],
        source_basis=["2.9.5 真实证据缺口", "产品反馈闭环"],
    ),
    _iteration(
        version="2.11.6", sequence=14, slug="biweekly-competitive-monitor", title="双周竞品来源监测与复核", workstream="competitive_evidence", decision="build",
        purpose="以至少每周一次的计划任务生成来源变化、过期项和人工复核提示，满足不晚于两周一次的刷新要求。",
        scope_boundary="自动化仅获取公开官方来源并输出 artifact/issue 提示；不得自动改写竞争结论、路线图、代码或发布状态。",
        dependencies=["2.10.4 来源变更复核", "2.11.4 Agent 能力观察"],
        delivery_artifacts=["计划任务", "来源监测报告", "差异摘要", "人工复核待办"],
        acceptance_criteria=["计划至少每 7 天触发", "报告含来源、时间、摘要、错误和过期状态", "变更仅创建待复核提示"],
        external_evidence_requirements=["维护者定期审阅与来源语义判断"],
        source_basis=["竞争情报方法论", "2.11.4 官方来源矩阵"],
    ),
    _iteration(
        version="2.11.7", sequence=15, slug="independent-audit-handoff", title="独立审计交接包", workstream="release_assurance", decision="build",
        purpose="将版本、来源、验收、性能、回放、未决风险和发布门禁整理为独立审计可复核的交接包。",
        scope_boundary="交接包不是审计通过、客户验收或生产批准；所有缺失证据保留为未决项。",
        dependencies=["2.10.8 发布证据桥接", "2.11.5 真实反馈证据", "2.11.6 双周监测"],
        delivery_artifacts=["审计索引", "摘要链", "未决风险清单", "复核职责矩阵"],
        acceptance_criteria=["每项主张均可追溯", "缺失证据显式保留", "交接不改变 release gate"],
        external_evidence_requirements=["独立审核人", "受控 shadow、漂移、回滚和验收材料"],
        source_basis=["2.9.5 release evidence", "2.10.0–2.11.6 受治理交付物"],
    ),
)


def program_digest() -> str:
    return canonical_digest({"program": ITERATION_PROGRAM_VERSION, "sources": AGENT_SOURCES, "iterations": ITERATION_DEFINITIONS})


def governance() -> dict[str, Any]:
    return {
        "instruction_kind": "user_instruction",
        "actor_identity_status": "unverified",
        "scope": "product_strategy_iteration_program_only",
        "iterations_require_explicit_initialization": True,
        "vendor_claim_is_not_independent_verification": True,
        "source_change_requires_human_review": True,
        "office_and_visual_acceptance_remain_gated": True,
        "can_auto_accept": False,
        "can_auto_execute": False,
        "can_auto_approve_release": False,
        "release_gate_mutated": False,
        "production_status": "not_authorized",
        "note": "十五个版本的控制平面可本地实现和验证；实际 Agent 动作、Office/视觉验收、真实任务证据和生产发布仍必须走独立的人类复核与既有 release-evidence 门禁。",
    }


def _preview_source(source: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    row = deepcopy(source)
    recorded_status = row.pop("evidence_status")
    row["evidence"] = {
        "tier": row.pop("evidence_tier"),
        "status": effective_evidence_status(recorded_status, row["expires_at"], now=now),
        "recorded_status": recorded_status,
        "vendor_claim_is_not_independent_verification": True,
    }
    return row


def _preview_iteration(definition: dict[str, Any]) -> dict[str, Any]:
    row = deepcopy(definition)
    row["initial_field_level_diff"] = {
        "from_revision": None,
        "to_revision": row["revision"],
        "changed_fields": [{"field": key, "before": None, "after": value, "change_type": "added"} for key, value in row.items() if key not in {"revision_digest", "initial_field_level_diff"}],
        "auto_acceptance_forbidden": True,
        "release_gate_mutated": False,
    }
    return row


def iteration_definitions() -> list[dict[str, Any]]:
    return deepcopy(list(ITERATION_DEFINITIONS))


def preview_iteration_program(*, now: datetime | None = None) -> dict[str, Any]:
    return {
        "iteration_program_version": ITERATION_PROGRAM_VERSION,
        "observed_at": iso(OBSERVED_AT),
        "expires_at": iso(EXPIRES_AT),
        "program_digest": program_digest(),
        "read_only": True,
        "initialized": False,
        "persistent_snapshot_digest": None,
        "instruction_evidence": instruction_evidence(),
        "governance": governance(),
        "agent_sources": [_preview_source(source, now=now) for source in AGENT_SOURCES],
        "iterations": [_preview_iteration(definition) for definition in ITERATION_DEFINITIONS],
        "initialization_audit": None,
    }
