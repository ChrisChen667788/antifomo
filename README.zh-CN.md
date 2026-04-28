# Anti-FOMO

[English](./README.md) | [简体中文](./README.zh-CN.md)

[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/ChrisChen667788/antifomo?style=social)](https://github.com/ChrisChen667788/antifomo/stargazers)

![Anti-FOMO hero](./docs/assets/github-hero.svg)

把嘈杂的网页与微信信息流，变成有证据的研报、专注执行和可交付动作。

Anti-FOMO 是一个开源 AI 研究工作台，适合咨询顾问、创业者、BD / 售前、策略团队和需要持续盯高信号内容的人。它不是“收藏稍后读 + AI 摘要”的叠加，而是把完整闭环重新接起来：

`collect -> clean -> research -> compare -> focus -> action`

先看这里：
- [快速开始](#快速开始)
- [公开路线图](https://github.com/ChrisChen667788/antifomo/issues/1)
- [适合新贡献者的入口](https://github.com/ChrisChen667788/antifomo/issues/2)
- [微信采集可靠性 help wanted](https://github.com/ChrisChen667788/antifomo/issues/3)
- [GitHub Discussions](https://github.com/ChrisChen667788/antifomo/discussions)
- [开源宣发素材包](./docs/open-source-launch-kit.md)
- [增长文案包](./docs/open-source-growth-copy.md)

## 为什么做 Anti-FOMO

大多数信息工具通常只覆盖其中一个环节：

- 收藏
- 摘要
- 搜索
- 导出笔记

Anti-FOMO 关注的是整条工作链路：

- 把 URL、文本、Feed 和微信重场景输入收进来
- 在清洗层尽量打掉 OCR 噪声、markdown/source dump、奖项论坛和弱 vendor 推进稿
- 基于证据生成研报、对比快照、历史版本和正式交付材料
- 用专注会话、行动卡、brief 和 watchlist 把研究继续推进成动作

## 为什么更容易吸引用户

- `WeChat-first`：不是泛网页收藏器，而是把微信信息环境当一等输入面。
- `Evidence-aware`：来源质量、章节证据配额、目标账户支撑率、官方源占比都被前台化。
- `Execution-oriented`：研报不是终点，后面还有专注会话、行动卡、brief、可研、项目建议书和对客 PPT 大纲。
- `Hackable`：本地优先的 Next.js + FastAPI 架构，附带浏览器扩展、小程序外壳、采集器和可跑的测试链路。

## 当前已经能做什么

### 1. 高信号采集

- URL、纯文本、RSS、Newsletter、文件、YouTube transcript 输入
- 浏览器扩展快速采集当前页面
- 微信 URL-first 采集、Collector 运维、Wechat PC Agent 工具链
- 针对截图 OCR、markdown dump、论坛奖项噪声、弱 vendor 推进稿的清洗规则

### 2. 研究工作台

- 关键词研究和结构化研报生成
- 追问 / 二次思考 / 补证后的二轮研报
- Compare Workspace、历史归档、字段 diff、导出链路
- Watchlists、Daily Brief、Knowledge Intelligence、Commercial Hub

### 3. 检索增强与质量层

- 本地 research retrieval index，支持持久化 rebuild、resume 和 search
- 章节级 retrieval pack 和 section 级证据诊断
- canonical org linking、guarded backlog、低质量研报 rewrite / backfill
- 近 3 年招投标/产品/技术参数情报包和方案交付包

### 4. 执行与交付

- 专注会话和会话总结导出
- 行动卡、老板简报、销售简报、外联草稿、watchlist digest
- 可行性研究报告、项目建议书、对客 PPT 大纲导出
- 支持用“场景 / 目标客户 / 更垂直场景”重建情报包和正式文档

## 适合谁

- 咨询顾问和策略团队
- 创业者、产品负责人和行业研究人员
- BD / 售前 / 解决方案团队
- 需要持续盯公众号和高频公开信号的人
- 想要本地运行、可改造、可验证的开源研究工作台的开发者

## 快速开始

### 1. 一次性安装

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:setup
```

这会安装前端依赖、后端 Python 依赖，并创建 `backend/.env`。

### 2. 一条命令启动

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:start
```

打开：

- Web：`http://localhost:3010`
- Backend API：`http://localhost:8000`

停止：

```bash
npm run demo:stop
```

### 3. 回归基线

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run check
npm run demo:smoke
```

如果要跑专注会话 E2E 和模拟流程：

```bash
npm run demo:focus-e2e -- --report-file .tmp/focus-e2e-report.json --artifact-dir .tmp/focus-e2e-artifacts
npm run demo:simulate
```

## 主要入口

- `http://localhost:3010/inbox`：采集、关键词研究、研报生成、正式文档导出
- `http://localhost:3010/research`：研究中心、Topics、Compare、Archive、检索增强分析
- `http://localhost:3010/focus`：专注会话和会话产物
- `http://localhost:3010/knowledge`：知识库、账户视图和 merge 工作流
- `browser-extension/chrome`：把当前页面快速送进 Anti-FOMO
- `miniapp`：微信小程序壳层
- `scripts/`：采集器、watchlist、插件验证和 smoke helpers

## 仓库结构

```text
.
├── src/                    # Next.js Web 应用
├── backend/                # FastAPI 后端、模型、服务、测试
├── miniapp/                # 微信小程序
├── browser-extension/      # Chrome 扩展
├── scripts/                # 采集器 / 自动化 / smoke helpers
├── docs/                   # 路线图、宣发素材、增长文案、设计资产
└── public/                 # 静态资源和 social preview
```

## 当前项目状态

当前代码基线：

- 本地优先、可直接运行的产品原型
- 当前版本：`0.4.2+20260424`
- Web 构建可通过
- 后端测试可通过 `npm run check`
- 仓库已做开源脱敏

公开仓库刻意不包含：

- 运行时 `.env` 密钥
- 个人数据
- 本地采集日志和截图
- 私有数据库或未声明的付费信源
- 真实小程序生产凭证

## 社区与宣发资源

- 产品想法和需求：开 Discussion 或 Issue
- Bug：附带复现步骤和日志
- 代码贡献：见 [CONTRIBUTING.md](./CONTRIBUTING.md)
- 安全问题：见 [SECURITY.md](./SECURITY.md)

仓库内已附带一套可直接复用的宣发资产：

- [开源宣发素材包](./docs/open-source-launch-kit.md)
- [增长文案包](./docs/open-source-growth-copy.md)
- [公开 backlog](./docs/open-source-backlog.md)
- [GitHub hero 图](./docs/assets/github-hero.svg)
- [GitHub social preview](./docs/assets/github-social-preview.png)
- [仓库 banner](./public/repo-banner.png)

如果 Anti-FOMO 对你的工作流有价值，点一个 star 依然是最直接的支持方式。它能显著提升仓库曝光，也能帮助后续用户和贡献者更快发现它。
