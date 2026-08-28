# Research Clarification and Progressive Disclosure Roadmap

Updated: 2026-08-13

Baseline: `2.9.5+20260814`

Status: engineering implementation complete locally; real-task, customer, Office, visual, security, performance, recovery, and release-candidate acceptance remains blocked.

## 1. Problem Diagnosis

The current research flow protects formal deliverables with a fail-closed evidence gate, but it exposes that internal control mechanism directly to end users.

The screenshot and current implementation show four concrete gaps:

1. `generation_workflow.py` returns an evidence-gap report before formal report generation when the evidence gate fails. This correctly protects formal output, but it also prevents a safe evidence-bounded working draft when the run is only narrowly below threshold.
2. `ResearchEvidenceGateOut` provides technical blockers and free-text `next_actions`, but it does not provide a structured clarification packet, answer types, recovery choices, or a resumable continuation contract.
3. The existing supplement form can restart a report, but it is placed after the long report card, is not populated from the actual missing evidence axes, and does not preserve an explicit parent/child recovery lineage.
4. The default report surface renders implementation terms such as version numbers, `evidence_gap`, reranker, scope gate, source-admission internals, and citation-gate counters. These are useful for operators, but they obscure the user's outcome and next action.

For the pictured case, 7 of 8 required sources were accepted, while official-source, independent-domain, and question-coverage thresholds already passed. The desired outcome is not a blank or terminal failure. It should be:

- a clearly labeled evidence-bounded working draft;
- an automatic attempt to find the missing source within a bounded budget;
- one focused request for user input if automatic recovery still fails;
- formal export kept disabled until the existing hard gates pass.

## 2. Product Principles

1. Hard evidence gates protect formal delivery, not useful interaction. A failed formal gate may still permit a bounded working draft composed only from accepted evidence.
2. The system repairs what it can before asking the user. Search retries, snapshot reuse, query expansion, and source deduplication run before clarification.
3. Ask only for information that is high-impact or user-exclusive. Limit one clarification turn to at most three questions.
4. Every question explains why it matters and what changes after it is answered.
5. Preserve accepted work. A continuation reuses the accepted-source snapshot and rebuilds only affected questions, claims, and sections.
6. User-provided material retains provenance as `user_supplied`; it is never silently promoted to an official source.
7. Default UI shows outcomes, confidence, evidence, and next actions. Internal pipeline diagnostics remain available in an advanced drawer or operator view.
8. Do not expose hidden model deliberation or chain-of-thought. User-facing rationale must be a concise, structured explanation derived from evidence and gate results.
9. Runtime degradation is a system problem. Do not ask the user to fix rerankers, adapters, or search infrastructure.

## 3. Target Interaction States

Keep the existing internal evidence and citation gates, but add a stable user-facing interaction state:

| Interaction state | User meaning | Product behavior |
| --- | --- | --- |
| `ready` | The report is supported enough for the selected delivery level | Show final report and permitted exports |
| `provisional` | A useful draft exists, but one or more formal checks remain | Show accepted findings and uncertainties; disable formal export |
| `awaiting_user` | The system needs a small amount of specific input | Show a guided clarification card with at most three questions |
| `recovering` | The system can continue searching or retrying by itself | Show retained progress, recovery budget, and cancel control |
| `system_degraded` | Search/model infrastructure failed | Offer retry and preserve the prior snapshot; do not blame the user |
| `blocked` | Topic mismatch, safety, permission, or unrecoverable hard failure | Explain the boundary in plain language and offer a safe restart path |

The database job status can remain backward compatible initially. The API should expose `interaction_state` separately so the frontend does not infer user experience from low-level gate enums.

## 4. Recovery Decision Policy

### 4.1 Automatic recovery first

Before requesting user input, run a bounded recovery policy:

- reuse the newest compatible accepted-source snapshot;
- execute only uncovered-question corrective queries;
- retry public search with deterministic query compaction;
- cap recovery at two rounds, six additional queries, and the active run's remaining time/cost budget;
- stop early when the gate passes or no new independent domain is found.

### 4.2 Safe provisional draft

A provisional draft may be generated only when all of the following hold:

