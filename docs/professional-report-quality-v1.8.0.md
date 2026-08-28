# Anti-FOMO 1.8.0 专业报告编译与语义质量升级

Updated: 2026-07-13

Status: engineering implementation completed locally through `1.9.1`; release promotion remains blocked by pending real 100+30 expert calibration, three-industry blind evaluation, and customer acceptance artifacts.

## 版本决策

`1.8.0` 插队成为 `1.7.2` 之后的下一产品版本，优先级高于原计划中的
ADR 表格导出、工作坊清单和通用插件扩展。

原因不是当前报告缺少章节，而是历史样本已证明：

- 66 份历史报告中 20 份被低质量审计命中，占 30.3%。
- 弱来源覆盖、降级 readiness、临时证据模式和关键章节证据失败仍较常见。
- 旧质量评分主要检查关键词和结构，来源正文污染、无关实体或证据错配仍可能得到高分。
- 解决方案、咨询报告、项目建议书和可行性研究报告仍共用过多通用字段，缺少各自独立的推理过程和量化模型。

因此本版本先提高“可信度和决策质量”，再继续增强外观和导出形式。

## 外部能力取舍

本版本吸收方法，不整体迁移框架：

| 来源 | 吸收能力 | 不直接采用的部分 |
| --- | --- | --- |
| STORM | 多视角问题发现、先研究后大纲、引用式长文 | 百科型成文目标 |
| GPT Researcher | 规划、并行研究、发布前审查 | 替换现有检索和来源门禁 |
| Agency Agents | 专业角色契约、SCQA/金字塔结构、量化行动 | 批量导入全部角色提示词 |
| GraphRAG | 实体、关系和证据锚点 | 首版即建设重型全量图索引 |
| PPTAgent / Presenton | 可编辑 PPTX、视觉检查和反思修订 | 用视觉包装替代内容质量 |
| SkillHub word-docx | DOCX 样式、编号、分节和往返质量 | 直接信任第三方内容方法 |
| SkillHub bid-proposal-generator | 招标评分项逐条响应矩阵 | 未经评测直接安装到生产 |
| SkillHub 公文/校对类 Skill | 输入完整性、格式检查、中文校对规则 | 未审查的外部 API 和数据出境 |

第三方 Skill 仅作为公开方法来源。进入生产前必须经过许可证、外部 API、
数据安全、提示注入、效果基准和回滚审查。

## 目标流水线

```text
文档类型与需求契约
  -> 输入完整度评分与一次性追问
  -> 问题树、假设台账、利益相关方视角
  -> 并行研究计划与来源门禁
  -> 主张—证据账本
  -> 文档类型编译器
  -> 挑战者语义审查
  -> DOCX/PPTX 渲染与视觉回归
  -> 人工确认与外发
```

## 实施顺序

### P0.1 语义质量硬门禁

Status: first implementation completed locally

Scope:

- 将结构完整度与语义质量拆开评分。
- 新增内容卫生检查，识别网页导航、页脚、登录提示、来源转储和模板污染。
- 新增主张—证据可追溯性检查，识别预算、金额、比例、工期、收益等强主张。
- 没有 URL、文号、项目编号或稳定 source/chunk ID 时，不能只凭“证据矩阵”章节名称获得通过。
- 内容污染时综合分硬上限为 fail；证据不可追溯时综合分不能进入 pass。

Acceptance:

- 含网页导航的完整报告不得超过 67 分。
- 只有完整章节但没有具体证据锚点的报告不得进入 pass。
- 有完整结构、足够交付控制且强主张逐条绑定证据的样本可以进入 pass。
- 现有解决方案和正式文档调用契约保持兼容。

### P0.2 主张—证据账本

Status: completed locally

Scope:

- 增加稳定的 claim ID、claim type、claim text、confidence 和 document section。
- 每条主张绑定 source/chunk ID、URL、文件名/文号、摘录、发布日期和来源等级。
- 保存支持、冲突、仅背景相关、待核验四类关系。
- 数字、预算、采购、合规、绩效和推荐结论必须逐条绑定。
- 最终报告显示可读的证据附录，导出保留稳定锚点。

Delivered:

- 使用规范化章节、主张类型和主张文本生成稳定 `clm_*` ID；输入顺序变化不改变 ID。
- 使用规范化 URL、文号或来源标题生成稳定 `ev_*` ID，并合并同源重复锚点。
- 每条主张记录类型、置信度、实体、数字事实和
  `supports / conflicts / background / needs_validation` 证据关系。
- 账本统计总体覆盖率和高置信主张覆盖率，并单独记录冲突、背景相关和待核验数量。
- 实体检查覆盖目标客户、建议业主、建设单位、采购人和中标主体冲突，以及高置信实体无证据。
- 数字检查将亿元/万元/元统一为人民币元，将年/月/天统一为月，将百分比统一为 ratio；
  日历年份单独标记，避免把发布日期误识别为投资或工期。
- 相同章节、主体和指标的非情景化冲突数字生成稳定 `issue_*` ID，并阻断 pass。
- 解决方案 Markdown、正式可研/建议书附录和前端交付卡已显示账本摘要与一致性阻断信息。

Acceptance:

- 高置信主张证据覆盖率不低于 90% 才允许进入 pass。
- 无证据强主张必须降级为假设或阻断外发。
- 同一证据不能通过重复引用虚增覆盖率。
- 等价单位数值不产生冲突；不同口径的金额、周期和比例必须生成一致性问题。

### P0.3 语义挑战者与回归集

Status: first implementation completed locally

Scope:

- 建立网页污染、错误实体、冲突数字、范围漂移、伪精确预算和模板摘要回归样本。
- 增加实体一致性、数字口径一致性、范围一致性和反方证据检查。
- 结构分、语义分、证据分和交付分分别展示。
- 选择真实项目制作四类黄金成品，由业务专家盲评。

Delivered:

- 新增 `delivery_semantic_challenger_v1`，输出稳定 `sch_*` 问题 ID、
  状态、评分、范围漂移数、跨章节冲突数、黄金样本对齐分和修订动作。
- 语义挑战者覆盖范围漂移、跨章节实体冲突、跨章节数字冲突、无证据高置信主张、
  网页/来源污染、模板占位和黄金样本对齐不足。
