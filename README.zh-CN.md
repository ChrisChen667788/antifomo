# Anti-FOMO

[English](./README.md) · [简体中文](./README.zh-CN.md)

<p align="center">
  <img src="./docs/assets/github-hero-20260910.png" alt="Anti-FOMO：散落的信息通过透镜形成有据可循的研究" width="1200" />
</p>

**从微信收藏，到有出处的方案判断。**

Anti-FOMO 是面向解决方案架构师、行业顾问和售前团队的开源研究与方案工作台。把网页、微信文章和文件带进来，沿着证据整理研报、准备架构讨论，再落到下一步行动。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![CI](https://github.com/ChrisChen667788/antifomo/actions/workflows/ci.yml/badge.svg)](https://github.com/ChrisChen667788/antifomo/actions/workflows/ci.yml)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](./package.json)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)](./backend/README.md)
[![GitHub stars](https://img.shields.io/github/stars/ChrisChen667788/antifomo?style=social)](https://github.com/ChrisChen667788/antifomo/stargazers)

[快速开始](#快速开始) · [产品演示](#产品演示) · [架构与流程](#这些能力如何连起来) · [WorkBuddy 对比](./docs/workbuddy-deep-dive-2026-09-18.md) · [路线图](./docs/public-roadmap.md)

> **当前状态：**本地优先的开发原型。开发进展、证据覆盖与尚待完成的验收统一维护在[当前产品状态](./docs/current-product-status.md)。现阶段没有可对外承诺的客户收益数据或生产服务等级。

## 你要完成的工作

看到一篇文章，觉得“这个可能对客户有用”，先收藏起来。等到下一场会议前，仍然要回答：**发生了什么变化，依据在哪里，接下来该做什么？**

Anti-FOMO 把这些步骤放在同一条工作流里：

`采集 → 检查来源 → 研究 → 对比 → 准备判断 → 跟进行动`

| 你的任务 | 带进来的材料 | 带到下一场讨论的结果 |
| --- | --- | --- |
| 准备客户方案研讨 | 客户背景、公开证据、已知约束 | 研报草稿、架构选项、集成风险与待核实问题 |
| 判断该跟进哪个项目 | 招采公告、政策、行业和客户信号 | 带来源的机会背景、缺失事实与跟进动作 |
| 持续更新竞品判断 | 官方产品页面与关注清单 | 有日期的变化摘要、过期提示与可复核的产品决策 |

期望价值是减少重复找资料和补上下文的时间，让研究更顺畅地进入交付。这些收益目前是**需要试点验证的目标**，不是已经取得的客户结果。测量办法见[价值与验收地图](./docs/value-map.md)。

## 产品演示

<p align="center">
  <a href="./docs/assets/marketing/antifomo-overview.mp4">
    <img src="./docs/assets/marketing/antifomo-overview.gif" alt="Anti-FOMO 产品概览：来源采集、证据核查、方案准备与后续行动" width="100%" />
  </a>
</p>

[观看 15 秒静音概览](./docs/assets/marketing/antifomo-overview.mp4) · [宣传海报](./docs/assets/marketing/poster.png) · [演示脚本与素材来源](./docs/marketing/DEMO-SCRIPT.md)

概览由 v1.9.1 历史本地 Demo 截图剪辑而成，运镜与字幕用于解释产品思路；它不是当前版本的端到端实录，也不能证明 2.11.8 已通过验收。页首透镜图为品牌概念设计。

### 1. 让收藏有一个下一步

把微信收藏导出的文件或链接导入，先预览、去重，再在首页队列中收藏或忽略。未处理批次、失败条目和采集源健康状态都能查看，方便回来继续处理。

### 2. 让结论带着出处

限定研究问题，检查来源和检索诊断，通过主题历史与对比页查看变化。缺失证据会成为待补问题。方案输出把假设、依赖、决策标准和验证动作带到客户讨论中。

### 3. 带走一份可以继续审阅的材料

准备研报、方案纲要、可研或项目建议书草稿、行动卡和专注会话总结。Decision Studio 与产品策略工作区补充来源修订、交付物差异和复核记录。文件导出成功与客户认可，分别记录。

<table>
  <tr>
    <td width="50%"><img src="./docs/assets/screenshots/home-signal-dashboard.png" alt="包含微信收藏导入与可恢复处理队列的首页" /><br /><strong>先把输入理顺</strong><br />预览、去重、收藏，回来接着处理未完成条目。</td>
    <td width="50%"><img src="./docs/assets/screenshots/research-compare-workspace.png" alt="展示研究版本和证据上下文的对比工作区" /><br /><strong>看清这次改了什么</strong><br />在沿用结论之前，对照研究版本和新增证据。</td>
  </tr>
  <tr>
    <td width="50%"><img src="./docs/assets/screenshots/knowledge-commercial-hub.png" alt="展示账户、机会与后续动作的知识库商业工作区" /><br /><strong>为客户跟进做准备</strong><br />把研究放回账户背景、机会判断与下一次沟通。</td>
    <td width="50%"><img src="./docs/assets/screenshots/collector-operations-workspace.png" alt="展示按来源诊断与恢复提示的采集器工作区" /><br /><strong>找到具体失效的来源</strong><br />检查采集健康状态，按提示恢复。</td>
  </tr>
</table>

上述为 [v1.9.1 历史截图集](./docs/assets/screenshots/screenshot-manifest.json)，不代表当前全部功能界面。[完整截图集](./docs/feature-screenshot-coverage.md)与[当前状态](./docs/current-product-status.md)保留采集日期和覆盖范围。

## 这些能力如何连起来

前端使用 Next.js 与 TypeScript；FastAPI 负责采集、研究、知识、任务和交付。本地 Demo 使用 SQLite。研究工作流通过框架中立协议接入 LangGraph，并保留 deterministic 引擎作为编排回退路径。

<p align="center"><img src="./docs/assets/antifomo-control-plane.svg" alt="Anti-FOMO 架构：输入入口、业务服务、研究与证据存储，以及外部适配边界" width="100%" /></p>

[架构图源文件](./docs/diagrams/architecture.mmd) · [界面与代码地图](./docs/product-surface-map.md)

<p align="center"><img src="./docs/assets/dataflow.svg" alt="数据流：采集资料经过研究和证据修订，形成可复核交付物" width="100%" /></p>

<p align="center"><img src="./docs/assets/workflow.svg" alt="研究工作流：来源检查、证据不足时的恢复、审阅与交付" width="100%" /></p>

图中的路径表示当前代码和数据关系，后续执行控制单独标为计划项；它们不是实时监控。[数据流源文件](./docs/diagrams/dataflow.mmd) · [工作流源文件](./docs/diagrams/research-delivery.mmd)。

**接入边界也写清楚：**现有 WorkBuddy 兼容 webhook 能执行支持的导出任务，并向配置的地址回调；未配置 webhook secret 时会跳过签名校验。Focus 委派可调用本机 CodeBuddy CLI。这些历史路径没有统一的人工批准门禁，也不等于已完成腾讯 WorkBuddy 原生互通。[后续接入方案](./docs/workbuddy-integration-plan-2026-09-18.md)会先补齐这些边界，再扩展功能。

## 为什么适合这个领域

- **贴近中文商业输入：**微信文章、公开招采和政策信号，以及围绕客户的研究上下文。
- **方便审阅推理过程：**来源版本、证据缺口、研报对比和交付物记录，让复核者知道从哪里查起。
- **衔接方案准备：**架构选项、干系人问题、集成依赖和验证动作，让研究进入咨询与售前交付。
- **实现可以检查和改造：**本地数据、可配置模型和可追踪的模块边界，方便开发者参与。

WorkBuddy 的通用办公执行与 Anti-FOMO 的垂直证据工作流各有适用场景。具体优劣势、官方来源与待验证项见 [WorkBuddy 深度对标](./docs/workbuddy-deep-dive-2026-09-18.md)；拟吸收功能、交付顺序与验收要求见[可执行迭代方案](./docs/workbuddy-integration-plan-2026-09-18.md)。

## 快速开始

准备 **Node.js 20+** 与 **Python 3.11**，确保终端能找到 `python3.11`。

```bash
git clone https://github.com/ChrisChen667788/antifomo.git
cd antifomo
npm run demo:setup
npm run demo:start
```

打开 Web **http://localhost:3010**，后端 **http://localhost:8000**。安装脚本会准备依赖，并在缺失时创建 `backend/.env`。

示例配置的主 LLM 使用 mock。完整研究、可选嵌入模型、策略模型和外部服务仍需分别配置，见[后端说明](./backend/README.md)和[环境变量示例](./backend/.env.example)。本地启动成功不表示所有外部服务已接通。

先用一条公开或合成样例走一遍：

1. 打开 `/inbox`，添加你有权使用的链接或文本。
2. 查看条目及来源状态，把值得保留的材料存入工作区。
3. 配置研究模型后，围绕一个范围明确的问题生成研究，导出前先看缺口。
4. 进入 `/research`、`/knowledge/accounts`、`/studio`、`/competitive` 查看相关复核界面。

```bash
npm run demo:stop        # 停止本地服务
npm run check            # Lint、测试、监测逻辑与构建
npm run demo:smoke       # API 冒烟检查；需要后端运行
```

[浏览器扩展](./browser-extension/README.md)、[微信小程序](./miniapp/README.md)和[采集入口说明](./docs/product-surface-map.md)提供其他使用路径。

## 你可以核验的证据

| 证据 | 能支持的判断 | 不能据此推导 |
| --- | --- | --- |
| [CI 与测试](https://github.com/ChrisChen667788/antifomo/actions/workflows/ci.yml) | 对应提交上的代码检查可重复执行 | 客户已验收、生产可用率已达标 |
| [采集器基准](./docs/wechat-collector-reliability-benchmark.md) | 小规模确定性合成样本上的去重行为 | 真实微信采集成功率、客户节省时间 |
| [浏览器捕获清单](./docs/assets/competitive-evidence/competitive-evidence-manifest.json) | 有日期的本地浏览器与模拟移动视口记录 | 物理真机覆盖、生产 SLA |
| [Office 证据收据](./docs/office-evidence-receipts-v2.10.5.md) | 文件、修订和渲染结果可追溯 | 内容已独立复核、客户已签收 |

如何设计试点、验收指标，以及如何区分目标与实测结果，见[产品白皮书](./docs/product-whitepaper.md)和[价值地图](./docs/value-map.md)。

## 一起把它做得更好

欢迎从工作中一个具体卡点开始：抓不到的来源、说不清的引用、不好用的导出，或重复操作太多的步骤。附上可复现的小样例和你期望看到的结果，会更容易推进。

- [中文贡献指南](./CONTRIBUTING.zh-CN.md) · [开放 Issue](https://github.com/ChrisChen667788/antifomo/issues) · [社区讨论](https://github.com/ChrisChen667788/antifomo/discussions)
- [公开路线图](./docs/public-roadmap.md) · [贡献者待办](./docs/open-source-backlog.md)
- [宣发素材包](./docs/open-source-launch-kit.md) · [可复制文案](./docs/open-source-growth-copy.md)
- [版本与功能历史](./docs/release-history-and-feature-map.md) · [安全反馈](./SECURITY.md)

公开贡献前请去除私有材料、令牌、本地数据库和客户标识。项目采用 [MIT 许可证](./LICENSE)。

如果这也是你正在处理的问题，欢迎试一个小任务，告诉我们哪一步没有接上。可复现的 Issue 和范围明确的 PR 都很有帮助。

## Star 趋势

<a href="https://www.star-history.com/?repos=ChrisChen667788%2Fantifomo&amp;type=date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ChrisChen667788/antifomo&amp;type=Date&amp;theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=ChrisChen667788/antifomo&amp;type=Date" />
    <img alt="Anti-FOMO GitHub Star 趋势图" src="https://api.star-history.com/svg?repos=ChrisChen667788/antifomo&amp;type=Date" width="800" />
  </picture>
</a>

图表由 Star History 提供，可用性与刷新时间取决于该服务。
