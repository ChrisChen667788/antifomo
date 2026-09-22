# README 主视觉与 Star 趋势更新

日期：2026-09-10。范围：中英文 README 的品牌展示与社区趋势；不升级软件版本，不代表功能、客户或生产验收。

## 交付

- 主视觉：[github-hero-20260910.png](./assets/github-hero-20260910.png)。原创概念宣传图，不是真实界面截图。
- 布局：开篇主视觉下放快速开始、产品截图、路线图和社区入口；真实功能截图保持独立。
- Star：README 最下方嵌入 Star History 明暗主题 SVG；无第三方令牌、无新增依赖。接口当前返回有效 SVG，缓存约 24 小时，外部服务不可用时仍保留可点击的详情入口。
- 旧版 SVG/PNG 保留，避免破坏既有引用。

## 设计判断与参考

| 参考 | 采用的原则 | 本项目处理 |
| --- | --- | --- |
| [Dify README](https://github.com/langgenius/dify/blob/main/README.md) | 开篇品牌识别、短主张、清楚的下一步入口 | 大标题和一句核心价值，不挤入版本表、指标或宣传徽章 |
| [RAGFlow README](https://github.com/infiniflow/ragflow/blob/main/README.md) | 品牌呈现与实际功能演示分层 | 概念图和真实截图分开，避免误认功能验收证据 |
| [Impeccable](https://github.com/pbakaus/impeccable) | 以产品语境驱动视觉，检查层级、对比度、留白和模板化装饰 | 采用“信息经透镜形成有迹可循的研究”的单一视觉隐喻 |
| [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | 明确字体与构图意图，保持克制并做视觉复查 | 矿物白、深海军蓝、低饱和青绿、少量金属反光；大字和一致的左对齐 |
| [Star History 官方嵌入说明](https://www.star-history.com/blog/how-to-use-github-star-history/#how-to-embed-the-chart-in-your-readme) | GitHub 支持的 picture 明暗主题图表 | 使用项目自己的公开仓库参数，未复制其他项目的 token 或数据 |

上述项目和远程 skill 仅作为设计研究参考，未安装或执行第三方 skill/CLI，未复制其品牌资产。主视觉使用内置 imagegen 生成，未调用项目配置的付费模型 API。图中不包含用户数、性能、独立验收或生产可用性主张。

## 生成提示词

执行方式：内置 imagegen；单张新图。以下保存本次完整提示词，便于后续迭代。素材已复制到仓库，不依赖本机生成缓存路径。

```text
Use case: ads-marketing.
Asset type: polished wide GitHub README product hero for the open-source project Anti-FOMO, landscape aspect ratio 2.4:1, approximately 2400 x 1000. This is a conceptual brand illustration, NOT a real app screenshot.
Primary request: Create a distinctive, premium product launch graphic for an evidence-aware AI research workspace that turns noisy web/WeChat inputs into traceable research, comparison, and considered decisions. Audience: solution architects, consultants, pre-sales, and builders. The emotion is clarity, intellectual confidence, and calm focus.
Art direction: a precise editorial identity combined with exceptionally crafted photographic 3D materials. Chalk-white / cool mineral background (#F3F6F4), deep navy ink (#121C34) typography, muted petrol teal (#0B8B78), a restrained champagne edge reflection (#C5AD86). No purple-blue neon gradients. Generous breathing room. Sharp hierarchy and deliberately asymmetric composition.
Composition: left 46 percent dedicated to typography with a consistent left edge and large readable words. Right 54 percent features ONE memorable sculptural optical object: a beautiful thick optical-glass lens/prism in an understated brushed titanium circular frame. A small cloud of fine, loosely scattered ink-blue source marks and thin paper fragments enters from its upper-left side; on its right, the same information resolves into three exquisitely aligned translucent vellum research sheets with precise citation-dot and line patterns. Subtle thin evidence connection lines, physically plausible refraction, soft daylight and grounded shadows. No laptop, phone, fake dashboard, stacked generic SaaS cards, robots, brains, sparkles, or corporate logos. This should look designed for an evidence-research product, not generic AI clip art.
Typography: bold yet restrained contemporary humanist grotesk, very large Anti-FOMO logotype at top left, a smaller two-line headline below, comfortable leading, crisp ink color. Bottom left small clear bilingual descriptor. Do not place type over the sculpture.
Text to reproduce exactly, with no other invented words:
"Anti-FOMO"
"From noise"
"to informed decisions."
"让信息成为有据可循的判断"
"Collect / Research / Compare / Act"
Constraints: all text must be accurate and comfortably readable when the image is displayed at 850px wide; 70px minimum large headline in a 2400px image, no tiny annotations. The two headline lines must have uniform color and weight. Keep 80px safe margins on every side. No statistics, star counts, performance claims, certifications, production-ready claims, fake charts, screenshot chrome, watermarks, competitor styling, or imitation trademarks. Create an original and finished high-end README banner.
```