- 新增脱敏真实项目型黄金样本集
  `backend/evaluation/delivery_golden_samples_v1.json`，首批覆盖政务 AI 服务中心、
  文旅 AIGC 导览、智能制造质量追溯三类项目。
- 黄金样本 loader 会根据锁定范围、目标主体、文档类型、必备范围词、禁入词和必备章节评分；
  锁定范围优先级高于正文中的漂移词，避免被错误内容反向重定向。
- 解决方案交付包、正式可研/建议书、Markdown 导出、API 类型和前端交付卡均已显示挑战者摘要。
- 发现 high 严重度挑战者问题时，交付质量综合分被限制在 fail 区间；
  watch 状态不能进入 pass。
- 新增回归测试覆盖范围漂移、跨章节实体冲突、跨章节数字冲突、无证据强主张、
  黄金样本完整性和禁入词惩罚。

Acceptance:

- 当前审计中已知噪声样本不能再次获得高分。
- 低质量标记率从 30.3% 降至不高于 10%。
- 无效报告载荷降至 0。
- 噪声实体率不高于 1%。

Open verification:

- 低质量标记率、无效载荷和噪声实体率仍需在下一次历史审计与真实生成样本上量化确认。
- 本地历史审计在旧报告集上仍为 `20/66` flagged；该结果保留为基线，P0.3 不回写历史报告。
- 四类文档的专家盲评黄金成品仍属 P1.1/P2 交付前验证项；本切片先完成离线黄金样本和自动挑战者。

### P1.1 四类文档专用编译器

Status: first implementation completed locally

Scope:

- 解决方案设计：业务目标、场景、能力架构、NFR、集成、安全、实施和验收。
- 咨询报告：问题树、假设、洞察、选项、权衡、建议、行动和影响。
- 项目建议书：立项必要性、目标、产出、实施、采购、投资、绩效和风险。
- 可行性研究报告：需求预测、方案比选、技术/组织/财务可行性、影响和敏感性。
- 每类文档拥有独立 schema、提示模板、质量规则和回归集。
- 大纲和关键假设确认后再进入长文生成。

Delivered:

- 新增 `delivery/document_compilers.py`，四类文档分别使用独立 compiler：
  `solution_design_compiler_v1`、`consulting_report_compiler_v1`、
  `project_proposal_compiler_v1`、`feasibility_study_compiler_v1`。
- 新增结构化 compiled document DTO，包含文档类型、受众、用途、证据口径、章节、
  全局假设、验证动作、质量门槛和 Markdown。
- 解决方案设计 compiler 覆盖业务目标、客户场景、能力架构、数据/模型/接口、
  NFR、安全合规、实施验收和证据风险。
- 咨询报告 compiler 覆盖 SCQA、问题树、假设台账、洞察与反方观点、
  战略选项、权衡矩阵、推荐路径和 30/60/90 天行动。
- 项目建议书 compiler 覆盖立项必要性、建设目标、产出、实施采购、
  投资绩效、运营风险和证据矩阵。
- 可行性研究报告 compiler 覆盖需求预测、方案比选、技术/组织/财务可行性、
  CAPEX/OPEX/TCO、收益测算、敏感性分析、影响评价和附件清单。
- 旧的 `feasibility_outline`、`project_proposal_outline` 和正式 Word/PDF 导出已改为由
  对应专用 compiler 适配生成；人工补充信息保留在“人工输入与交叉验证说明”章节。
- 解决方案交付包 API、Markdown 导出、前端交付卡和 TypeScript contract 已显示
  `compiled_documents` 与四类 compiler 摘要。
- 新增回归测试证明四类文档不是同一模板换标题，并验证 legacy outline/formal export 适配。

Acceptance:

- 不再通过同一通用报告字段简单换标题生成四类文档。
- 输入不足时只追问一次关键缺口，随后明确降级。
- 每类文档至少有一份专家认可的黄金样本。

Open verification:

- 专家认可的四类黄金成品仍需用真实业务主题生成并盲评。
- 输入不足时“一次性追问”的交互层还未独立产品化；当前首版通过假设台账和验证动作显式降级。
- 本地 P1.1 全量检查通过：ESLint、前端 `16/16`、Next production build、后端 `328/328`。
- 本地历史审计在旧报告集上仍为 `20/66` flagged；P1.1 不回写历史报告。

### P1.2 量化决策模型

Status: first implementation completed locally

Scope:

- 建立维持现状、分期试点、整体建设等备选方案的加权比选矩阵。
- 可研增加 CAPEX、OPEX、TCO、收益、NPV、IRR、回收期和敏感性分析。
- 数据不足时输出假设表和待补数据，不生成伪精确财务数字。
- 项目建议书和投标材料增加评分项—章节—证据—责任人响应矩阵。

Delivered:

- 新增 `delivery/quantitative_models.py` 和 `delivery_quantitative_decision_model_v1`。
- 交付包新增结构化 `quantitative_decision_model`，包含：
  - 维持现状、分期试点、整体建设三类备选方案；
  - 战略匹配、证据支撑、实施复杂度、投资压力、交付风险、价值潜力和可扩展性加权评分；
  - 投标评分项—章节—证据—责任人—验证动作响应矩阵；
  - 保守、基准、乐观三情景 CAPEX/OPEX/TCO/收益/NPV/IRR/ROI/回收期；
  - CAPEX、年度 OPEX 比例、年度收益比例和折现率敏感性变量。
- 数据不足时财务三情景保留为待补，不输出伪精确 CAPEX/NPV/IRR/ROI。
- 解决方案交付包 Markdown、正式可研/项目建议书 Word/PDF 附录、API contract 和前端交付卡已展示量化模型摘要。
- 新增 P1.2 回归测试覆盖有预算金额、无预算金额、formal export 附录和 runtime pack 集成。

Acceptance:

- 数据充分的可研 100% 输出基准、乐观、悲观三情景。
- 每个投标评分项可追溯到章节、证据和负责人。
- 所有测算可以复算，并显示单位、期间、税费和折现率口径。

Open verification:

