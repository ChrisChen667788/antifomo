# Security Policy

## Reporting

Do not open a public issue for credential leaks, webhook verification issues, or collector automation security problems.

Report privately to the repository owner with:
- affected component
- reproduction steps
- impact
- whether secrets or personal data may be exposed

## Sensitive Data Rules

Never commit:
- `.env` files
- API keys or bearer tokens
- webhook secrets
- local SQLite databases
- `.tmp` runtime artifacts
- Mini Program private config files

## Scope

Priority areas:
- `backend/.env` and webhook callback configuration
- WeChat collector and OCR ingestion flows
- browser extension submission path
- mini program API base and runtime storage
