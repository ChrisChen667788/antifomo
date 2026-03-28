# Publishing Notes

This repository snapshot was sanitized from a local working copy for public GitHub publishing.

## Removed From The Public Snapshot

- runtime `.env`
- SQLite databases
- `.tmp` reports, logs, screenshots, PID files
- local virtual environments
- local build artifacts
- WeChat Mini Program private config
- original Mini Program `AppID`

## Before Pushing

1. Review `README.md`, `LICENSE`, and `SECURITY.md`.
2. Confirm the license matches your intention.
3. Fill in your own GitHub repository URL.

## Push Commands

```bash
cd /tmp/antifomo-open-source-20260329
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## Optional Release Archives

This snapshot is also packaged as:
- `antifomo-open-source-20260329.tar.gz`
- `antifomo-open-source-20260329.zip`
