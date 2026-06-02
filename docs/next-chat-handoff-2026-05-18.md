# Anti-FOMO Next Chat Handoff - 2026-05-18

This document is the compressed project context for opening a new chat window.
It captures the necessary repository state, recent decisions, implementation
history, key files, validation status, and recommended next steps.

## New Chat Starter Prompt

Use this prompt in the next chat:

```text
请继续开发 /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo 这个项目。

项目名：Anti-FOMO。
当前版本：0.8.0+20260518。
当前 Git 状态：main 已同步 origin/main，HEAD 为 f7bdd6d，远端标签 v0.8.0+20260518 已推送。
工作语言：中文沟通，代码与文档按项目现有风格维护。

请先阅读 docs/next-chat-handoff-2026-05-18.md 获取完整上下文，再继续下一版本迭代。不要提交 backend/anti_fomo_demo.db.before-entity-quality-20260502-021530，这是本地数据库备份。

下一阶段产品重点：继续提升“解决方案架构师 / 行业咨询顾问”相关能力质量，把公开信号和研报进一步转成客户可讨论的方案架构、集成依赖、非功能要求、决策依据、验证动作和交付材料。
```

## Repository State

- Repository path: `/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo`
- Branch: `main`
- Current HEAD: `f7bdd6d Release 0.8.0 solution architecture readiness`
- Current tag on HEAD: `v0.8.0+20260518`
- Remote state confirmed:
  - `origin/main` points to `f7bdd6d2c1bca85635d9ce57cd22ec0d84e5d5dc`
  - remote tag `v0.8.0+20260518` exists
- Current `package.json` version: `0.8.0+20260518`
- Screenshot manifest version: `0.8.0+20260518`
- Screenshot manifest accepted count: `15`
- Untracked local file to preserve and not commit:
  - `backend/anti_fomo_demo.db.before-entity-quality-20260502-021530`

## Product Positioning

Anti-FOMO is an open-source AI research workspace for turning noisy web and
WeChat-heavy information flows into evidence-backed reports, solution
architecture blueprints, focus sessions, and action-ready follow-up.

The newest positioning should emphasize:

- solution architects
- industry consultants
- pre-sales / BD / strategy teams
- evidence-backed research
- architecture readiness
- architecture blueprint layers
- integration risks
- non-functional requirements
- stakeholder questions
- validation actions
- client-ready advisory delivery

Avoid describing the product as only a bookmark manager, generic AI summarizer,
or simple reading-later queue. The product story is a research-to-delivery loop.

## Important Historical Decisions

### Focus Mode and WeChat Collection

The user raised concern that focus mode did not reliably fetch the daily full
set of updates from followed WeChat official accounts.

The working direction chosen in prior iterations:

- Do not make headless browser crawling the default primary path for all target
  article collection.
- Treat headless browser collection as a possible fallback or audit tool for
  selected source pages, because it has operational risks around login state,
  anti-automation behavior, resource cost, stability, and compliance.
- Improve reliability first through source-level health and omission diagnosis,
  so the product can identify which official-account source is failing instead
  of only showing a total coverage rate.
- The 0.7.0 release focused on collector reliability and source-page health.

### 0.8.0 Product Focus

The user then shifted the next major version toward a visible quality upgrade
for solution-architect workflows. The 0.8.0 release added architecture readiness
and architecture blueprint output to solution delivery packs.

## Recent Release History

- `v0.8.0+20260518`
  - Commit: `f7bdd6d Release 0.8.0 solution architecture readiness`
  - Focus: solution architecture readiness for solution architects and industry
    consultants.
  - Added readiness scoring, architecture blueprint sections, non-functional
    requirements, integration risks, assumptions, stakeholder questions, and
    validation actions.

- `v0.7.0+20260518`
  - Commit: `7143dc8 Release 0.7.0 collector reliability update`
  - Focus: collector reliability and source-level health / omission diagnosis.

