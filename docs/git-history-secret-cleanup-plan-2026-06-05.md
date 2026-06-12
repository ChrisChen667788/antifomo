# Git History Secret Cleanup Plan - 2026-06-05

## Current State

Current tracked tree scan is clean:

```bash
npm run security:scan
```

Local ignored scan still finds private runtime configuration:

```bash
npm run security:scan:local
```

Known local-only findings are expected and must stay ignored:

- `backend/.env` contains OpenAI API keys.
- `miniapp/project.private.config.json` contains the private WeChat miniapp AppID.

Git history scan still finds the old WeChat AppID in historical commits:

```bash
npm run security:scan:history
```

The scan reports historical references under these paths:

- `docs/miniapp-devtools-sync.md`
- `miniapp/README.md`
- `miniapp/project.config.json`
- `miniapp/project.private.config.json`

Remote repositories configured locally:

- `origin`: GitHub `ChrisChen667788/antifomo`
- `modelscope`: ModelScope `haozi667788/antifomo`

## Required Security Actions Before History Rewrite

1. Rotate or invalidate every exposed credential before relying on Git cleanup.
2. Treat the historical WeChat AppID as public.
3. Keep `backend/.env` local and ignored; do not commit any `.env` replacement file containing real keys.
4. Keep `miniapp/project.private.config.json` local and ignored; only commit `.example` templates.

## Proposed Rewrite Strategy

Do not run this automatically during ordinary refactor work. It changes commit history and requires coordinated force pushes.

Recommended tool: `git filter-repo`.

Preparation:

```bash
git status --short
git remote -v
git branch --show-current
git tag --list
```

Create a safety mirror before rewrite:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea
git clone --mirror anti-fomo-demo anti-fomo-demo-history-backup.git
```

Rewrite historical sensitive values with a replacement file:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
cat > /tmp/antifomo-secret-replacements.txt <<'REPLACEMENTS'
# Add exact exposed values locally. Do not commit this file.
# Example format:
# exposed_value==>REDACTED_WECHAT_APP_ID
REPLACEMENTS

git filter-repo --replace-text /tmp/antifomo-secret-replacements.txt
```

If the private config file itself should be removed from all history:

```bash
git filter-repo --path miniapp/project.private.config.json --invert-paths
```

If historical docs also need path-level removal instead of text replacement, remove only the affected files after confirming acceptable loss of documentation history:

```bash
git filter-repo \
  --path miniapp/project.private.config.json \
  --path miniapp/project.config.json \
  --path miniapp/README.md \
  --path docs/miniapp-devtools-sync.md \
  --invert-paths
```

## Validation After Rewrite

Run all checks after the rewrite and before pushing:

```bash
npm run security:scan
npm run security:scan:history
backend/.venv311/bin/pytest -q backend/tests/test_research_hybrid_retrieval.py
backend/.venv311/bin/pytest -q backend/tests/test_research_report_evaluation_service.py
```

## Remote Sync Plan

Only after validation and explicit confirmation:

```bash
git push origin --force-with-lease --all
git push origin --force-with-lease --tags
git push modelscope --force-with-lease --all
git push modelscope --force-with-lease --tags
```

After force push, every existing clone must either re-clone or hard reset to the rewritten remote. This is disruptive, so it should be scheduled as a dedicated maintenance window.

## Decision Gate

Do not execute the rewrite until these are confirmed:

1. All exposed credentials have been rotated or invalidated.
2. GitHub and ModelScope force-push timing is approved.
3. A mirror backup exists.
4. Everyone using existing clones knows they must re-clone or reset.