- accepted sources are at least 75% of the minimum and no more than one source below the minimum;
- official-source, independent-domain, and question-coverage thresholds pass;
- there is no topic mismatch, permission failure, runtime degradation, entity-authenticity hard failure, or unsupported critical buyer claim;
- every emitted claim is built only from accepted sources and still passes the claim/citation checks;
- formal DOCX, PDF, PPTX, solution, feasibility-study, and project-proposal exports remain disabled.

This policy covers the pictured 7/8 case without weakening release evidence.

### 4.3 Clarification instead of terminal failure

After automatic recovery, generate a structured clarification packet for unresolved high-impact gaps:

- ambiguous scope: region, industry, scenario, time range, or output type;
- unknown subject: target customer, buyer, owner, competitor, or partner;
- missing private context: internal budget, meeting note, project phase, current vendor, or delivery constraint;
- inaccessible evidence: URL, file, screenshot, policy, tender, contract, or user authorization;
- output choice: continue searching, submit evidence, narrow scope, or view a provisional draft.

Low-impact public-source shortages should default to `continue_search`; missing user-exclusive business context should default to `awaiting_user`.

## 5. Backend and API Contract

Add a report/job-level `ResearchClarificationPacketOut`:

```text
status
reason_type
summary
questions[]
  question_id
  field_key
  prompt
  why_needed
  answer_type
  required
  options[]
  examples[]
  affected_axes[]
  expected_effect
accepted_snapshot_digest
recovery_options[]
recommended_action
expires_at
```

Supported answer types:

- `single_choice`
- `multi_choice`
- `short_text`
- `organization`
- `region`
- `date_range`
- `url_list`
- `file_upload`
- `long_text`

