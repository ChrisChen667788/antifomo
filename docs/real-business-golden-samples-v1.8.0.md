# Real-business golden samples for 1.8.0

Updated: 2026-06-20

Purpose: use source-backed real business topics to validate P0.3 semantic
challenger, P1.1 document compilers, and P1.2 quantitative decision model
before entering P2 formal delivery engineering.

Dataset:

- `backend/evaluation/real_business_delivery_golden_v1.json`
- Dataset ID: `anti-fomo-real-business-delivery-golden-v1`
- Status: `draft_for_blind_review`
- Execution mode: deterministic, no live model call, no paid evaluation.

Registered semantic-challenger samples:

- `backend/evaluation/delivery_golden_samples_v1.json`
- Version: `1.1.0`
- Added IDs:
  - `shanghai-medical-ai-2026`
  - `shanghai-culture-tourism-ai-2026`
  - `yangtze-delta-gov-ai-2026`

## Topic 1: 2026 上海市医疗行业 AI 需求与潜在商机

Source basis:

- 上海市发展医学人工智能工作方案（2025—2027年）
  - `https://www.shanghai.gov.cn/nw12344/20241224/0f60c01551784720899dbb911e9d5f08.html`
- 卫生健康行业人工智能应用场景参考指引
  - `https://www.nhc.gov.cn/guihuaxxs/c100133/202411/3dee425b8dc34f739d63483c4e5c334c/files/1733227133524_47343.pdf`
- 国家数字经济创新发展试验区（上海）实施方案
  - `https://www.shanghai.gov.cn/nw12344/20260421/9edf5d5c1b2244298c315304349d0963.html?siteId=1`
- “人工智能+医疗健康”推进会暨医学 AI 赛事在徐汇举行
  - `https://wsjkw.sh.gov.cn/gzdt1/20250519/c9b2d912b30845d0b8ed3e4bf1d9127d.html`

Validated opportunity hypotheses:

- Medical data governance, privacy computing, and high-quality health datasets.
- Clinical decision-support knowledge base.
- Medical imaging diagnosis and quality-control assistant.
- Smart follow-up, discharge management, smart pharmacy, and patient service automation.
- Medical AI pilot, testing, validation, and application sandbox.

P1.2 finance rule:

- Public sources do not disclose project amount. The model must remain
  `assumption_required` and leave CAPEX/NPV/IRR/ROI empty until procurement,
  budget, or customer-confirmed finance inputs are available.

## Topic 2: 2026 上海市文旅行业 AI 需求与潜在商机

Source basis:

- 上海市文旅局关于组织推荐“人工智能+文化和旅游”应用试点的通知
  - `https://whlyj.sh.gov.cn/zw-hwlf2026/20260327/2c28168841224f419a0498e04091f6a3.html`
- AI 如何重塑微短剧生产？2026 上海微短剧大会在沪举行
  - `https://www.shanghai.gov.cn/nw31406/20260311/78858c166b0944faafafe03f5cd48228.html`
- “科技+”激发文旅消费潜力
  - `https://www.news.cn/20251230/b91293e4a1394515bfcb94a9bb4eb03f/c.html`

Validated opportunity hypotheses:

- Cultural-tourism data collection, labeling, quality control, and dataset construction.
- Smart guide, itinerary planning, ticket booking, translation, digital human, and robot service.
- AIGC micro-drama and cultural-content production service.
- Cultural heritage preservation and public cultural knowledge Q&A.
- Tourism market supervision, risk warning, complaint analysis, and emergency response.

P1.2 finance rule:

- Pilot notice gives direction and tasks, not project amount. The model must keep
  finance outputs as assumptions and require budget/procurement follow-up.

## Topic 3: 2026 长三角政府行业 AI 需求与潜在商机

Source basis:

- 上海市促进长三角政务服务“一网通办”规定
  - `https://www.shanghai.gov.cn/nw12344/20260401/b83261592788473788f20e95dc2ec690.html`
- 江苏省促进长三角政务服务“一网通办”规定
  - `https://www.jsrd.gov.cn/qwfb/sjfg/202604/t20260409_1321590.shtml`
- 2026 年度长三角地区主要领导座谈会在上海举行
  - `https://cgzf.sh.gov.cn/channel_8/20260525/2bdaa60eb2cd4b94ab842fabe22f6db5.html`
- 上海持续深化“一网通办”改革
  - `https://www.ssme.sh.gov.cn/public/news%21loadNewsDetail.do?id=2c9e88329daff4c7019e29b16ba00794`

Validated opportunity hypotheses:

- Cross-province service standardization and workflow orchestration.
- Electronic certificate, e-seal, and e-signature mutual recognition.
- Government data-sharing catalogs, trusted knowledge bases, corpus construction, and compute support.
- Intelligent guidance, intelligent pre-fill, intelligent assisted handling, and staff copilot.
- 12345 / satisfaction feedback analytics and cross-region service-effectiveness monitoring.

P1.2 finance rule:

- Regulations and reform updates do not disclose project amount. Finance outputs
  stay assumption-based until platform-upgrade or procurement sources appear.

## Current validation result

Targeted tests:

```text
backend/tests/test_real_business_delivery_golden_samples.py
backend/tests/test_delivery_golden_samples.py
backend/tests/test_delivery_semantic_challenger.py
backend/tests/test_delivery_solution_materials.py
backend/tests/test_research_solution_intelligence_service.py
```

Result: `14/14` passed.

Full local verification:

- `npm run check` passed:
  - ESLint passed.
  - Frontend tests passed `16/16`.
  - Next production build passed.
  - Backend tests passed `335/335`.
- Historical low-quality audit remained on the old baseline: `20/66` flagged.
  - JSON: `/tmp/af-quality-audit-v180-real-golden.json`
  - Markdown: `/tmp/af-quality-audit-v180-real-golden.md`
- `git diff --check` passed.

What is validated:

- The three real-business samples are source-backed and registered in semantic
  challenger golden samples.
- Policy-only sources no longer create fake tender projects.
- P1.1 compilers produce four document kinds for all three themes.
- P1.2 produces weighted alternatives and three finance scenarios.
- Because the public sources do not include project amount, P1.2 correctly keeps
  finance status as `assumption_required`.
- P0.3 golden alignment matches the expected sample IDs and has no high-severity
  scope drift.

Known limitation before client-ready use:

- The semantic challenger still reports medium-severity unsupported-claim issues
  for some generated generic claims. This is acceptable for the P2 gate: the
  samples are usable for regression, but full client-ready golden documents still
  need manual evidence anchoring and expert blind review.