- `v0.6.10+20260514`
  - Commit: `473039d feat(research): inject runtime strategies into report generation`
  - Focus: runtime experiment strategy injection into report generation.

## 0.8.0 Implementation Summary

### Backend

Key changed files:

- `backend/app/schemas/research.py`
- `backend/app/services/research_solution_intelligence_service.py`

Main schema additions:

- `ResearchSolutionArchitectureBlueprintSectionOut`
- `ResearchSolutionArchitectureReadinessOut`
- `architecture_readiness` on `ResearchSolutionDeliveryPackOut`

Main service additions:

- Architecture readiness scoring.
- `build_solution_architecture_readiness(report, market_pack, pack)`.
- Readiness dimensions:
  - business alignment
  - architecture completeness
  - integration readiness
  - security / compliance
  - delivery feasibility
- Blueprint sections:
  - 业务与角色层
  - 应用能力层
  - 模型、数据与集成层
  - 安全、部署与运维层
- Additional generated fields:
  - non-functional requirements
  - integration risks
  - assumptions
  - validation actions
  - stakeholder questions

Markdown export now includes:

- `## 解决方案架构就绪度`
- `### 架构蓝图`
- integration risks
- validation actions

### Frontend

Key changed files:

- `src/lib/api.ts`
- `src/components/inbox/research-report-card.tsx`

API types added:

- `ApiResearchSolutionArchitectureBlueprintSection`
- `ApiResearchSolutionArchitectureReadiness`
- optional `architecture_readiness` on `ApiResearchSolutionDeliveryPack`

UI additions:

- Solution architecture readiness panel in the research report delivery-pack
  surface.
- Shows readiness score / status, dimension metrics, blueprint sections,
  integration risks, and validation actions.

### Tests

Key changed files:

- `backend/tests/test_research_solution_intelligence_service.py`
- `backend/tests/test_research_solution_delivery_exports.py`

Assertions cover:

- architecture readiness score
- blueprint sections
- model/data/integration layer
- non-functional requirements
- validation actions
- markdown export chapter

### Documentation and Marketing

Updated files:

- `README.md`
- `README.zh-CN.md`
- `CHANGELOG.md`
- `docs/product-whitepaper.md`
- `docs/open-source-launch-kit.md`
- `docs/open-source-growth-copy.md`
- `docs/release-history-and-feature-map.md`
- `docs/feature-screenshot-coverage.md`
- `docs/version-iteration-plan-2026-04-23.md`

Main content change:

- The public product story now explicitly speaks to solution architects and
  industry consultants.
- 0.8.0 is documented as a solution architecture release.
- Open-source launch and growth copy now describes Anti-FOMO as a workspace
  that converts noisy signals into evidence-backed research, architecture
  blueprints, and advisory delivery outputs.

### Screenshots

Updated screenshot-related files:

- `scripts/capture_repo_screenshots.mjs`
- `docs/assets/screenshots/home-signal-dashboard.png`
- `docs/assets/screenshots/research-center-dashboard.png`
- `docs/assets/screenshots/research-experiment-control-plane.png`
- `docs/assets/screenshots/screenshot-manifest.json`

Screenshot manifest:

- version: `0.8.0+20260518`
- accepted screenshots: `15/15`

## Validation Already Completed

The following checks were completed successfully during the 0.8.0 release:

```bash
python3 -m py_compile backend/app/schemas/research.py backend/app/services/research_solution_intelligence_service.py backend/app/services/research_delivery_quality_service.py
backend/.venv311/bin/pytest -q backend/tests/test_research_solution_intelligence_service.py backend/tests/test_research_solution_delivery_exports.py backend/tests/test_research_evaluation_service.py
npx eslint src/components/inbox/research-report-card.tsx src/lib/api.ts
node --check scripts/capture_repo_screenshots.mjs
git diff --check
npm run build
npm run repo:screenshots
npm run demo:smoke
npm run test:backend
npm run lint
```