- 当前财务模型以公开预算/同类招采金额中位数作为 CAPEX 基准；真实项目仍需财务负责人确认税费、付款节奏、残值、收益归因和折现率。
- IRR 为三年现金流内部测算，缺少正负现金流或输入不足时会留空。
- P1.2 targeted 测试已本地通过 `19/19`。
- 本地 P1.2 全量检查通过：ESLint、前端 `16/16`、Next production build、后端 `332/332`。
- 本地历史审计在旧报告集上仍为 `20/66` flagged，输出
  `/tmp/af-quality-audit-v180-p12.json` 和 `/tmp/af-quality-audit-v180-p12.md`；P1.2 不回写历史报告。

P2 启动前增加一个真实业务主题验证门：不是再造更多模板，而是确认 P0.3/P1.1/P1.2
在真实公开政策和行业场景下不会产生伪招采、伪金额或跨行业漂移。

### P1.3 真实业务主题黄金样本验证

Status: first implementation completed locally

Scope:

- 以 3 个 2026 年真实业务主题验证交付链路：
  - 上海市医疗行业 AI 需求调研和潜在商机；
  - 上海市文旅行业 AI 需求调研和潜在商机；
  - 长三角政府行业 AI 需求调研和潜在商机。
- 每个主题必须绑定公开 HTTPS 来源，优先使用政府、主管部门和一手政策/通知来源。
- 政策/试点来源不能被误判成招标或中标项目。
- 公开来源未披露项目金额时，P1.2 财务模型必须保持 `assumption_required`，不得编造
  CAPEX、NPV、IRR、ROI。
- 三个主题必须能生成解决方案设计、咨询报告、项目建议书、可行性研究报告四类编译结果。

Delivered:

- 新增 `backend/evaluation/real_business_delivery_golden_v1.json`，
  dataset ID 为 `anti-fomo-real-business-delivery-golden-v1`，状态为
  `draft_for_blind_review`。
- 在 `backend/evaluation/delivery_golden_samples_v1.json` 注册 3 个真实业务语义样本：
  `shanghai-medical-ai-2026`、`shanghai-culture-tourism-ai-2026`、
  `yangtze-delta-gov-ai-2026`。
- 新增 `real_business_golden_samples.py` loader 和 deterministic 报告构造器，避免验证依赖
  付费模型调用。
- 收紧 market intelligence 来源分类：公开政策、试点通知和媒体报道不再自动生成伪招采项目；
  无真实招采时，交付材料文案切换为“公开政策/试点参考”和“机会准备”。
- 收紧语义挑战者行业词，降低“客服机器人”“数据治理”等通用表述误触电商、制造或政务范围漂移。
- 新增真实业务黄金样本回归测试，覆盖来源完整性、政策来源不伪造招采、四类文档编译、
  P1.2 缺金额降级、P0.3 黄金样本匹配和高严重度问题拦截。

Open verification:

- Targeted 测试已本地通过 `14/14`。
- 本地 P1.3 全量检查通过：ESLint、前端 `16/16`、Next production build、后端 `335/335`。
- 本地历史审计在旧报告集上仍为 `20/66` flagged，输出
  `/tmp/af-quality-audit-v180-real-golden.json` 和
  `/tmp/af-quality-audit-v180-real-golden.md`；P1.3 不回写历史报告。
- `git diff --check` 通过。
- 三个样本当前可作为 P2 回归门禁，但仍是 `draft_for_blind_review`；
  客户级黄金成品还需要人工补强逐条证据锚点并做专家盲评。
- 由于公开来源没有披露具体预算，三类主题的财务模型不能作为客户报价或投资测算直接外发。

### P2 正式交付工程

Status: P2.7 completed locally

Scope:

- 建立受控 DOCX 样式、标题编号、表格、分节、页眉页脚和分页规则。
- 建立 Word/PDF 往返和截图视觉回归。
- 增加中文术语、数字、标点、公文格式和一致性校对。
- 引入 PPTX 生成—视觉检查—反思修订闭环，输出保持可编辑。

Delivered:

- 新增 P2.1 正式文档渲染控制切片，先覆盖可行性研究报告和项目建议书的
  Word 兼容 HTML `.doc` 与简易 PDF 预览，不改变现有任务 API。
- Word 兼容 HTML 增加受控 A4 页面 CSS、元信息表、目录表、章节内容表、
  交付版式控制清单、页眉、页脚和 PDF/Word 往返校验清单。
- 正式导出章节统一经 `_number_formal_document_sections` 编号：
  主章节使用中文序号，人工输入、质量门槛、主张—证据、语义挑战者和量化模型等补充材料进入
  `附录A/B/C`。
- 保留旧标题别名和 `data-plain="标签：值"`，保证历史导出断言、全文检索和后续往返校验能继续定位
  “目标客户：...” 与 “附：量化决策模型摘要”等关键文本。
- 简易 PDF 渲染器新增可选页眉/页脚参数，正式可研/项目建议书 PDF 预览逐页写入
  `Anti-FOMO 正式交付` 页眉和 `P2 controlled export` 页脚。
- 新增 `backend/tests/test_formal_document_rendering.py`，锁定受控版式、编号去重、表格、
  页眉页脚、PDF preview 和 PDF 文件头。
- 新增 P2.2 原生文件与校对切片：
  - 使用标准库 zip/XML 生成原生 DOCX，不新增第三方运行依赖；
  - 可研和项目建议书 Word 任务现在输出 `.docx`、Office OpenXML MIME 和 `content_base64`，
    同时保留 HTML 预览内容供前端查看；
  - PDF 任务复用同一份 formal render payload，并返回往返清单、视觉指纹和中文校对诊断；
  - 新增中文校对器，覆盖中文语境半角标点、重复标点、长数字缺单位、中文词间空格、
    括号不闭合、绝对化承诺和“待核验但无责任/验证动作”等确定性问题；
  - 新增可编辑 PPTX 导出任务 `export_research_solution_delivery_pptx`、API/WorkBuddy 类型、
    前端按钮和 OpenXML 文本框输出；
  - DOCX/PDF/PPTX 运行时诊断均带 `visual_regression.fingerprint` 和 required markers，
    用于后续截图/文件往返回归定位；
  - 已刷新 `npm run repo:screenshots` 的 30 张 light/dark 产品截图基线和 manifest。
