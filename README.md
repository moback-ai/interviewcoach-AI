# InterviewCoach AI

AI-powered mock interview platform (React + Flask + PostgreSQL + Ollama).

Production: **https://ugaanlabs.ai**

## Quick start (local)

```bash
# Backend (terminal 1) — needs Python 3.12, AWS secrets or backend/.env
bash scripts/dev-local.sh

# Frontend (terminal 2)
cd frontend && npm install --legacy-peer-deps && npm run dev
```

- Frontend: http://127.0.0.1:5173  
- Backend API: http://127.0.0.1:5001/api/health  

Copy env templates: `backend/.env.example`, `frontend/.env.example`.

## Branches & deploy

| Branch | Role | Deploy |
|--------|------|--------|
| `develop` | Integration (default) | Yes — auto after merged PR |
| `develop/<feature>` | Feature work | Yes — after admin PR approval |
| `main` | Monthly snapshot | **Never** deploys |

### Is a manual deploy button required?

**Usually no** — merging an admin-approved PR into `develop` triggers **Deploy · Production** automatically (one workflow run).

**Use the manual button when you need to:**

- Re-deploy the same commit (no new merge)
- Force `deploy_target: all` when `auto` skipped unchanged paths
- Deploy a specific SHA or feature branch tip

**Where to find it:** GitHub → **Actions** → **Deploy · Production** → **Run workflow** (top right).

If auto deploy did not start after merge, use **Deploy · Production** manually with `git_ref` = `develop` or a commit SHA.

Both paths still require **production environment approval** before anything reaches servers. Failed deploys roll back to the last stable release.

Full steps: [docs/DEPLOY.md](docs/DEPLOY.md) · Requirements map: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) · Workflows: [.github/workflows/README.md](.github/workflows/README.md)

## Project layout

```
backend/          Flask API (app.py), INTERVIEW AI, support bot
frontend/         Vite + React 19
database/         Schema and SQL migrations
scripts/          Dev, deploy, security scan helpers
docs/             Deploy and security runbooks
```

## Tests

```bash
# Frontend lint + build
cd frontend && npm run lint && npm run build

# Frontend E2E (login smoke)
cd frontend && npm run test:e2e

# Backend unit tests
cd backend && python -m pytest tests/ -q
```

Security scans run as one **Security scan** step (PR + deploy). See [docs/SECURITY_SCANNING.md](docs/SECURITY_SCANNING.md).

## Security

Report vulnerabilities privately (see [SECURITY.md](SECURITY.md)). Do not file public issues for exploitable bugs.
