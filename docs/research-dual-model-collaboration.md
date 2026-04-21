# Research Dual-model Collaboration

This project now uses a dual-model strategy for research generation:

- `claude-opus-4-6`
  - main long-form synthesis
  - section drafting
  - structured report generation
- `gpt-5.4` via TabCode
  - pre-retrieval scope planning
  - post-draft strategy refinement
  - title / executive summary / consulting-angle correction

## Why

`Opus 4.6` is strong at broad synthesis, but it can drift when the user gives narrow regional or thematic constraints.
`gpt-5.4` is used as a higher-priority strategy layer to lock scope and audit the draft before the final report is returned.

## Runtime flow

1. Engineering scope extraction
   - Parse explicit regions, industries, companies from keyword and research focus.
2. `gpt-5.4` scope planner
   - Prompt: `backend/app/prompts/research_strategy_scope.txt`
   - Output:
     - locked regions / industries / clients
     - must-include terms
     - must-exclude terms
     - extra query expansions
3. Retrieval and filtering
   - Engineering rules remain the hard gate.
   - Region conflict filtering and theme scoring still clamp the result set.
4. `claude-opus-4-6` draft generation
   - Prompt: `backend/app/prompts/research_report.txt`
5. `gpt-5.4` refinement/audit
   - Prompt: `backend/app/prompts/research_strategy_refine.txt`
   - Refines:
     - report title
     - executive summary
     - consulting angle
6. Engineering post-check
   - Scope diagnostics
   - entity graph normalization
   - ranked entity generation

## Cross-validation policy

- If `gpt-5.4` is unavailable:
  - pipeline falls back to engineering rules + `Opus 4.6`
- If `gpt-5.4` provides expansions/exclusions:
  - they are advisory until engineering filters validate them
- If `Opus 4.6` draft drifts outside scope:
  - `gpt-5.4` can rewrite title / summary / consulting angle
  - engineering filters still control retained evidence

## Config

Main report model:
- `OPENAI_BASE_URL=https://vip.aipro.love/v1`
- `OPENAI_MODEL=claude-opus-4-6`

Strategy model:
- `STRATEGY_OPENAI_BASE_URL=https://api2.tabcode.cc/openai`
- `STRATEGY_OPENAI_MODEL=gpt-5.4`

## Diagnostics

`source_diagnostics` now exposes:
- `strategy_model_used`
- `strategy_scope_summary`
- `strategy_query_expansion_count`
- `strategy_exclusion_terms`