- 新增 P2.3 真实 Office 往返与专业模板切片：
  - DOCX 模板升级为 P2.3 专业交付模板，包含封面区、交付摘要看板、项目元信息、
    Word 可更新 TOC 域、图表/图片排版占位、正文表格、中文校对清单和往返清单；
  - DOCX 写入 `word/settings.xml` 并开启 updateFields，方便在 Word 中刷新目录；
  - PPTX 增加 `ppt/theme/theme1.xml`、专业色板、关键结论卡、证据/假设卡、图表占位、
    图片占位和可编辑文本框；
  - 新增 `office_roundtrip.py`，检测 LibreOffice CLI、macOS QuickLook、Microsoft Word
    和 PowerPoint，可验证 DOCX/PPTX OpenXML zip、XML well-formed、必备 part 和关键文本；
  - 新增 `scripts/validate_office_roundtrip.py` 与 `npm run office:roundtrip`，
    默认只做非 GUI 结构校验；`--quicklook` 可生成 macOS 缩略图；`--open-gui`
    需显式传入才会打开 Word/PowerPoint/Preview；
  - PDF 诊断新增 `professional_pdf_layout` 与 PDF 结构检查，确认 `%PDF-1.4`、EOF 和页数。
- 新增 P2.4 客户品牌、真实图表资产和图片资源切片：
  - `delivery_supplement` 支持结构化 `brand_template`、`chart_assets`、`image_assets`
    和 `renderer_strategy`，不改变既有任务 API；
  - 正式 render payload 会归一化客户品牌模板、真实数据图表、可替换图片资源和 headless
    转换策略；没有结构化输入时，会从预算信号、来源数量、证据密度、来源质量、客户、
    场景和实施窗口派生默认资产清单；
  - DOCX 写入 `P2.4 可替换资产清单`、`客户品牌模板`、`真实数据图表`、
    `可替换图片资源`、品牌色、Logo 文案、保密标识、来源/单位/期间/替换槽和数据摘要；
  - PPTX 写入客户命名主题、品牌色、可编辑品牌标签、图表/图片资产卡，并保留
    `Anti-FOMO P2.3 editable PPTX template` 兼容 marker；
  - HTML/PDF/plaintext 预览和 diagnostics 增加 P2.4 required markers、品牌元数据、
    可替换资产数量/标题和 `headless_conversion_strategy`；
  - headless 转换策略已定为：不自动安装 LibreOffice、不自动启动 GUI Office；默认继续使用
    in-repo controlled preview + OpenXML/PDF 结构校验，LibreOffice headless 或真实
    Word/PowerPoint 打开作为显式外发前门禁。
- 新增 P2.5 真实打开验证门禁、复杂样式模板和原生可编辑图表切片：
  - `office_roundtrip.py` 增加 `headless_conversion`、`real_open_validation_gate`、
    `complex_template_parts`、`native_chart_parts`、`embedded_workbooks`、
    `native_editable_charts` 和 PDF `professional_layout_checks`；
  - `scripts/validate_office_roundtrip.py` 增加 `--libreoffice-convert` 和
    `--manifest-out`，可在显式执行时输出 DOCX/PPTX/PDF roundtrip manifest；
  - DOCX 写入 `word/theme/theme1.xml`、`word/numbering.xml`、theme/numbering
    relationships、多级清单和 `AFBrandBand`/`AFChecklist`/`AFSmallNote` 等复杂样式；
  - DOCX 正文增加 `P2.5 复杂样式模板与真实打开验证门禁` 可见章节；
  - PPTX 写入 `ppt/charts/chart1.xml`、`ppt/charts/_rels/chart1.xml.rels`、
    `ppt/embeddings/chart-data.xlsx`，并在 slide rels 中以 `rIdChart1` 引用；
  - PPTX slide 中新增 native chart graphic frame `P2.5 Native Editable Chart`，
    图表数据来自 `chart_assets.data_rows`，并同步写入嵌入 workbook；
  - diagnostics 暴露 `complex_style_template`、`office_validation_gate`、
    `native_editable_charts`、`native_chart_parts`、`embedded_workbooks` 和 P2.5
    visual-regression artifact expectations。
- 新增 P2.6 生产级 PDF/图片排版、原生图片嵌入和历史样本 artifact 基线切片：
  - DOCX 写入 `word/media/image1.png`，并通过 `word/_rels/document.xml.rels`
    的 `rIdImage1` 和正文 DrawingML `原生图片嵌入` 标记引用；
  - PPTX 写入 `ppt/media/image1.png`，并通过 slide rels `rIdImage1` 和
    picture shape `原生图片嵌入` 标记引用；
  - `office_roundtrip.py` 增加 `native_image_parts`、`native_images`、
    PDF `has_vector_layout` 和 `vector_brand_frame_present` 检查；
  - 受控 PDF 预览升级为 `p2.6-brand-media-grid` 布局 profile，注入矢量页眉带、
    页面框、品牌侧边栏和横向 guide rails；
  - 新增 `scripts/generate_formal_artifact_visual_baseline.py` 与
    `npm run office:visual-baseline`，可对 3 个真实业务黄金样本批量生成
    DOCX/PPTX/PDF artifact、结构校验、raw/normalized hash、visual fingerprint
    和可选 PDF QuickLook 缩略图 hash；
  - baseline manifest 的 `normalized_sha256` 会忽略 OpenXML zip metadata 和
    core created/modified 时间，避免同内容 artifact 因打包时间戳产生假回归。
- 新增 P2.7 PDF 原生图片对象、LibreOffice 可配置路径和 GUI 视觉门禁切片：
  - 受控 PDF renderer 写入 native PDF Image XObject `/Im1`，包含
    `/Subtype /Image`、`/ColorSpace /DeviceRGB`、`/Filter /FlateDecode`，并绘制到
    `p2.6-brand-media-grid` media slot；
  - PDF 校验新增 `has_native_image` 与 `native_pdf_image_present`；
  - formal PDF diagnostics 升级为
    `professional_pdf_layout_version=p2.7-vector-brand-media-image-preview`，
    并暴露 `native_pdf_image_embedding=p2.7-pdf-image-xobject`；
  - LibreOffice 检测新增 `ANTI_FOMO_LIBREOFFICE_CLI`、`LIBREOFFICE_CLI`、
    `SOFFICE_PATH`、`/Applications/LibreOffice.app/Contents/MacOS/soffice` 和常见
    Homebrew symlink 路径；
  - Homebrew LibreOffice 安装已尝试，但当前机器网络在 Homebrew API/GitHub clone
    阶段失败，自动 Office→PDF headless 转换仍需先修复环境或手动配置 `soffice`。

