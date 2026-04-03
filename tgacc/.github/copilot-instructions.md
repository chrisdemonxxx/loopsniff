# Copilot Instructions for This Repository

## Build, Test, and Lint Commands

This monorepo contains multiple subprojects. Use the following commands in each subproject directory:

### Node.js/TypeScript (Next.js projects)
- **Install dependencies:** `npm install`
- **Run dev server:** `npm run dev`
- **Build:** `npm run build`
- **Start:** `npm run start`
- **Lint:** `npm run lint`
- **Run all tests:** `npm test` (if test scripts are present)
- **Run single test file:** `npm test -- path/to/test.spec.ts`

Projects: `adflux-admin-panel`, `adflux-client-portal`, `adflux-website`

### Python projects
- **Install dependencies:** `pip install -r requirements.txt`
- **Run all tests:** `python -m pytest`
- **Run single test file:** `python -m pytest path/to/test_file.py`
- **Run single test function:** `python -m pytest path/to/test_file.py::test_function_name`
- **Lint/format:** `python -m black . && python -m isort . && python -m flake8`

Projects: `adflux-api`, `adflux-bot`, `adflux-rag`, `bulk-account-creator`

## High-Level Architecture

- **Monorepo**: Contains several independent apps/services, each in its own directory under the repo root or `tgacc/`.
- **Frontend**: Next.js/React apps for admin, client, and website panels.
- **Backend/API**: Python FastAPI and bot services for data, automation, and integrations.
- **RAG/AI**: Retrieval-Augmented Generation (RAG) service for lead intelligence (see `adflux-rag`).
- **Bulk Automation**: Tools for account creation and outreach (see `bulk-account-creator`).

## Key Conventions

- **TypeScript/Next.js**: Uses `@/*` path alias for `src/` (see `tsconfig.json`).
- **Python**: Follows standard pytest and Black conventions. Tests are named `test_*.py`.
- **Environment Variables**: Each project uses its own `.env` or `.env.local` file. Do not share secrets between projects.
- **Agent Guidelines**: See `AGENTS.md` in the repo root for detailed agent coding standards, commit rules, and project-specific recipes.
- **AI Assistant Configs**: See `CLAUDE.md` and `AGENTS.md` for additional agent/AI-specific rules.
- **Next.js**: Some projects use a custom Next.js version—see `adflux-website/AGENTS.md` for agent-specific Next.js rules.

---

For more details, consult each subproject's README or config files.
