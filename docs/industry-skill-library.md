# 本地行业资料 Skill 库

## 目标

将用户本地的行业报告、白皮书、解决方案、政策标准、证券研究和演示材料沉淀为可重建的行业 Skill 与全文 RAG 知识库，供“解决方案智囊”在生成可研、项目建议书和对客 PPT 大纲时选择使用。

原始资料不会移动、改名或上传。默认来源目录为 `~/.antifomo/industry-sources`，默认生成目录为 `.tmp/industry-skills`，两者均可通过命令参数或环境变量覆盖。可用 `INDUSTRY_SKILL_SOURCE_DIR` 指向自己的资料目录。

## 建库

```bash
npm run knowledge:industry-skills:build
```

该命令会：

- 排除 macOS `._*` AppleDouble 元数据文件。
- 对每份 PDF 提取全部页文本，对每份 PPTX 提取全部幻灯片文本；分类依据是全文内容，文件名只作为次要信号。
- 对扫描型 PDF 使用本机 macOS Vision OCR；OCR 不可用或失败时明确标记为 `ocr_pending`/失败，绝不把它伪装成已理解内容。
- 为每份资料生成内容覆盖率、页数/幻灯片数、全文哈希、结构目录线索与抽取式内容要点。
- 在 `rag/industry_knowledge.sqlite3` 建立 SQLite FTS5 trigram 关键词索引，在 `rag/industry_passages.npy` 建立本地句向量索引；运行时用 RRF 融合两路召回。
- 按行业、文件类型、分类置信度和内容分析状态生成 `catalog.json` 与 `classification-report.md`，并为每个有资料覆盖的行业生成 `skills/<industry>.md`。

示例：

```bash
backend/.venv311/bin/python scripts/build_industry_skill_library.py \
  --source-dir ~/.antifomo/industry-sources \
  --output-dir .tmp/industry-skills \
  --workers 4
```

默认会执行全文解析、OCR 和 RAG 索引。仅需要排查解析问题时可以加 `--skip-rag` 或 `--skip-ocr`；这两种模式不会满足正式的全文 RAG 完整性要求。

## 运行时边界

方案智囊默认匹配最多三个行业 Skill，用户也可以在“正式文档与方案交付输出”中显式选择。它会从已选行业的全文 RAG 中检索与当前主题、客户和场景相关的真实段落，再将带页码/幻灯片定位的待核验要点进入可研、项目建议书、PPT 大纲、编译文档章节和 Markdown 导出中的“行业资料技能与规范性要求”。

本地资料只用于行业框架、交付规范和自检，不会增加公开来源支撑度，不会被写成客户事实，也不会绕过研究证据门或正式交付门。任何对外数据、政策、机构和案例仍需回查原件与官方来源。

`GET /api/research/industry-skills/retrieve?query=文旅AIGC景区导览` 可用于查看混合检索结果。公开 API 只返回脱敏短片段、文件名和页码/幻灯片定位，不返回外接盘绝对路径或全文。

## 检索排序 A/B

生产默认仍是 `baseline_hybrid`。固定题集 A/B 只在评测任务中显式调用候选策略，不会因为配置存在或一次运行成功而改变线上检索路径：

- `baseline_hybrid`：当前关键词 FTS5 + 向量 RRF 混合检索基线。
- `prefilter_weighted_hybrid`：先按行业/文件类型过滤关键词候选，再提高标题字段权重，解决先截全库候选后范围过滤可能造成的漏召回。
- `prefilter_weighted_rerank`：在候选 A 之上使用真实 Cross Encoder 复排。仅当本地模型快照可用且实际后端返回 `sentence-transformers` 时计为真实复排；离线缺失时不联网下载，也不把启发式回退算作复排成功。

运行和查看评测：

```bash
npm run knowledge:industry-skills:retrieval-ranking
npm run knowledge:industry-skills:retrieval-ranking:review:validate
```

同一能力也在研究中心的“Local Knowledge Retrieval”面板可查看或重跑，接口为：

```text
GET  /api/research/industry-skills/retrieval-ranking-benchmark
POST /api/research/industry-skills/retrieval-ranking-benchmark/run
```

需要进行报告人工评分时，可用 `POST /api/research/industry-skills/retrieval-ranking-benchmark/delivery-review` 传入某个固定 `case_id` 和同一份已经通过正式交付门的研报。服务会只改变本地行业资料检索策略，生成三份完整方案交付 Markdown 并自动回写评分模板的 `report_artifact_path`；它不会替用户生成分数或把候选策略写入生产默认路径。

固定题集位于 `backend/evaluation/industry_knowledge_retrieval_ranking_v1.json`，当前覆盖政务、制造、金融、能源、汽车、医疗、农业、AI、文旅、零售、地产和通信资料。每一臂都计算 Recall@10、nDCG@10、引用命中率与平均延迟，并落盘至 `.tmp/industry-knowledge-retrieval-ranking-ab-v1.json`。

评测同时生成每个“题目 x 策略”的可追溯固定证据审阅样本，并在 `.tmp/industry-knowledge-retrieval-ranking-ab-v1-human-review.json` 中提供评分模板。样本只用于核验检索证据，不能代替完整研报。人工评分必须关联同策略的真实 `report_artifact_path`、覆盖全部题目和策略、填写独立复核声明；没有报告工件的分数会被排除。候选还必须不使任一检索指标相对基线回退超过 1 个百分点、人工均分至少 4.0/5、延迟不超过 2 倍，并获得明确质量增益；复排候选还必须在全部题目中取得真实 Cross Encoder 证据。任一条件未满足时结论保持 `HOLD`。

## 维护

- 新增、删除或替换资料后重新执行建库命令。
- `INDUSTRY_SKILL_LIBRARY_DIR` 可指定生成目录；`INDUSTRY_SKILL_CATALOG_PATH` 可为运行时指定不同 catalog。
- 外接盘暂时未挂载时，运行时仍可使用已沉淀的本地索引；打开原件或重新建库前必须重新连接资料盘。
- 优先使用配置的 `BAAI/bge-m3` 离线缓存；若该缓存盘未挂载，系统只会使用已缓存的后备模型并在 API/UI 中明确显示降级原因，绝不联网下载或隐瞒实际模型。