Open verification:

- P2.1 targeted 测试已本地通过 `14/14`。
- 本地 P2.1 全量检查通过：ESLint、前端 `16/16`、Next production build、后端 `337/337`。
- 本地历史审计在旧报告集上仍为 `20/66` flagged，输出
  `/tmp/af-quality-audit-v180-p21.json` 和 `/tmp/af-quality-audit-v180-p21.md`；P2.1 不回写历史报告。
- P2.2 targeted 测试已本地通过 `18/18`。
- 本地 P2.2 全量检查通过：ESLint、前端 `16/16`、Next production build、后端 `341/341`。
- P2.2 截图回归通过 `npm run repo:screenshots`，刷新 30 张 light/dark 生产截图。
- 本地历史审计在旧报告集上仍为 `20/66` flagged，输出
  `/tmp/af-quality-audit-v180-p22.json` 和 `/tmp/af-quality-audit-v180-p22.md`；P2.2 不回写历史报告。
- P2.3 targeted 测试已本地通过 `20/20`。
- 本地 P2.3 全量检查通过：ESLint、前端 `16/16`、Next production build、后端 `343/343`。
- 本机能力检测：未检测到 LibreOffice CLI；检测到 `/usr/bin/qlmanage`、
  `/Applications/Microsoft Word.app` 和 `/Applications/Microsoft PowerPoint.app`。
- P2.3 临时样件写入 `/tmp/af-p23-office`，`scripts/validate_office_roundtrip.py`
  对 DOCX/PDF/PPTX 结构校验通过；PDF QuickLook 缩略图校验通过。
- PPTX QuickLook 缩略图在本机超过 60 秒未返回，已改为脚本级 timeout，并作为外部渲染超时记录；
  真实 PowerPoint GUI 打开验证保留给显式 `--open-gui` 或人工外发前门禁。
- 本地历史审计在旧报告集上仍为 `20/66` flagged，输出
  `/tmp/af-quality-audit-v180-p23.json` 和 `/tmp/af-quality-audit-v180-p23.md`；P2.3 不回写历史报告。
- `git diff --check` 通过。
- P2.4 targeted affected 测试已本地通过 `25/25`：
  `backend/tests/test_formal_document_rendering.py`、
  `backend/tests/test_research_solution_delivery_exports.py`、
  `backend/tests/test_daily_brief_and_extended_tasks.py`、
  `backend/tests/test_delivery_quantitative_models.py`、
  `backend/tests/test_delivery_document_compilers.py`。
- 本地 P2.4 全量 `npm run check` 通过：ESLint、前端 `16/16`、Next production build、
  后端 `345/345`。
- P2.5 targeted affected 测试已本地通过 `25/25`：
  `backend/tests/test_formal_document_rendering.py`、
  `backend/tests/test_research_solution_delivery_exports.py`、
  `backend/tests/test_daily_brief_and_extended_tasks.py`、
  `backend/tests/test_delivery_quantitative_models.py`、
  `backend/tests/test_delivery_document_compilers.py`。
- P2.5 样件写入 `/tmp/af-p25-office`，`npm run office:roundtrip -- ... --libreoffice-convert
  --manifest-out /tmp/af-p25-office/roundtrip-manifest.json` 通过；本机未安装 LibreOffice CLI，
  因此转换项记录为 `skip_no_libreoffice`。
- PDF QuickLook 视觉烟测通过，写入 `/tmp/af-p25-office/pdf-quicklook-manifest.json`
  和 `/tmp/af-p25-office/quicklook` 缩略图；manifest 现在记录缩略图 `sha256`，
  可作为后续视觉回归基线。
- 显式 GUI 打开门禁通过：`npm run office:roundtrip -- /tmp/af-p25-office/*.docx
  /tmp/af-p25-office/*.pptx /tmp/af-p25-office/*.pdf --open-gui --manifest-out
  /tmp/af-p25-office/gui-open-manifest.json` 成功启动 Microsoft Word、Microsoft
  PowerPoint 和 Preview。该结果只证明应用成功打开，最终视觉正确性仍需人工查看窗口确认。
- 本地 P2.5 全量 `npm run check` 通过：ESLint、前端 `16/16`、Next production build、
  后端 `345/345`。
- P2.6 targeted affected 测试已本地通过 `28/28`：
  `backend/tests/test_formal_document_rendering.py`、
  `backend/tests/test_research_solution_delivery_exports.py`、
  `backend/tests/test_daily_brief_and_extended_tasks.py`、
  `backend/tests/test_delivery_quantitative_models.py`、
  `backend/tests/test_delivery_document_compilers.py`、
  `backend/tests/test_real_business_delivery_golden_samples.py`。
- P2.6 历史样本 artifact baseline 写入
  `/tmp/af-p26-real-business-baseline/visual-baseline-manifest.json`：
  3 个真实业务样本、9 个 artifact、`failed_validation_count=0`、
  `failed_quicklook_count=0`；PDF QuickLook scope 通过并写入缩略图 hash。
- P2.6 独立 roundtrip manifest 写入
  `/tmp/af-p26-real-business-baseline/roundtrip-manifest.json`：
  DOCX/PPTX 均识别 `native_images=True`，PPTX 均识别
  `native_editable_charts=True`，PDF 均识别 `has_vector_layout=True`；
  本机未安装 LibreOffice CLI，因此转换项仍为 `skip_no_libreoffice`。
- P2.7 `backend/tests/test_formal_document_rendering.py` 已本地通过 `10/10`。
- P2.7 历史样本 artifact baseline 写入
  `/tmp/af-p27-real-business-baseline/visual-baseline-manifest.json`：
  3 个真实业务样本、9 个 artifact、`failed_validation_count=0`、
  `failed_quicklook_count=0`；PDF 均识别 `has_vector_layout=True` 与
  `has_native_image=True`。
- P2.7 独立 roundtrip manifest 写入
  `/tmp/af-p27-real-business-baseline/roundtrip-manifest.json`：
  DOCX/PPTX 均识别 `native_images=True`，PPTX 均识别
  `native_editable_charts=True`，PDF 均识别 `has_vector_layout=True` 与
  `has_native_image=True`；本机仍未安装 LibreOffice CLI，因此转换项为
  `skip_no_libreoffice`。
