# 2.10.5 Office 证据收据

## 交付结论

2.10.5 已实现本地 Office 证据收据：将 DOCX/PPTX 原文件摘要、2.10.2 工件 revision、OpenXML 结构校验、Office 导出 PDF 摘要和逐页 PNG 摘要绑定为不可变记录。

这不是交付验收。收据固定保持 `HOLD` / `blocked`，不能自动接受工件、批准发布或宣称生产可用；具名人工视觉复核、客户验收和发布批准仍须另行提供。

## 可复核路径

- API：`GET/POST /api/product-strategy/office-evidence-receipts`
- UI：竞品与迭代工作台中的“Office 交付物证据收据”
- 后端服务：`backend/app/services/product_strategy/office_evidence_service.py`
- 数据表：`product_strategy_office_evidence_receipts`
- 本地存储：`.storage/product-strategy/office-evidence/<source-sha256>/`

上传可只提供 DOCX/PPTX；环境存在 LibreOffice 时执行无头转换。也可同时提供由 Microsoft Word/PowerPoint 实机导出的 PDF，服务端重新校验 PDF、用 `pdftoppm` 渲染页面并记录全部页级 SHA-256。伴随 PDF 仅证明本次导出记录，不能证明操作者身份或独立人工验收。

## 本轮实际证据

- 源文件：`shanghai-medical-ai-2026-feasibility_docx.docx`
- DOCX SHA-256：`017d5e66c6c14c5fe3281310a4d2248865b701aeb290d95a7294b6373749696f`
- Microsoft Word 导出 PDF SHA-256：`1bb35e3bc3254b7c04c638d83f039e468657727043bbf0c949ba27409b552072`
- 页数：20；已逐页检查，无截断、重叠、缺字或图片丢失
- 结构：21 个章节、9 个附录、原生图片、主题和编号结构均保留
- 内容门禁：证据账本、语义挑战和交付自审仍为 `fail`，因此内容修订、具名人工复核和外发验收仍被阻断

该样本来自本地历史回归基线，只能作为本地运行证据，不是客户材料、生产输出或业务验收结果。

## 安全与一致性

- 仅允许不含目录的 `.docx` / `.pptx` 文件名，拒绝路径穿越。
- Base64 严格解码，单文件最大 20 MB。
- 文件扩展名与 media type 必须一致。
- 同一工件与源文件摘要幂等去重。
- 记录绑定当前 artifact revision digest，后续 revision 不会改写旧收据。
- 文件存储只返回逻辑引用，不暴露本机绝对路径。
