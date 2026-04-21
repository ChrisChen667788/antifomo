# Anti-FOMO 系统能力对照表

更新时间：2026-03-23

## 1. 总览

当前系统可以拆成 4 条主链路：

1. `WorkBuddy 兼容控制通道`
2. `研报中心公开信息源采集链`
3. `微信公众号 PC 采集链`
4. `LLM 解析与任务执行链`

其中：

- `WorkBuddy` 当前是 **本地兼容 webhook 适配层**，不是腾讯官方托管账号模式。
- `爬虫/采集工具` 主要用在：
  - 研报中心的公开信息源采集
  - 微信公众号内容采集

---

## 2. 系统能力对照表

| 能力链路 | 当前接入位置 | 运行环境 | 作用 | 当前是否可验证 | 主要限制 |
| --- | --- | --- | --- | --- | --- |
| WorkBuddy 兼容控制通道 | `backend/app/api/workbuddy.py` | 后端 API + Web/小程序前台 | 任务控制、导出、委派 | 是 | 不是腾讯官方账号接入 |
| 研报中心公开信息源采集 | `backend/app/services/research_source_adapters.py` | 后端 research pipeline | 为研报补充公开招投标、政策、讲话、交易公告等证据 | 是 | 仅公开可访问源，未做付费墙/登录墙绕过 |
| 微信公众号 PC 采集器 | `scripts/wechat_pc_full_auto_agent.py` | Mac/PC 微信前台 + 后端 collector | 扫公众号文章、正文入库、转为内容卡片 | 是 | 依赖 PC 微信 UI 稳定性 |
| LLM 解析与行动卡生成 | `backend/app/services/research_service.py` 等 | 后端 | 生成摘要、标题、研报、行动卡、Top 3 排序与推理 | 是 | 受模型响应速度和公开证据密度影响 |

---

## 3. WorkBuddy 对接现状

### 3.1 当前模式

`WorkBuddy` 当前不是腾讯官方托管模式，而是项目内置的兼容适配层。

后端健康接口明确返回：

- `integration_mode = local_webhook_adapter`
- `official_tencent_connected = false`
- `provider_label = WorkBuddy-compatible local webhook adapter`

参考代码：

- [backend/app/api/workbuddy.py](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/backend/app/api/workbuddy.py)
- [backend/app/services/workbuddy_adapter.py](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/backend/app/services/workbuddy_adapter.py)

### 3.2 已接入环节

| 环节 | 具体作用 | 前台入口 |
| --- | --- | --- |
| 设置页 WorkBuddy 面板 | 检查健康状态、`ping`、手动触发任务 | Web 设置页、小程序设置页 |
| Session Summary | 导出 `Markdown 总结 / 阅读清单 / 待办草稿` | Summary 页面 |
| 知识库 | 导出知识卡 Markdown | 知识详情页 |
| 研报 | 导出研报 Markdown / Word / PDF | Inbox / 研报结果卡 |
| Focus Assistant | 作为低风险任务委派/执行通道 | Focus 页面 |

相关前台代码：

- [src/components/settings/workbuddy-panel.tsx](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/src/components/settings/workbuddy-panel.tsx)
- [src/components/session/session-summary-panel.tsx](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/src/components/session/session-summary-panel.tsx)
- [src/components/knowledge/knowledge-detail-card.tsx](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/src/components/knowledge/knowledge-detail-card.tsx)
- [miniapp/pages/settings/index.js](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/miniapp/pages/settings/index.js)
- [miniapp/utils/api.js](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/miniapp/utils/api.js)

### 3.3 WorkBuddy 当前起到的具体作用

它当前主要承担：

- `控制通道`
- `导出通道`
- `Focus Assistant 委派通道`

它当前 **不承担**：

- 个人微信会话托管
- 公众号数据抓取
- 腾讯官方账号连接

### 3.4 如何验证 WorkBuddy 已接入

你可以用这 3 种方式确认：

1. 访问 `GET /api/workbuddy/health`
2. 打开 Web 设置页里的 `WorkBuddy` 面板
3. 在 `Session Summary` 或 `知识库` 里实际点一次导出

---

## 4. 研报中心爬虫/信息源适配器

### 4.1 运行环境

研报中心的信息源采集运行在后端 `research pipeline` 中。

核心代码：

- [backend/app/services/research_source_adapters.py](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/backend/app/services/research_source_adapters.py)
- [backend/app/services/research_service.py](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/backend/app/services/research_service.py)
- [backend/app/api/research.py](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/backend/app/api/research.py)

### 4.2 当前已接入的数据源

| 数据源 | 类型 | 主要用途 |
| --- | --- | --- |
| 剑鱼标讯 | 招投标聚合源 | 招标、中标、预算、项目线索 |
| 云头条 | 招投标/行业聚合源 | 商机、标讯、行业动态 |
| 全国公共资源交易平台 `ggzy.gov.cn` | 官方公共资源源 | 项目公告、中标、项目期次 |
| 中国招标投标网 `cecbid.org.cn` | 官方/公共招投标源 | 招标、中标、采购进度 |
| 政府采购合规聚合 | 合规聚合源 | 采购意向、采购公告、预算线索 |
| 中国政府网 `gov.cn` | 官方政策/讲话源 | 政策、领导讲话、战略规划 |
| 地方公共资源交易平台 | 地方官方源 | 区域项目、地方中标、采购节奏 |

