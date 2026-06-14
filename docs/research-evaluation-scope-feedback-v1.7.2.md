# Research Evaluation Scope Feedback v1.7.2

Version: `1.7.2+20260615`

## Input Summary

The completed Chinese review CSV contained:

- `21` approved cases.
- `78` cases marked `需要修改`.
- `1` unanswered case: `transport-003` (`深圳机场数字孪生`).
- `99` approved answer-anchor reviews.
- `99` approved source-domain reviews.
- No requested replacement behavior labels, answer anchors, or source domains.

Reviewer name and date were intentionally ignored per operator instruction. The comment text was treated as curation feedback, not as an independently signed approval artifact.

## Feedback Classification

- Region precision only: `8` cases.
- Named research subject/buyer only: `24` cases.
- Both concrete region and named subject: `46` cases.

The unanswered airport case already contains `深圳` and `深圳机场`, so it remains unchanged and is explicitly recorded as unanswered rather than inferred approved.

## Applied Changes

- Changed only `regions`, `entities`, and curation provenance notes for the 78 cases.
- Preserved every expected behavior label.
- Preserved every reference answer term.
- Preserved every expected source domain.
- Replaced all `中国`, `全国`, `全球`, and empty region scopes with province-level, municipality-level, or city-level scopes.
- Used clearly labeled fictional organizations in sensitive safety tests where naming a real organization would create an unnecessary implication.

Resolution source:

```text
backend/evaluation/research_scope_feedback_resolution_v1_2.json
```

Repeatable application command:

```bash
backend/.venv311/bin/python scripts/apply_research_evaluation_scope_feedback.py
```

## Result

- Dataset version: `1.2.0`
- Status: `locked`
- Cases: `100`
- Scope revisions: `78`
- Broad or empty regions remaining: `0`
- Lock digest: `f52835846045726158277abf5212dda8370d3b23d4b17229df161b827e514df5`

## Remaining Gate

The revised values have been applied but have not been independently approved after replacement. Live-provider evaluation remains gated by the formal review artifact. A second-round confirmation sheet is generated for the 78 changed cases plus the one unanswered case.