Implemented endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/research/jobs/{job_id}/clarification` | Load the current structured clarification packet |
| `POST /api/research/jobs/{job_id}/clarification` | Submit answers, URLs, files, or a selected recovery action |
| `POST /api/research/jobs/{job_id}/experience-feedback` | Record user experience feedback without changing the report |
| `GET /api/research/experience/metrics` | Aggregate clarification, provenance, recovery, feedback, and bypass metrics |
| `GET /api/research/experience/readiness` | Evaluate the human-in-the-loop release gate |

Continuation requirements:

- immutable `parent_job_id` and `accepted_snapshot_digest`;
- idempotency key for every resume request;
- source and answer provenance;
- affected-question and affected-section list;
- retained-source count and newly admitted-source count;
- no duplicate billing or duplicate side effects after retry;
- audit event for every user answer, source admission, and gate transition.

Reuse the existing Decision Program research-run checkpoints and pause/resume semantics instead of creating a second unrelated run-control system.

## 6. Frontend Information Architecture

### 6.1 Default user layer

The default report surface should show, in this order:

1. outcome: `可交付`, `可查看草稿`, `需要你补充`, or `系统正在继续查找`;
2. one-sentence summary of what is already known;
3. the highest-impact missing input;
4. one primary action and at most two secondary actions;
5. confirmed findings, uncertainties, and source links;
6. the full report when available.

For `awaiting_user`, render a `ResearchRecoveryCard` immediately above the report:

- "已经完成什么";
- "还缺什么";
- one to three generated questions;
- answer controls matched to each question type;
- paste URL, upload file, or add text;
- primary action: `提交补充并继续`;
- secondary actions: `继续自动查找` and `先看当前草稿`;
- explicit notice that accepted sources and completed work will be retained.

### 6.2 Evidence explanation layer

An expandable `为什么还不能正式导出` section may show:

- missing evidence categories;
- accepted and missing source counts in plain language;
- which conclusions remain uncertain;
- what evidence would unlock the formal report;
- adopted and unadopted source links.

### 6.3 Operator diagnostics layer

Move these items out of the default report body:

- implementation version labels such as `1.8.2 / 1.8.3`;
- raw enums such as `evidence_gap`;
- reranker and scope-gate implementation notes;
- raw rejected-source reason lists;
- claim-gate counters and runtime lane warnings;
- pipeline query plans and internal threshold details.

They remain available behind `查看技术诊断`, with operator/admin visibility and a copyable diagnostic bundle.

### 6.4 Plain-language terminology

| Internal term | Default user copy |
| --- | --- |
| `evidence_gap` | 还需要补充资料 |
| formal report blocked | 暂不能生成正式交付稿 |
| scope gate | 研究范围核对 |
| citation gate | 结论出处检查 |
| rejected source | 未采用的资料 |
| reranker degraded | 搜索服务暂时异常，系统可重试 |
| question coverage | 关键问题覆盖情况 |
| source admission | 可用于本报告的资料 |

## 7. Incremental Resume Flow

1. Freeze accepted sources and the current question tree.
2. Convert user answers into typed scope updates, assumptions, or user-supplied evidence.
3. Validate URLs/files and retain origin, author, timestamp, and trust tier.
4. Re-run only missing or affected question nodes.
5. Re-evaluate source admission, entity authenticity, claim citations, and hard failures.
6. Rebuild only affected report sections.
7. Present a concise delta: new sources, changed conclusions, remaining gaps, and newly enabled exports.

User statements such as budget expectations or internal project status are assumptions or internal evidence until independently verified. They must not become public facts.

## 8. Planned Version Integration

| Version | Priority | Delivery scope | Required acceptance gate |
| --- | --- | --- | --- |
| `2.2.1` | P0 | Evidence Recovery Contract: interaction-state taxonomy, bounded auto-recovery, near-threshold provisional output, structured clarification packet, and fail-safe export policy | On at least 60 cross-industry evidence-gap cases, 100% return one of auto-recovery, provisional output, or actionable clarification; blank terminal output = 0; formal-gate bypass = 0 |
| `2.2.2` | P0 | Guided Clarification and Resume: typed questions, URL/file/text supplementation, accepted-snapshot reuse, idempotent continuation, parent/child lineage, delta rebuild, and audit | At least 95% of clarification answers map to the intended scope/evidence field; accepted-source preservation = 100%; duplicate effects = 0; user-supplied provenance = 100% |
| `2.2.3` | P0 UX | Progressive Disclosure Research UI: recovery card, result-first report layout, plain-language status mapping, advanced diagnostics drawer, mobile and keyboard completion | Default UI exposes zero raw internal enums/version/reranker/scope-gate terms; at least 90% of usability participants identify the next action without assistance; desktop/mobile visual and accessibility gates pass |
| `2.3.0` | P0 release closure | Human-in-the-loop Research Experience RC: preflight clarification, post-search recovery, resumable report updates, telemetry, experiments, and release-readiness aggregation | At least 120 real tasks across government, healthcare, finance, tourism, education, and manufacturing; evidence-gap-to-usable conversion >=75%; median clarification questions <=3; abandonment improves >=30%; unsupported critical claims and gate bypasses = 0 |
| `2.3.1` | P0 operations | Clarification Quality and Operations: feedback capture, stale-recovery monitoring, idempotent replay audit, provenance/bypass metrics, system-degraded retry, and global release-readiness integration | At least 30 human feedback records; average score >=4.0/5; technical-copy feedback <=10%; stale recovery <=15%; formal-gate bypass and missing provenance = 0 |

Engineering status on 2026-07-26:

- `2.2.1`: implemented locally; 60-case cross-industry acceptance remains blocked.
- `2.2.2`: implemented locally; real clarification mapping and source-preservation acceptance remains blocked.
- `2.2.3`: implemented locally; desktop/mobile human visual and accessibility confirmation remains blocked.
- `2.3.0`: instrumentation and readiness gate implemented; 120 real tasks across at least three industry buckets remains blocked.
- `2.3.1`: feedback and operations metrics implemented; 30 human feedback records and customer acceptance remains blocked.

These statuses do not override the existing independent expert, customer, Office, visual, security, performance, recovery, or release-candidate blockers.

## 9. Test and Evidence Plan

Backend tests:

- clarification reason taxonomy and question ranking;
- automatic-recovery budget and stop conditions;
- provisional eligibility positive and hard-negative cases;
- user-supplied evidence provenance and trust-tier enforcement;
- parent/child snapshot integrity and idempotent resume;
- affected-section-only rebuild;
- no formal export when evidence or citation gates fail.

Frontend tests:

- each interaction state and action path;
- question-type controls, upload/URL/text errors, retry, and cancellation;
- default UI contains no internal enums or version labels;
- technical diagnostics remain complete in advanced mode;
- keyboard navigation, focus order, screen-reader labels, mobile wrapping, empty/loading/error states;
- light/dark visual baselines for ready, provisional, awaiting-user, recovering, and system-degraded states.

Real-task evaluation:

- balanced six-industry corpus, including broad and underspecified prompts;
- one-source-short, no-official-source, no-buyer, topic-mismatch, inaccessible-private-source, and runtime-degraded cases;
- measure clarification completion, recovery conversion, time to next action, abandonment, answer-field accuracy, source preservation, and final claim support.

Privacy and telemetry:

- record state transitions, selected actions, completion time, and error class;
- do not log raw private documents, user answers, credentials, or hidden model prompts in product analytics;
- retain detailed audit evidence only in the governed project space with existing ACL and retention controls.

## 10. Non-Goals

- Do not lower evidence, citation, entity, permission, or formal-document gates to improve completion metrics.
- Do not present assumptions as verified facts.
- Do not expose chain-of-thought or internal prompts.
- Do not retry public search without a time, query, and cost limit.
- Do not build a separate chat platform; extend the existing research conversation, inbox report, and Decision Program run controls.
- Do not mark `2.2.0` or any later version release-ready from generated fixtures or automated UI tests alone.

## 11. Local Implementation Evidence

Primary implementation:

- `backend/app/services/research/clarification.py`
- `backend/app/services/research/supplemental_sources.py`
- `backend/app/services/research/source_snapshot_recovery.py`
- `backend/app/services/research/generation_workflow.py`
- `backend/app/services/research_job_store.py`
- `backend/app/services/research_experience_service.py`
- `backend/alembic/versions/20260726_0029_add_research_clarification_recovery.py`
- `src/components/inbox/research-recovery-card.tsx`
- `src/components/inbox/research-experience-feedback.tsx`
- `src/components/inbox/research-report-sources-diagnostics-section.tsx`

Automated evidence:

- backend suite: `565 passed`;
- frontend suite: `31 passed`;
- frontend lint: passed;
- Next.js production build: passed;
- migration: local SQLite stamped at `20260718_0028` after structural verification, upgraded to `20260726_0029`;
- local database backup: `backend/.tmp/anti_fomo_demo.pre-2.3.1-20260726.db`.
- real local `7/8` evidence-gap job: recovery card rendered on desktop and `390x844` mobile without root horizontal overflow; sticky-header scroll clearance passed;
- formal action-plan API guard: the provisional report returned HTTP `409`;
- default result layer: formal save/export controls are disabled, advanced diagnostics are closed, and raw admission rows are not rendered;
- local browser evidence: `output/playwright/research-recovery-desktop-2.3.1.png` and `output/playwright/research-recovery-mobile-viewport-2.3.1.png`.

Release truth:

- deterministic and integration checks prove the engineering paths, not customer acceptance;
- `/api/research/experience/readiness` intentionally remains `blocked` until the required real samples and feedback exist;
- global `/api/system/release-readiness` includes the new `research_experience` gate and remains fail-closed.

## 12. Post-2.3.1 Field-Test Report Quality Recovery

Updated: 2026-08-10

Status: field-quality contracts through `2.5.0-development` and the `2.5.1-2.6.5` read-only assurance control plane are implemented locally on 2026-08-10. This line was added after real local reports for a broad Yangtze River Delta tourism research topic and an earlier government-AI topic were reviewed. It does not change the release truth above: independent review, customer acceptance, and current-version visual artifacts remain external blockers.

### 12.1 Field-Test Findings

The reports demonstrate useful policy and solution-playbook synthesis, but are not yet decision-grade account-pursuit reports:

1. A raw tender instruction can be extracted and ranked as a target account. A candidate such as a phrase beginning with "potential bidder" must never survive entity review, appear in `top_target_accounts`, or influence a title.
2. A target-specific commercial claim can be supported by an external-region benchmark, old policy, snapshot-reused source, or media excerpt. Those materials are useful references, but must not count as current local opportunity proof.
3. Section source quotas can be satisfied while the sources are low-locality, secondary, or insufficiently fresh. A numeric quota alone cannot justify a high-confidence label.
4. Evidence, citation, entity, freshness, and delivery status can disagree. A report must have one authoritative delivery state; a citation failure, invalid target, or stale-only evidence cannot coexist with a formal-ready signal.
5. Current solution sections produce sensible vertical playbooks, but lack a named buyer, actual current estate, decision owner, budget route, procurement stage, option trade-off, and customer-specific acceptance evidence. They are reusable consulting hypotheses, not yet a customer solution architecture.

### 12.2 Planned Version Integration

| Version | Priority | Delivery scope | Required acceptance gate |
| --- | --- | --- | --- |
| `2.3.2` | P0 truth repair | Entity and role integrity: extract organizations only from admissible semantic fields; require canonical organization identity plus buyer/supplier/partner role evidence; prune rejected candidates before ranking, title generation, report rendering, and exports; add tender-boilerplate, navigation, sentence-fragment, and narrative-prefix hard-negative corpora | In a 500-case entity corpus, false target-account precision >=99%; zero rejected/narrative/boilerplate entity may enter `top_target_accounts`, report title, or export; every ranked target has at least one direct role-bearing evidence anchor |
| `2.3.3` | P0 evidence topology | Source classes and relevance contract: label every source as target proof, local comparable, external benchmark, policy context, or historical context; add locality, time-window, primary-origin, URL-safety, and snapshot-freshness checks before Cross Encoder reranking; external benchmarks move to a separate reference lane and cannot increase local opportunity confidence | Local target-proof precision@5 >=90% on government and tourism qrels; zero external benchmark is used as local budget/procurement proof; 100% of snapshot and reused sources display their age and cannot satisfy fresh-evidence gates; unsafe/SEO-contaminated URLs are excluded |
| `2.3.4` | P0 gate convergence | One delivery truth model: compose entity, source-topology, freshness, citation, runtime, and evidence gates into a single formal/provisional/awaiting-user/system-degraded decision; high-confidence section labels require the same hard conditions; explain the decisive missing proof in plain language | Contradictory combinations such as `citation=fail` plus formal-ready = 0; formal export bypass = 0; usability test participants correctly identify report state and next action >=90% |
| `2.4.0` | P0 account-pursuit research | Account-first opportunity cards replace generic target lists: named account, verified role, current signal, procurement/budget stage, evidence-versus-inference split, confidence band, incumbent/partner status, next proof source, and a time-bounded owner action; if no viable account exists, render a market-scan result rather than a false pursuit report | In a 60-report expert review, every top-three account is real and role-verified; at least 80% of reviewers agree the first next action is specific and executable; unsupported budget/date/probability claims = 0 |
| `2.4.1` | P1 consulting and solution architecture | Customer-specific solution engineering: problem and stakeholder map, current-estate discovery, options A/B/C, ADR/C4 boundary, data/AI/security/operations design, 90-day pilot, KPI baseline and target, TCO assumptions, delivery risks, and acceptance evidence; every item is marked as fact, assumption, benchmark, or recommendation | Architecture reviewers rate >=4/5 for traceability and implementability; every proposed component has a linked target fact or explicit assumption; unlabelled assumptions = 0 |
| `2.4.2` | P1 commercial strategy | Pursuit and bid engineering: buyer map, budget route, procurement calendar, incumbent and competitor evidence, partner role fit, qualification plan, win themes, loss risks, and no-bid triggers; use verified organization profiles only | For audited reports, 100% of named competitors/partners have real-entity evidence and source anchors; no-bid trigger coverage >=95%; three sector practitioners confirm the playbook is usable in a real account review |
| `2.5.0` | P0 quality calibration and release evidence | Independent blind review corpus, customer-quality rubric, source-topology qrels, account-pursuit scoring, solution-architecture scoring, paired model/prompt evaluation, and release-readiness integration | At least 100 real reports across six industries; critical-claim coverage =100%; entity precision >=99%; formal/provisional classification error =0; three independent reviewers and three customer-side acceptance samples remain required before release promotion |

Engineering completion in this table means the product contract, APIs, UI, regression tests, validation template, and release-readiness aggregation exist locally. It does not convert pending human review, customer acceptance, or visual/Office artifacts into approval evidence.

### 12.3 Operating Rules

- A broad industry report may contain external or historical examples, but it must label them as benchmarks and must not turn them into local account, budget, or tender claims.
- A customer report must fail closed to a market-scan or evidence-recovery result when it cannot identify at least one verified buyer-side organization and current decision signal.
- Cross Encoder reranking is a relevance optimization after hard source-topology rules; it is never an evidence-admission substitute.
- A polished vertical architecture cannot promote a report to formal delivery unless its customer facts, assumptions, and acceptance path are explicitly separated.
- Existing real-task, expert, Office, visual, security, performance, recovery, and customer-acceptance gates remain `blocked` until independently evidenced.

## 13. Post-2.5.0 Assurance and Evidence Operations

Status: the engineering aggregation, API, panel, regression coverage, and release-readiness connection are implemented locally through `2.9.5-development`. Each row below remains evidence-gated: this is a quality operating program, not a declaration that historic data, external reviewers, customer acceptance, or visual baselines have passed.

| Version | Focus | Local engineering contract | Required acceptance gate |
| --- | --- | --- | --- |
| `2.5.1` | Historical payload compatibility | Parse every completed report through the current response schema; isolate invalid payloads before any dashboard score is calculated. | `invalid payload = 0` across the release sample; incompatible historical records are migrated or explicitly quarantined. |
| `2.5.2` | Source topology and freshness | Measure source-topology labelling, local decision proof, snapshot reuse, and formal-delivery topology contradictions. | All formal account claims use current local proof; snapshot/history material remains non-fresh context. |
| `2.5.3` | Entity role truth | Measure entity-gate enforcement, rejected entities, and formal report bypasses. | In an independently audited entity corpus, no narrative fragment or unsupported organization reaches formal ranking/export. |
| `2.5.4` | Claim coverage and conflicts | Measure high-confidence claim support, conflicting claims, and ledger status for formal delivery. | All formal high-confidence claims are supported and conflict-free; manual audit confirms the evidence relation. |
| `2.5.5` | Delivery-truth convergence | Detect unresolved legacy delivery states and contradictions between formal status, citation, and evidence gates. | Formal/provisional/awaiting-user/system-degraded classification error is zero in the release sample. |
| `2.5.6` | Low-quality remediation | Surface flagged rate and invalid payloads from the persisted low-quality review queue. | Flagged rate is at or below 10%, invalid payloads are zero, and accepted rewrites are human-reviewed. |
| `2.5.7` | Clarification recovery cohorts | Aggregate real task volume, sector coverage, and clarification-to-usable-result conversion. | At least 120 real tasks across six industries with the agreed recovery and feedback thresholds. |
| `2.5.8` | Model fallback truth | Link real report fallback markers to the model-control-plane route state. | Formal reports have zero deterministic/mock fallback; A/B evidence confirms any strategy-model upgrade. |
| `2.5.9` | Cost ledger coverage | Aggregate priced versus unpriced model calls and observed report cost. | Every production model call has input/cache/output pricing and per-report cost is auditable. |
| `2.6.0` | Reranker adoption and drift | Measure enabled Cross Encoder runs, actual use, and degraded-without-use events after source admission. | Fixed qrels demonstrate quality/latency benefit before broad enablement; enabled degradation count is zero. |
| `2.6.1` | Cross-industry coverage | Track sector buckets independently from generic completed-task count. | Government, healthcare, finance, tourism, education, and manufacturing each have real labeled samples. |
| `2.6.2` | Independent review packet | Validate the locked 100-case dataset against reviewer identity, attestation, substantive notes, decision, and digest. | Independent reviewers approve 100/100 valid cases; no template or self-review can satisfy this gate. |
| `2.6.3` | Expert calibration and customer acceptance | Validate 100 quality audits, topology qrels, fixed-evidence A/B, reviewer separation, and customer conclusions. | Expert calibration completes with agreed recall/consistency thresholds plus three-sector customer acceptance. |
| `2.6.4` | Visual, Office, and durable queue proof | Require version-aligned release screenshots, Office manifests, failure/lease visibility, and durable task recovery state. | Screenshot and Office baseline manifests are current, visually accepted, and all stale jobs are reconciled. |
| `2.6.5` | Assurance Command Center | Publish the above state as a read-only API and Research Center view; feed the aggregate into release readiness. | Every prior local and external gate is evidenced; otherwise the aggregate remains `watch` or `blocked`. |

### 13.1 Operating Boundaries

- The Assurance API reads persisted jobs and artifact files; it does not mutate reports, restart work, export a reviewer template, or write an approval.
- A missing review, calibration, customer, screenshot, Office, or queue artifact is a visible gap, not an inferred pass.
- The aggregate score is a prioritization signal only. `release-readiness` remains fail-closed on any blocked gate.

## 14. Retrieval Assurance and Controlled Promotion (`2.6.6`-`2.8.0`)

Status: all 15 engineering rounds below are implemented locally. The current real local snapshot remains `blocked`: the fixed 12-case artifact is only `partial`, the configured Cross Encoder was not applied because its external cache volume is unavailable, and the existing human-review file is an older/pending protocol artifact. No candidate strategy has been promoted; `baseline_hybrid` remains the sole production default.

| Version | Control | Local implementation | External acceptance gate |
| --- | --- | --- | --- |
| `2.6.6` | Immutable benchmark snapshot | Persist dataset hash, knowledge-base generation, result-level digest, and reject tampered persisted results. | A current fixed result is signed off as reproducible. |
| `2.6.7` | Cohort coverage | Require at least 12 fixed cases, all three strategy arms, and per-case result coverage. | The cohort has agreed cross-industry representativeness. |
| `2.6.8` | Failure localization | Preserve per-case Recall@10, nDCG@10, citation hit rate, latency, evidence excerpts, and reranker provenance. | Reviewers confirm failed cases have actionable root causes. |
| `2.6.9` | Full-report review integrity | Require every case/strategy score to cite a real complete-report artifact plus reviewer identity, independence, and conflict declaration. | Independent reviewers complete every required report comparison. |
| `2.7.0` | Paired human review | Compare baseline and candidates on the same fixed cases and review protocol. | All required paired scores are completed. |
| `2.7.1` | Paired significance | Compute deterministic paired-bootstrap confidence intervals from the review artifact. | Candidate lower confidence bound is positive. |
| `2.7.2` | Latency and cost boundary | Retain measured latency and enforce the two-times-baseline candidate guardrail. | Shadow traffic confirms local hardware and operating cost remain acceptable. |
| `2.7.3` | Cross Encoder provenance | Record actual backend, model name, and case-level application; heuristic/degraded paths cannot count as reranking. | Cached model is actually used on every required fixed case. |
| `2.7.4` | Candidate governance | Candidate must pass retrieval, complete-report quality, latency, and provenance gates; human quality breaks eligible-candidate ties. | Quality owner confirms the promotion recommendation. |
| `2.7.5` | Human approval separation | Approval must bind the same benchmark digest and be completed by someone other than the report reviewer. | Named independent approver signs the candidate decision. |
| `2.7.6` | Controlled shadow | Require a bound approval digest, named operator, attestation, at least 30 samples, zero fallback, and zero quality regression. | A real controlled shadow run is completed. |
| `2.7.7` | Drift monitoring | Require a bound approval digest, named operator, attestation, at least 12 fixed checks, and zero regression. | Post-shadow fixed-set drift check passes. |
| `2.7.8` | Rollback readiness | Keep `baseline_hybrid` as the only default independent of approval evidence. | Rollback is rehearsed with the production owner. |
| `2.7.9` | Audit chain | Link approval, shadow, and drift artifacts through immutable summaries. | Audit owner validates the full evidence chain. |
| `2.8.0` | Release-readiness integration | Expose the 15-round snapshot, template exports, operator commands, and aggregate release gate in Research Center/API. | All preceding external gates pass; otherwise release readiness remains `blocked`. |

### 14.1 Operating Rules

- A completed human review is accepted only when its `benchmark_digest` matches the exact fixed retrieval result. Updating review scores never reruns retrieval.
- Template exports create only missing pending artifacts and refuse to overwrite unreadable or human-authored approval/runtime records.
- A `promote` recommendation authorizes only a human approval template and then controlled shadow work; it never changes the production default by itself.
- UI exposes concise status, evidence, and next actions. It does not expose internal model reasoning or hidden prompts.

## 15. Retrieval Evidence Operations (`2.8.1`-`2.9.5`)

Status: all 15 engineering rounds below are implemented locally. This is the operational continuation of the `2.6.6`-`2.8.0` control plane: it makes all evidence artifacts discoverable, bound, fresh, and auditable. The local snapshot remains `blocked` until real named reviewers/operators complete the current evidence chain. Pending templates, configuration values, and fixture tests do not count as external evidence.

| Version | Control | Local implementation | Required acceptance gate |
| --- | --- | --- | --- |
| `2.8.1` | Evidence envelope | Recompute the fixed retrieval result digest and reject a persisted benchmark whose stored digest differs from its content. | A current fixed result is independently reproducible. |
| `2.8.2` | Artifact inventory | List benchmark, review, approval, shadow, drift, incident, revocation, and handoff artifacts with readable/missing state. | Every required artifact is present and readable. |
| `2.8.3` | Artifact lineage | Require review, approval, shadow, and drift records to bind the exact current benchmark digest. | Audit confirms no old cohort or old knowledge-base evidence is reused. |
| `2.8.4` | Evidence freshness | Enforce review/approval/shadow/drift time windows and block stale records. | Owners renew evidence under the current operating cadence. |
| `2.8.5` | Role separation | Require distinct named reviewer, approver, shadow operator, and drift operator; document that identity verification remains organizational. | Organization verifies independence and conflict boundaries. |
| `2.8.6` | Review coverage matrix | Count every fixed-case x strategy complete-report review, report artifact path, and human score. | Independent review covers every required report pair. |
| `2.8.7` | Reranker runtime preflight | Reuse actual Cross Encoder provenance from the fixed cohort; configured/degraded paths never count as applied reranking. | Real cached Cross Encoder runs on every required case. |
| `2.8.8` | Shadow operations ledger | Carry forward approved-candidate, sample, fallback, and quality-regression checks from the real shadow artifact. | A named operator completes the controlled shadow sample. |
| `2.8.9` | Drift operations ledger | Bind fixed-set drift checks to the same approval and require the evidence order after shadow execution. | Post-shadow fixed-set drift check has zero regression. |
| `2.9.0` | Incident register | Add a bound, fresh, named record for fallback, source degradation, quality regression, and manual waivers; open entries block promotion. | All incidents are independently closed or release remains blocked. |
| `2.9.1` | Revocation acknowledgement | Require a named current confirmation that any candidate can roll back to `baseline_hybrid`. | Production owner rehearses and confirms the rollback route. |
| `2.9.2` | Renewal chronology | Verify `review -> approval -> shadow -> drift` order so old runtime evidence cannot support a newer approval. | Owners renew the full chain in the required order. |
| `2.9.3` | Evidence package manifest | Compute a canonical chain digest across benchmark and operations artifacts for reproducible external review. | Independent audit can recompute and match the submitted package. |
| `2.9.4` | Independent audit handoff | Add a separately completed handoff record bound to the exact chain digest. | Named independent audit owner accepts the handoff. |
| `2.9.5` | Release-readiness bridge | Publish the 15-round operations snapshot, templates, operator commands, Research Center panel, and fail-closed release gate. | All preceding operations gates and inherited external release gates pass. |

### 15.1 Operating Rules

- The operations API is read-only. Template export only creates missing `pending` incident, revocation, and handoff files and refuses to overwrite unreadable or human-authored records.
- A completed record must bind the current benchmark digest (or, for handoff, the recomputed evidence-chain digest), have a named owner, a valid timestamp, and an attestation. A file's existence alone is not evidence.
- The UI exposes status, missing evidence, and next actions without exposing private prompts or hidden model reasoning.
- `baseline_hybrid` remains the only production default throughout these rounds. The new release gate cannot authorize a strategy switch.