Recorded results:

- targeted backend tests: `6 passed`
- full backend tests: `258 passed`
- screenshot capture: `15/15`
- build: passed
- lint: passed
- smoke: passed

## Useful Commands

From repository root:

```bash
npm run build
npm run lint
npm run test:backend
npm run repo:screenshots
npm run demo:smoke
```

Development servers used previously:

```bash
npm run demo:backend
npm run dev
```

Notes:

- Backend typically uses port `8000`.
- A frontend server on port `3010` existed during prior work and was left
  untouched if it was already running.
- If checking backend port:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN || true
```

## Key File Map

Backend research and delivery logic:

- `backend/app/services/research_solution_intelligence_service.py`
- `backend/app/services/research_delivery_quality_service.py`
- `backend/app/services/research_evaluation_service.py`
- `backend/app/schemas/research.py`

Backend tests:

- `backend/tests/test_research_solution_intelligence_service.py`
- `backend/tests/test_research_solution_delivery_exports.py`
- `backend/tests/test_research_evaluation_service.py`

Frontend API and report UI:

- `src/lib/api.ts`
- `src/components/inbox/research-report-card.tsx`

Screenshot automation:

- `scripts/capture_repo_screenshots.mjs`
- `docs/assets/screenshots/screenshot-manifest.json`

Primary product docs:

- `README.md`
- `README.zh-CN.md`
- `CHANGELOG.md`
- `docs/product-whitepaper.md`
- `docs/open-source-launch-kit.md`
- `docs/open-source-growth-copy.md`
- `docs/release-history-and-feature-map.md`
- `docs/feature-screenshot-coverage.md`
- `docs/version-iteration-plan-2026-04-23.md`

## Recommended Next Version Direction

Suggested next major theme: `0.9.0 Solution Architect Workbench`.

The goal should be to move beyond "architecture readiness exists" toward a
more complete architecture-consulting workflow.

High-value next features:

1. Customer scenario and stakeholder mapping
   - Convert research findings into customer scenarios, roles, pain points,
     objections, and decision criteria.

2. Capability-to-architecture matrix
   - Map business capabilities to application services, data dependencies,
     model dependencies, integration surfaces, and security constraints.

3. Architecture decision record generation
   - Generate ADR-style decisions with context, options, tradeoffs, selected
     direction, risks, and validation evidence.

4. Integration dependency diagnostics
   - Expand integration risks into source systems, APIs, data contracts,
     auth boundaries, deployment assumptions, and operational owners.

5. Consultant-ready export pack
   - Export a concise advisory pack with executive framing, architecture
     blueprint, decision table, phased roadmap, risks, and next meeting agenda.

6. UI quality pass for architect workflows
   - Add a dedicated architecture section or tab in the research/report surface
     so architects can scan blueprint, risks, assumptions, and decisions without
     reading the full report.

7. Evidence traceability
   - Link each architecture recommendation back to source excerpts, report
     findings, market signals, or collector evidence.

## Implementation Constraints for Future Work

- Preserve existing project patterns before adding abstractions.
- Keep manual edits via `apply_patch`.
- Do not revert unrelated user changes.
- Do not commit local DB backups.
- Prefer targeted tests first, then broader validation when touching shared
  research/delivery code.
- Continue updating docs, screenshots, release notes, and marketing copy when a
  version is completed.
- When user asks to sync GitHub, commit, tag, push `main`, and push the version
  tag.

## Current Open Risk / Watch Item

GitHub connectivity was intermittent during the final 0.8.0 push, but the final
state was verified:

- `origin/main` has the 0.8.0 commit.
- remote tag `v0.8.0+20260518` exists.

If future remote commands hang, retry after a short delay and verify with:

```bash
git ls-remote --heads origin main
git ls-remote --tags origin 'v0.8.0+20260518'
```

