# Contributing

## Development Setup

1. Install Node.js 20+ and Python 3.11+.
2. Install frontend dependencies with `npm install`.
3. Create a backend virtual environment and install `backend/requirements.txt`.
4. Copy:
   - `backend/.env.example` -> `backend/.env`
   - `.env.local.example` -> `.env.local`

## Before Opening a PR

- run `npm run build`
- run backend tests with `pytest backend/tests`
- avoid committing `.env`, `.tmp`, database files, and local build artifacts
- keep WeChat Mini Program `AppID` and any webhook tokens out of git

## Scope

High-value contributions for this repository:
- content intake and collector reliability
- research quality and citation grounding
- focus/session artifact quality
- mini program and extension integration
- tests, CI, and packaging improvements