代码里的可配置开关包括：

- `enable_jianyu_tender_feed`
- `enable_yuntoutiao_feed`
- `enable_ggzy_feed`
- `enable_cecbid_feed`
- `enable_ccgp_feed`
- `enable_gov_policy_feed`
- `enable_local_ggzy_feed`

### 4.3 当前采集的数据类型

研报链路当前重点采集：

- 招标公告
- 中标/成交公告
- 采购意向
- 预算/投资金额信号
- 项目分布
- 项目二期/三期/四期线索
- 政策发布
- 领导讲话
- 战略规划
- 甲方同行动态
- 中标方同行动态
- 标杆案例
- 生态伙伴线索
- 决策部门线索
- 公开业务联系方式线索

### 4.4 前台怎么验证爬虫是否起作用

研报结果卡和研报中心前台会显示：

- 启用的信息源
- 实际命中的 source labels
- `命中爬虫源`
- `命中搜索源`
- `官方源 / 媒体源 / 聚合源` 分层

前台代码：

- [src/components/inbox/research-report-card.tsx](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/src/components/inbox/research-report-card.tsx)
- [src/components/research/research-center.tsx](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/src/components/research/research-center.tsx)
- [miniapp/pages/inbox/index.wxml](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/miniapp/pages/inbox/index.wxml)
- [miniapp/pages/research/index.wxml](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/miniapp/pages/research/index.wxml)

---

## 5. 微信公众号 PC 采集器

### 5.1 运行环境

这条链运行在：

- 桌面端脚本
- 后端 collector
- PC 微信前台

核心代码：

- [scripts/wechat_pc_full_auto_agent.py](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/scripts/wechat_pc_full_auto_agent.py)
- [backend/app/services/wechat_pc_agent_daemon.py](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/backend/app/services/wechat_pc_agent_daemon.py)
- [backend/app/api/collector.py](/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/backend/app/api/collector.py)

### 5.2 这条链抓什么

| 数据类型 | 说明 |
| --- | --- |
| 公众号文章链接 | 主路径优先 URL/DOM |
| 文章正文 | 入库成 `items` |
| OCR 预检文本 | 用于判断当前是否真的是文章详情页 |
| 批次状态 | 采集进度、已见去重、失败数 |
| 去重状态 | 避免重复文章重复入库 |

### 5.3 这条链的作用

它的目标不是出研报，而是：

- 把公众号文章变成内容卡片
- 进入 Feed / Inbox / Focus / Session Summary
- 再走摘要、标签、评分、建议动作链路

### 5.4 如何验证它在工作

你可以看这些接口：

- `GET /api/collector/wechat-agent/status`
- `GET /api/collector/wechat-agent/batch-status`
- `GET /api/collector/wechat-agent/dedup-summary`

---

## 6. LLM 解析与任务执行链

### 6.1 当前负责的事情

| 模块 | 作用 |
| --- | --- |
| Summarizer | 标题精炼、短摘要、长摘要 |
| Tagger | 标签提取 |
| Scorer | 价值判断与建议动作 |
| Research Service | 深度研报、行动卡、Top 3 排序与推理 |
| Focus Assistant | Focus 任务编排和委派 |

### 6.2 产出内容

- 内容卡摘要
- 标签
- 建议动作
- 研报
- 行动卡
- 高价值甲方 Top 3
- 高威胁竞品 Top 3
- 高影响力生态伙伴 Top 3

---

## 7. 当前边界

当前系统明确 **不做**：

- 付费墙绕过
- 登录墙绕过
- 未授权后台数据抓取
- 腾讯官方 WorkBuddy 账号托管
- 个人微信私聊自动托管

当前系统明确 **已做**：

- 本地 WorkBuddy 兼容适配层
- 公开源/官方源/聚合源采集
- PC 微信公众号内容采集
- 研报、行动卡、知识库、Focus 串联

---

## 8. 推荐验证路径

### 验证 WorkBuddy

1. 打开 `Web 设置页 -> WorkBuddy`
2. 查看健康状态
3. 触发一次 `Session Summary` 导出

### 验证研报采集器

1. 打开 `Web Inbox`
2. 输入一个关键词生成研报
3. 观察：
   - 启用信息源
   - 命中爬虫源
   - 命中搜索源
   - 来源分层

### 验证公众号采集器

1. 打开 `Collector` 或 `Focus`
2. 查看微信 agent 状态/批次进度
3. 在 `Session Summary` 或 `Feed` 看新增内容卡片

---

## 9. 一句话结论

- `WorkBuddy` 目前负责“控制和执行”，不负责“抓数据”。
- `爬虫/采集器` 目前分成“研报公开源采集”和“微信公众号内容采集”两条链。
- `研报中心` 抓的是招投标、预算、政策、讲话、战略、案例、伙伴等公开情报。
- `公众号采集器` 抓的是文章链接和正文，再转成卡片。
