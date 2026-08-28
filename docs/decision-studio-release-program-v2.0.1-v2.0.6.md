# Decision Studio 2.0.1-2.0.6 Release Program

Status: locally implemented on 2026-07-16. This is an engineering completion record, not a commercial release approval.

Current development version: `2.0.6-development`.

Current promotion status: `blocked`. The repository now calculates and stores every required gate, but real human qrels, independent report/entity review, expert document calibration, security review, Office/visual approval, production load/recovery evidence, the inherited `100+30` calibration, three-industry blind review, and customer acceptance have not been synthesized or auto-approved.

## Shared Evidence Contract

All six versions use append-only `decision_validation_runs` records introduced by Alembic revision `20260716_0027`:

- The server derives `milestone_version`, `evidence_class`, metrics, findings, score, and status from the registered suite. A client cannot submit a final pass score directly.
- Each record stores a canonical input digest, computed metrics, raw artifact URI, reviewer identity/role, attestation, reviewed time, and start/completion time.
- Independent and expert suites require a reviewer distinct from the artifact owner, a substantive attestation, reviewed time, and raw artifact URI.
- There are no update or delete APIs. A new run supersedes an old run only because the aggregate reads the latest append-only record.
- Audit export chains every serialized run with SHA-256 and returns `chain_head` plus `chain_valid`.

## Version Acceptance Matrix

| Version | Implemented capability | Required acceptance evidence |
| --- | --- | --- |
| `2.0.1` | Idempotent activation of existing `KnowledgeEntry` and succeeded `ResearchJob` data into source-revision Notebooks; qrel and parser calculators | At least one provenance-bound real source; 300 human qrels with 100 each for medical/finance/tourism; `nDCG@10 >= 0.78`; at least 15% over hash baseline; `Recall@20 >= 0.90`; click-back `>=98%`; leakage `0`; 100 parser documents with order/table/locator fidelity `>=98%` |
| `2.0.2` | Formal-document calibration and Claim/incremental-compiler validation | Government FSR, enterprise FSR, and project proposal each have 20 expert samples; outline coverage `100%`; unsourced numbers `0`; formula lineage `100%`; at least 100 critical claims with citation coverage `100%`; critical conflicts `0`; unaffected section reuse `>=90%` |
| `2.0.3` | Independent report-quality and organization-entity authenticity validation | 100/100 reports independently reviewed; low-quality rate `<=10%`; at least 10 undeliverable positives with recall `>=95%`; 500 independently labeled entities; output noise rate `<=1%`; invalid-phrase rejection recall `>=95%` |
| `2.0.4` | Cross-surface ACL/connector matrix and governed Skill security benchmark | At least 25 cases spanning search/chat/cache/export/deep-link; authorization mismatch, resource leakage, and credential exposure all `0`; at least five first-party Skills signed, licensed, approved, and benchmarked; injection undeclared actions and least-privilege violations `0` |
| `2.0.5` | Six-form artifact consistency plus Office and Studio visual acceptance | All six artifact forms present; critical facts `100%` consistent; ordinary facts `>=98%`; stale artifacts `0`; DOCX/XLSX/PPTX roundtrip and `/studio` light/dark views independently approved |
| `2.0.6` | Performance/cost and recovery/audit/external-model-volume reliability contracts | At least 20 concurrent users and 500 requests; interaction API P95 `<=2.5s`; errors `<=1%`; BGE-M3 cold start `<=120s`; long-report model cost `<=20 CNY`; queue restart, backup restore, audit export, and external-volume fail-closed all pass with zero data loss and RTO `<=15m` |

## API Surface

| Method and path | Purpose |
| --- | --- |
| `POST /api/decision-studio/activation/preview` | Enumerate source candidates, duplicate/update state, and provenance before writing |
| `POST /api/decision-studio/activation/run` | Create or update a Notebook idempotently and append the `real_data_activation` run |
| `GET /api/decision-studio/validation-specs` | Return server-owned 2.0.1-2.0.6 contracts |
| `POST /api/decision-studio/validation-runs/preview` | Calculate status without persistence |
| `POST /api/decision-studio/validation-runs` | Append an immutable validation run |
| `GET /api/decision-studio/validation-runs` | List latest/history records, optionally by suite |
| `GET /api/decision-studio/validation-runs/audit-export` | Export the tamper-evident hash chain |
| `GET /api/decision-studio/release-program` | Aggregate the latest run for all 13 suites and six milestones |
| `POST /api/decision-studio/reliability/probe` | Run non-destructive DB, audit-chain, cache-path, and external-mount checks |
| `GET /api/decision-studio/readiness` | Combine the new release program with all inherited release gates |

The `/studio` release tab presents implementation and acceptance separately. The left Notebook rail supports preview-first activation of the existing knowledge base and completed reports.

## Operator Commands

```bash
npm run studio:validation:specs -- --output .tmp/decision-studio-validation-specs.json
npm run studio:validation:preview -- --input /path/to/run.json
npm run studio:validation:record -- --input /path/to/run.json
npm run studio:release -- --output .tmp/decision-studio-release.json
npm run studio:audit -- --output .tmp/decision-studio-audit.json
npm run studio:reliability -- --output .tmp/decision-studio-reliability.json
npm run stability:concurrency -- --environment local --validation-input .tmp/decision-studio-performance-input.json
npm run studio:validation:preview -- --input .tmp/decision-studio-performance-input.json
```

`preview`, `record`, `release`, and `reliability` return a non-zero exit code while their target remains blocked, so CI cannot mistake an incomplete evidence package for release approval.

The concurrency runner defaults to the 2.0.6 load shape (`20` workers, `500` requests, P95 `<=2.5s`, errors `<=1%`) and includes Decision Studio endpoints. Its default `environment=local` output is deliberately rejected by the release calculator. A production performance record additionally needs measured BGE-M3 cold-start time and long-report model cost; changing the environment label without running the production test is not admissible evidence.

The 2026-07-16 real local-data diagnostic initially exposed a cache stampede in the knowledge-commercial dashboard (`491/500`, P95 `10.583s`). Content-signature single-build caching reduced the repeated run to `500/500`, error rate `0`, and P95 `690ms`; Dashboard and Accounts P95 were `1.436s` and `1.422s`. The raw reports remain local engineering diagnostics and are not recorded as production validation runs.

## Migration And Recovery Baseline

The complete SQLite migration chain is part of the 2.0.6 recovery contract, not only the two Decision Studio revisions. Historical migrations now use dialect-compatible JSON, SQLite-safe default handling, and Alembic batch mode for foreign-key changes. Verification covers:

```bash
cd backend
DATABASE_URL=sqlite:////tmp/anti-fomo-migration.db .venv311/bin/alembic upgrade head
DATABASE_URL=sqlite:////tmp/anti-fomo-migration.db .venv311/bin/alembic downgrade 20260716_0026
DATABASE_URL=sqlite:////tmp/anti-fomo-migration.db .venv311/bin/alembic upgrade head
```

This proves schema reconstruction and the latest-revision rollback path. It does not replace the separate production-data backup restore, queue restart, zero-loss, and `RTO <=15m` evidence required by `recovery_audit_reliability`.

## Promotion Rule

Promotion requires both layers:

1. Every 2.0.1-2.0.6 validation suite has a latest `pass` run with the required raw artifact and external review contract.
2. The inherited release-readiness snapshot passes health, diagnostics, low-quality audit, 100+30 review/calibration, three-industry blind evaluation, customer acceptance, Office roundtrip, and visual confirmation.

Machine fixtures validate the calculators and orchestration only. They are not admissible as the missing human, expert, security, visual, or customer evidence.
