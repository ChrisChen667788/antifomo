# Anti-FOMO

[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/ChrisChen667788/antifomo?style=social)](https://github.com/ChrisChen667788/antifomo/stargazers)

Open-source research workspace for high-signal content intake, AI-assisted reports, focus sessions, action cards, and WeChat-first collection workflows.

If this project is useful, give it a star. It makes the repository easier to discover and helps future contributors find it faster.

## Why AntiFomo

Most information tools stop at one of these layers:
- read later
- news triage
- AI summary
- task export

AntiFomo tries to connect the full loop:

`collect -> filter -> research -> focus -> action`

That makes it useful for people who do real work with information, not just consume it.

## Built For

- consultants and strategy teams
- founders and operators
- BD and market research teams
- people who monitor WeChat-heavy information flows
- builders who want a local-first, hackable research workspace

## Core Capabilities

### 1. High-Signal Intake

- submit URLs, raw text, and keyword research requests
- browser extension for fast page capture
- multi-format collector pipeline
- WeChat-oriented URL-first collection path

### 2. Research Workspace

- generate structured report drafts
- compare research topics
- track research versions and watchlists
- turn reports into reusable action cards

### 3. Focus And Execution

- run focus sessions with goals
- generate session artifacts
- export follow-up tasks, briefs, and reading lists
- bridge research output into execution workflows

### 4. Multi-Client Surface

- web app
- FastAPI backend
- WeChat mini program
- Chrome extension

## Why It Feels Different

- `WeChat-first`: not only generic web links
- `evidence-aware`: designed around source quality and report iteration
- `execution-oriented`: action cards and session outputs are first-class
- `hackable`: easy to run locally, inspect, and modify

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

## Repository Layout

```text
.
├── src/                    # Next.js web app
├── backend/                # FastAPI backend, models, services, tests
├── miniapp/                # WeChat mini program
├── browser-extension/      # Chrome extension
├── scripts/                # automation and smoke helpers
└── public/                 # static assets
```

## Project Status

Current repository status:
- active local-first prototype
- public snapshot sanitized for open-source release
- web build passes
- backend tests pass

What is intentionally not included in this public repo:
- runtime `.env`
- personal data
- local databases
- `.tmp` collector logs and screenshots
- real WeChat mini program `AppID`

## Configuration

### Backend

See `backend/.env.example` for all supported variables.

Key groups:
- `DATABASE_URL`: SQLite or PostgreSQL
- `LLM_PROVIDER`: `mock` or OpenAI-compatible provider
- `OPENAI_*`: primary model config
- `STRATEGY_OPENAI_*`: optional second model for research pipeline
- `WORKBUDDY_*`: callback and webhook integration

### Mini Program

`miniapp/project.config.json` ships with an empty `appid`.

Before importing into WeChat DevTools:
1. fill in your own Mini Program `AppID`
2. adjust API base to your local or LAN backend

### Browser Extension

The extension lives in `browser-extension/chrome`. Load it in Chrome developer mode and point it to your backend URL.

## Roadmap

Near-term areas worth pushing further:
- better WeChat collection reliability
- stronger report grounding and source traceability
- better watchlist and entity workflows
- stronger focus-to-action artifact quality
- cleaner public demo assets and walkthroughs

## Community

- ideas and product suggestions: open a Discussion or Feature Request
- bugs: open an Issue with reproduction details
- code contributions: see `CONTRIBUTING.md`
- security reports: see `SECURITY.md`

## License

MIT. See `LICENSE`.