- P2.7 代表性 GUI 打开门禁写入
  `/tmp/af-p27-real-business-baseline/gui-open-manifest.json`：
  `shanghai-medical-ai-2026` 的 DOCX/PPTX/PDF 分别成功启动 Microsoft Word、
  Microsoft PowerPoint 和 Preview；该结果仍只证明打开成功，主观视觉 polish 需人工查看。
- 当前 DOCX/PPTX 已具备客户品牌模板、真实数据图表资产清单、可替换图片资源、复杂样式模板、
  原生可编辑 PPTX 图表对象、嵌入 workbook、原生图片 media part、可编辑文本、
  本机结构校验和显式 GUI 启动门禁；下一步仍需人工视觉确认窗口内容，或安装 LibreOffice CLI
  后跑 headless PDF 转换。
- 当前 PDF 已具备受控矢量品牌框架和 media-grid guide rails，但仍不是复杂桌面排版引擎；
  若要达到客户级复杂排版，应继续接入 LibreOffice/headless Chromium/受控渲染服务，
  并用真实 Word/PowerPoint/Preview 打开确认。

Acceptance:

- DOCX/PDF 往返后章节、编号、表格和证据锚点不丢失。
- PPTX 页面溢出为 0，专家盲评平均不低于 4/5。
- 外部校对服务保持可选，默认不上传敏感项目材料。

### P3 内部 Skill 治理

Scope:

- 建立版本化内部 Skill 注册表和渐进加载机制。
- 记录负责人、许可证、数据边界、依赖、基准、适用文档和回滚方式。
- 第三方 Skill 先转化为内部测试包，再决定是否进入生产。

Acceptance:

- 未评测 Skill 不进入默认生成链路。
- 每个生产 Skill 有固定回归集和版本变更记录。
- 外部 API、密钥和数据出境状态在设置和运行诊断中可见。

## 版本验收指标

| 指标 | 当前基线 | 1.8.0 目标 |
| --- | ---: | ---: |
| 历史低质量标记率 | 30.3% | ≤10% |
| 无效报告载荷 | 6.1% | 0 |
| 高置信主张证据覆盖 | 未稳定统计 | ≥90% |
| 噪声实体率 | 存在已知样本 | ≤1% |
| 无证据结构高分 | 可出现 96/100 | 0 |
| 数据充分的可研三情景覆盖 | 未稳定提供 | 100% |
| 投标评分项响应可追溯 | 未提供 | 100% |

## 发布边界

- `1.8.0` 开发不触发付费全量模型评测。
- LangGraph 仍是默认工作流，deterministic 必须保持可回滚。
- P0 质量规则优先使用确定性检查，模型挑战者作为后续可选增强。
- 当前未提交的主题、微信采集、评测治理和报告质量改动必须保留。
- 未经明确要求，不提交、不打 tag、不推送 GitHub 或 ModelScope。

## 2026-07-13 外部调研结论与后续质量路线

### 结论

当前主要矛盾不是“模型参数还不够强”，而是研究链路允许低相关证据进入、允许证据不足时继续长文生成，且总分可以掩盖主题错位等致命错误。继续叠加模板、反思轮次或统一切换到更强模型，只会让错误内容更完整、更像专业交付物。

后续迭代应先完成以下闭环：

1. 先把用户问题拆成可验证子问题，并把检索预算分配到每个子问题。
2. 每条来源必须同时通过主题锚点、语义相关性和可支持主张检查，不能仅凭“AI”“模型”等通用词判为严格匹配。
3. 先形成原子主张和证据账本，再写章节；引用与主张同时生成，禁止成文后补引用。
4. 证据不足、检索降级或主题冲突时停止生成正式研报和解决方案，只输出证据缺口说明。
5. 解决方案设计从“章节齐全”升级为“质量属性场景、备选方案、权衡、决策和验证证据齐全”。
6. 自动评分只能辅助，必须用真实失败集和专家盲评校准；任一硬门禁失败时，总分不得把结果抬回可交付状态。

### 本地最新失败样本

2026-07-13 抽查 `backend/anti_fomo_demo.db` 中最新成功任务 `ba0ea2a443eb4ba4af8b63d99a962210`：

- 用户问题是“2026年下半年上海医疗行业AI潜在需求行业调研及商机情报分析”，生成标题却变成“长三角｜生成式AI｜编程工具竞争格局”。
- 最终仅保留 2 条与 Codex/OpenAI 相关的二手来源，官方来源为 0，但诊断仍记录 `strict_match_ratio=1.0`。
- `accepted/ambiguous/rejected` 三类来源计数均为 0，说明来源分类结果没有真正约束最终保留集合。
- 公网扩展触发后新增来源为 0，reranker 处于 fallback/degraded，流水线仍继续生成完整研报与解决方案包。
- 研报就绪度为 `needs_evidence / 38`、质量分仍为 `54`；下游架构包继续围绕编程工具生成，架构就绪度 `64 / blocked`。
- 历史索引还召回了跨行业旧报告，行业方法路由将医疗问题误判为 `compute_llm`，形成“检索污染 -> 研报跑题 -> 方案跑题”的级联错误。

该样本将作为后续版本的首个硬负例。修复验收不是让它获得更高分，而是让错误来源被拒绝，并在证据不足时可靠停止。

### 可借鉴的权威方法

