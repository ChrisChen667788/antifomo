# AntiFomo

AntiFomo is a `Next.js + FastAPI` research workspace for high-signal content intake, recommendation, focus sessions, research reports, action cards, and WeChat-oriented collection workflows.

This open-source snapshot is prepared for GitHub publishing:
- local secrets and runtime artifacts are excluded
- example config files are kept
- the mini program `AppID` is intentionally blank
- the repository is packaged as a fresh git repo without local history

## What It Does

- `Inbox`: submit URLs, raw text, or keywords for research
- `Feed`: triage content with `like / ignore / save / open detail`
- `Research`: generate report drafts, compare topics, and derive action cards
- `Focus`: run focus sessions and turn inputs into follow-up artifacts
- `Collector`: manage URL-first collection, desktop collector, and WeChat PC agent
- `Mini Program`: a mobile companion for feed, inbox, research, focus, and collector operations
- `Browser Extension`: send current web pages or WeChat article pages into the system

## Repository Layout

```text
.
├── src/                    # Next.js web app
├── backend/                # FastAPI backend, models, services, tests
├── miniapp/                # WeChat mini program
├── browser-extension/      # Chrome extension
├── scripts/                # local automation and smoke helpers
├── public/                 # static assets
└── .github/workflows/      # CI for build + backend tests
```

## Quick Start

### 1. Install dependencies

```bash
npm install
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
cp .env.local.example .env.local
```

Default mode uses mock LLM behavior and local SQLite, so you can start without external API keys.

### 3. Start backend

```bash
source backend/.venv/bin/activate
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

### 4. Start frontend

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Open:
- Web: `http://127.0.0.1:3000`
- API: `http://127.0.0.1:8000`

## Useful Commands

```bash
# Web production build
npm run build

# Backend tests
source backend/.venv/bin/activate
pytest backend/tests

# One-command local demo scripts
npm run demo:setup
npm run demo:start
npm run demo:stop

# WeChat collector helpers
npm run collector:start
npm run collector:stop
npm run wechat-agent:start
npm run wechat-agent:stop
```

## Configuration

### Backend

See `backend/.env.example` for all supported variables.

Key groups:
- `DATABASE_URL`: SQLite or PostgreSQL
- `LLM_PROVIDER`: `mock` or OpenAI-compatible provider
- `OPENAI_*`: primary model config
- `STRATEGY_OPENAI_*`: optional second model for research pipeline
- `WORKBUDDY_*`: callback / webhook integration

### Mini Program

The file `miniapp/project.config.json` ships with an empty `appid`.

Before importing into WeChat DevTools:
1. fill in your own Mini Program `AppID`
2. adjust API base to your local or LAN backend

### Browser Extension

The extension is under `browser-extension/chrome`. Load it in Chrome developer mode and point it to your backend URL.

## Security Notes

- No runtime `.env`, database files, logs, or `.tmp` artifacts are included in this repo
- Secrets should only be placed in local env files, never committed
- The mini program `AppID` is intentionally removed from the public snapshot
- Some automation scripts target local desktop workflows and require manual permission setup on macOS

If you discover a security issue, see `SECURITY.md`.

## CI

GitHub Actions runs:
- `npm run build`
- backend `pytest`

Workflow file: `.github/workflows/ci.yml`

## License

This snapshot is prepared with the MIT license. See `LICENSE`.
