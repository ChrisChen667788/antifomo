# Anti-FOMO 增长文案与分享指南

更新时间：2026-09-22。可复制的文字必须与仓库当前实现和[证据词汇](./current-product-status.md#evidence-legend)一致。

## 先说清楚产品

**中文短版**

> Anti-FOMO 是一个面向解决方案架构师、行业顾问和售前团队的开源研究工作台：把网页与微信信号整理成带出处的研报、架构讨论材料和后续动作。它不只做摘要，还把来源状态、研究版本、证据缺口和方案验证问题放到同一条工作流里。

**English short version**

> Anti-FOMO is an open-source research and solution workspace for consultants, solution architects, and pre-sales teams. It turns web and WeChat-heavy inputs into reviewable research, architecture options, evidence gaps, and next actions.

## 适合发在 X / 即刻

### 中文

> 收藏了一堆链接，客户会议前仍然说不清依据和下一步？
>
> 我在做 Anti-FOMO：
> - 微信/网页/文件进入可恢复队列
> - 来源状态、证据缺口和版本变化可见
> - 研报继续进入架构蓝图、验证动作和会议准备
> - 本地优先、开源、可检查
>
> 15 秒概览（历史本地 Demo 截图剪辑）：`docs/assets/marketing/antifomo-overview.mp4`
> GitHub：https://github.com/ChrisChen667788/antifomo

### English

> Lots of saved links, but the next customer meeting still needs a source, a decision, and a next step?
>
> Anti-FOMO is an open-source workspace for that handoff:
> - collect web, WeChat, and file signals
> - inspect source health and evidence gaps
> - compare research revisions
> - turn the result into architecture discussion and follow-up
>
> Overview: https://github.com/ChrisChen667788/antifomo

## 中文公众号 / 知乎长文提纲

### 标题

**我不想再把“收藏链接”和“客户方案”放在两个世界里：Anti-FOMO 的研究到行动工作流**

### 开头

真正费时间的不是打开一篇文章，而是在会议前重新找回它：来源是否还有效？当时的判断是什么？哪些只是我的假设？客户下一步要确认什么？

### 中段：一条真实工作流

1. 把微信收藏、网页或文件送进 Collector。
2. 先看批次、去重和来源健康，不让失败悄悄消失。
3. 在 Inbox 写下范围明确的研究问题。
4. 在 Research Center 查看报告、引用、证据缺口和版本变化。
5. 在 Decision Studio/架构工作台整理依赖、风险、NFR 和验证问题。
6. 用 Focus、行动卡或导出任务准备下一次沟通。

### 结尾

Anti-FOMO 当前是本地优先开发原型。仓库提供真实代码界面、测试和可复现的本地/合成证据，但没有把这些写成客户 ROI 或生产 SLA。欢迎拿公开样例试跑，提交一条具体 Issue。

## LinkedIn 中文/英文

**中文：**

> 我把 Anti-FOMO 重新整理成一条“信号 → 证据 → 方案 → 行动”的开源工作流。它服务于解决方案架构、咨询和售前团队：微信和网页信号先进入可恢复队列，再通过来源诊断、研究版本、架构蓝图和验证动作进入客户讨论。当前仍是本地优先开发原型；我更希望看到真实使用者指出哪一步还不够顺。

**English:**

> I am building Anti-FOMO around one practical handoff: signal → evidence → solution → action. It is an open-source, local-first workspace for solution architects, consultants, and pre-sales teams working with web and WeChat-heavy inputs. The repository shows the code, UI, tests, and evidence boundaries; it does not turn a local prototype into a production or customer claim. Feedback on a concrete workflow is welcome.

## Hacker News / Reddit

**标题：**

- Show HN: Anti-FOMO — an open-source workspace from web/WeChat signals to reviewable solution decisions
- [P] I built a local-first research workflow for evidence-backed architecture preparation

**首条说明：**

> Anti-FOMO keeps collection state, source freshness, report revisions, architecture context, and follow-up artifacts connected. The backend is FastAPI, the web app is Next.js, and the local demo uses SQLite. The existing WorkBuddy-compatible webhook executes supported exports and callbacks; signature verification depends on a configured secret. An optional CodeBuddy CLI bridge supports delegation. These paths do not establish native Tencent-hosted WorkBuddy execution or universal approval coverage. The repo documents what is implemented, what is demo evidence, and what still needs human or customer acceptance.

## 产品更新模板

```text
Anti-FOMO <version/date>

问题：<哪一个研究、采集或交付步骤卡住>
变化：<用户现在能看到/完成什么>
证据：<测试、截图、fixture、monitor run 或具名验收；写清 tier>
边界：<未测量的指标、历史截图、外部依赖或 HOLD 项>
试用：<route / command / demo asset>
反馈：<一个可复现的 Issue 或讨论问题>
```

## 不能这样写

- “生产级”“替代专家”“节省 80% 时间”：除非链接到生产或客户验收证据。
- “已接入腾讯 WorkBuddy”：当前应写“WorkBuddy-compatible webhook/可选 CodeBuddy CLI bridge”。
- “100% 准确”“真实 SLA”：合成 benchmark、CI 通过和本地浏览器测量不支持这些说法。
- “最新版已完成全部验收”：请链接 canonical status，并区分 development、demo、evidence-gated、human/customer acceptance。

## 传播素材顺序

1. [`antifomo-overview.gif`](./assets/marketing/antifomo-overview.gif)：无声、可快速理解的流程钩子。
2. [`antifomo-overview.mp4`](./assets/marketing/antifomo-overview.mp4)：15 秒历史本地 Demo 截图剪辑，与 GIF 同源。
3. `/`、`/inbox`、`/research/compare`、`/knowledge/accounts` 的真实界面截图。
4. [架构与数据流](./diagrams/architecture.mmd)及 SVG 图。
5. [价值地图](./value-map.md)和 [WorkBuddy 深度对标](./workbuddy-deep-dive-2026-09-18.md)。

所有素材的日期、来源、viewport、hash 和 claim boundary 维护在 [`docs/marketing/asset-manifest.json`](./marketing/asset-manifest.json)。