| 方法 | 可借鉴点 | 在 Anti-FOMO 中的落地 |
| --- | --- | --- |
| [STORM](https://aclanthology.org/2024.naacl-long.347/) | 多视角提问、检索前写作计划、可信来源组织 | 保留现有多视角规划，但补子问题覆盖门禁 |
| [IRCoT](https://aclanthology.org/2023.acl-long.557/) 与 [Self-RAG](https://proceedings.iclr.cc/paper_files/paper/2024/file/25f7be9694d7b32d5cc670927b8091e1-Paper-Conference.pdf) | 推理与检索交替，按需要检索和自我批判，而非固定一次检索 | 对证据缺口、冲突和新实体触发定向补检 |
| [CRAG](https://arxiv.org/abs/2401.15884) | 先判断检索质量，再决定接受、纠错或扩大搜索 | 将现有 retrieval correction 改为真正的 fail-closed 状态机 |
| [Query Decomposition](https://aclanthology.org/2025.acl-srw.32/) | 分解复杂问题、逐题检索、合并后重排 | 建立 question tree、每题来源配额和覆盖率 |
| [ALCE](https://aclanthology.org/2023.emnlp-main.398/) | 分开评价流畅度、正确性和引用质量 | 不再用单一专业分代替引用完整性和正确性 |
| [RAGChecker](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract-Datasets_and_Benchmarks_Track.html) 与 [RAGAS](https://aclanthology.org/2024.eacl-demo.16/) | 分离检索器与生成器问题，提供细粒度诊断 | 分别记录检索相关性、覆盖、忠实度和生成质量 |
| [CiteEval](https://aclanthology.org/2025.acl-long.1574/) | 引用判断要结合问题、上下文和生成文本，不能只做局部 NLI | 在主张级评审中加入查询意图和上下文 |
| [DEER](https://arxiv.org/abs/2512.17776) 与 [DeepResearch Bench](https://arxiv.org/abs/2506.11763) | 全文主张检查、多维 rubric、专家标准和有效引用评估 | 建立文档类型/行业 rubric，并用专家样本校准自动裁判 |
| [SEI QAW](https://www.sei.cmu.edu/library/quality-attribute-workshops-qaws-third-edition/) 与 [ATAM](https://www.sei.cmu.edu/library/the-architecture-tradeoff-analysis-method/) | 用质量属性场景驱动架构，并显式识别风险、敏感点和权衡点 | 重构方案生成器的输入、备选方案比较和评审输出 |
| [C4 Model](https://c4model.com/diagrams) | 用上下文、容器、组件、动态和部署视图服务不同受众 | 生成可追溯的多层架构视图，不再只输出一张泛化框图 |
| [AWS Well-Architected](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)、[Azure Well-Architected](https://learn.microsoft.com/en-us/azure/well-architected/pillars) 与 [Google Cloud Well-Architected](https://docs.cloud.google.com/architecture/framework) | 按可靠性、安全、成本、性能和运维等维度审视取舍 | 形成云无关的质量属性检查矩阵，再映射具体云产品 |
| [NIST AI RMF GenAI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) | 将可信、评估、治理和生命周期风险纳入生成式 AI 方案 | 增加数据、模型、内容、供应链、人工复核和监控控制项 |

### 1.8.2：真实研究数据绑定与主题硬门禁

Implementation status (2026-07-13): complete in the local default workflow. Scope contracts, source admissions, minimum evidence, archive/index isolation, domain methodology routing, evidence-gap output, score caps, API/UI diagnostics, and the known medical hard-negative regression are implemented. Statistical promotion evidence based on independently reviewed cases remains pending and is not inferred from deterministic fixtures.

Goal: 先保证检索证据确实回答用户问题，再允许研报和方案生成。

Scope:

- 新增独立的 `research_scope_contract`，固化行业、地区、时间、对象、任务类型、排除项和允许的比较范围。
- 行业/方法路由改为“结构化分类 + 主题锚点 + 置信度”，医疗问题不得因通用 AI 词被路由到 `compute_llm`。
- 每条候选来源必须绑定至少一个子问题，并记录 `accepted / ambiguous / rejected`、原因、相关性、来源类型和独立域。
- 使用 cross-encoder/reranker 或等价语义判断做第二阶段筛选；深度模式下 reranker 降级必须显式阻断，不得静默回退后继续正式交付。
- 为向量/历史报告索引增加 scope namespace 和交叉行业准入规则，默认禁止无关历史报告污染当前任务。
- 定义可配置的最低证据包。行业研报默认至少 8 条有效来源、5 个独立域、3 条一手/官方来源；不足时输出 `evidence_gap_brief`，不生成正式研报或解决方案。
- 解决方案生成增加前置依赖：研究状态不是 `evidence_ready` 时，只返回阻断原因和补证动作。

Acceptance:

- 最新医疗硬负例中的 2 条 Codex/OpenAI 来源均被拒绝，任务进入 `blocked_topic_mismatch` 或 `evidence_gap`，不再产生客户版研报和方案包。
- 基于人工标注的 100 条候选来源，主题准入 precision 不低于 95%，严重跨行业泄漏为 0，整体泄漏率不高于 1%。
- 任一保留来源都可追溯到分类结果和至少一个子问题；三类来源计数之和必须等于候选来源总数。
- 公网扩展新增 0 条、reranker 不可用、官方来源为 0 或独立域不足时，状态与原因在 API、UI、diagnostics 和 release readiness 中一致可见。

### 1.8.3：主张级迭代研究与引用完整性

Implementation status (2026-07-13): complete in the local default workflow. The six-axis question tree, bounded corrective retrieval, atomic claim ledger, citation gate, fail-closed solution delivery, Markdown/API/UI traceability, and deterministic release-readiness regression are implemented. Formal promotion still depends on the real independent-review artifact.

Goal: 把“先写文章再找证据”改为“问题树 -> 证据 -> 原子主张 -> 章节”的可审计流程。

Scope:

- 在现有多视角规划上生成 question tree，定义每个一级问题的成功条件、来源偏好和检索预算。
- 逐子问题执行检索、覆盖评估和纠错；对空白、冲突、新实体和低置信主张定向补检，支持分支与回退。
- 升级现有 claim-evidence ledger：主张起草时即绑定支持证据、反证、来源独立性、时效和适用范围。
- 将数字、机构、时间、因果、比较、预测和建议拆成原子主张；一个引用不得用来装饰多个未被支持的断言。
- 增加反证搜索和冲突仲裁。无法消解的冲突必须进入正文限制项，不能由模型静默选边。
- 章节生成只能读取已通过门禁的主张账本，禁止直接读取未过滤网页块或跨 scope 历史摘要。

Acceptance:

- 关键主张证据覆盖率 100%，全部高置信主张覆盖率不低于 95%，未支持的高置信主张为 0。
- 引用支持正确率不低于 95%，引用完整率不低于 90%；每个一级子问题覆盖率不低于 80%，不得存在零证据一级问题。
- 来源重复域和二手转载不能虚增独立证据数；关键结论至少有 2 个独立来源，或明确标注为单一来源结论。
- 报告可从任一关键句追溯到主张、证据、检索问题、来源决策和纠错记录。

### 1.8.4：多维评测、专家校准与硬失败上限

Goal: 让评分反映真实可交付性，而不是版式和结构完整度。

Implementation status (2026-07-13): engineering complete. The locked 100-case set now exports 100 primary and 30 stratified second-blind assignments with reviewer separation, arbitration, five expert dimensions, agreement, automatic-judge bias, undeliverable recall, hard-cap validation, attestations, and digests. The shared 20/40/59 policy is consumed by report quality, automatic evaluation, readiness, and solution delivery. The exported artifact remains honestly `pending` at 0/100 primary and 0/30 secondary reviews; no expert conclusion has been synthesized.

Scope:

- 将评测拆为 scope alignment、retrieval relevance、sub-question coverage、citation correctness、citation completeness、faithfulness、objectivity、analysis depth、actionability 和 presentation。
- 对行业、竞品、商机、可研、方案和投标文档配置不同 rubric；通用总分只用于汇总，不替代单项门禁。
- 建立真实失败集：医疗跑到编程工具、金融跑到科技委、跨行业客户泄漏、来源计数不一致、零扩展仍生成、引用不支持主张等。
- 完成 100 条独立复核 artifact，其中至少 30 条由两名领域评审者盲评并仲裁；记录评审一致性和自动裁判偏差。
- 自动裁判使用少量人工标签做校准并持续抽检，不将单一 LLM judge 作为发布依据。
- 引入硬失败分数上限：主题错位最高 20，最低证据包失败最高 40，存在无证据关键主张最高 59；硬门禁失败时交付状态始终为 blocked。

Acceptance:

- 自动门禁对人工“不可交付”样本的召回率不低于 95%，不得出现主题错位但总分可交付的样本。
- 专家盲评在准确性、完整性、洞察、可执行性和专业表达五维平均不低于 4/5，且无维度低于 3.5/5。
- 新版本与当前基线在同一真实样本集上盲测；只有硬失败率下降且关键指标不退化，才能进入默认链路。

### 1.9.0：架构决策工程化

Goal: 让解决方案从“合理措辞和通用组件”升级为可评审、可取舍、可验证的工程决策。

Implementation status (2026-07-13): engineering complete in the solution-delivery pack, Markdown, API contract, UI, and release regression. Evidence-ready solutions produce six measurable QAW scenarios, all ATAM finding classes, three-option baseline/pilot/target ADRs, C4 context/container/component/dynamic/deployment views, cloud-neutral and NIST AI checks, 100% requirement-to-test traceability, and zero orphan components. Evidence-light inputs degrade to workshop-only output; research hard failures remain blocked.

Scope:

- 先用 QAW 结构生成并确认质量属性场景：业务来源、刺激、环境、受影响对象、期望响应、可测响应指标和优先级。
- 每个关键问题至少比较现状基线、低风险试点和目标方案三类可行选项，禁止在未比较备选方案时直接给唯一推荐。
- 用 ATAM 风格 utility tree 组织质量属性，输出风险、非风险、敏感点、权衡点和风险主题。
- 升级现有 ADR：补充决策驱动因素、备选方案、证据、假设、后果、回滚条件和待验证项。
- 生成 C4 上下文、容器、必要组件、动态和部署视图；图中每个关键组件必须关联业务场景、数据、接口、责任边界和质量属性。
- 用云无关的 Well-Architected 矩阵检查可靠性、安全、性能、成本和运维；AI 方案额外映射 NIST AI RMF 的数据、模型、内容、供应链、人工监督和持续监控风险。
- 禁止孤立输出“知识库、RAG、智能体、接口编排”等通用组件；每个组件必须回答具体需求并有采用理由。

Acceptance:

- 关键非功能需求 100% 有可量化场景，关键架构决策 100% 有备选方案、权衡、证据和验证动作。
- 业务需求到能力、组件、数据、接口、部署、风险和验收测试的追溯链完整率为 100%，孤立组件为 0。
- 高风险决策均有 owner、截止时间、通过阈值和回退方案；未验证假设不能伪装成已确认事实。
- 研究门禁失败时不生成完整架构蓝图；研究通过但质量属性信息不足时，只生成 workshop 问题单和验证计划。

### 1.9.1：可执行验证与客户交付闭环

Goal: 用可运行证据证明方案，而不是以文档章节数量证明方案成熟。

Implementation status (2026-07-13): machine engineering complete. A digest-verified minimum vertical simulator executes eight proof checks for each medical, financial-services, and tourism reference scenario; the delivery pack separates customer-confirmed evidence from internal assumptions/limitations and maps quality scenarios and high-risk ADRs to machine-readable checks. Release readiness records failure types, correction rounds, human status, artifacts, and commands. The reference suite is `3/3 machine passed`, while real three-industry blind review and customer acceptance remain `pending`, so promotion stays blocked.

Scope:

- 从架构决策自动生成 proof-of-architecture 清单：API/数据契约、代表性数据流、容量与成本模型、威胁建模、权限边界、故障与恢复、可观测性和回滚测试。
- 为高风险路径提供最小纵向样机或模拟器，并把结果回写 ADR、风险和方案置信度。
- 将验证动作转成机器可读检查项，包含输入、执行方式、owner、截止时间、阈值、证据 artifact 和状态。
- 导出客户版正文与内部证据附录。客户版只呈现已确认结论；假设、限制、争议和待验证项不得被隐藏。
- 将质量失败类型、纠错轮次、人工结论和发布状态接入 release-readiness 聚合面板。

Acceptance:

- 所有高风险架构决策至少有一项实际测试、原型、数据核验或客户确认 artifact，不能只以模型自评关闭。
- 关键质量属性场景都能映射到验收测试，测试结果可回写方案结论和风险状态。
- 真实医疗、金融、文旅三类样本完成从研究问题到交付 artifact 的端到端盲评，Office roundtrip、视觉基线和内容门禁同时通过。

### 发布策略

- `1.8.2` 和 `1.8.3` 先以 shadow mode 对同一任务同时运行新旧链路，比较来源准入、阻断率、引用和人工结论。
- 通过真实回归后按 5% -> 25% -> 100% 放量；任一主题泄漏或无证据正式交付立即回滚。
- “一键更新到最强模型”只作为经过模块基准验证后的路由更新，不允许绕过证据与质量门禁，也不默认给所有模块统一换模。
- 每次升级保留 prompt、模型、检索器、reranker、规则、语料快照和评测集版本，保证结果可复现。
