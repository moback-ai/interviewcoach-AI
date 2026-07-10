# InterviewCoach AI

AI-powered mock interview platform (React + Flask + PostgreSQL).

Production: **https://www.ugaanlabs.ai**

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
| `release/<month>-<year>` | **Active month** — open PRs here | Yes — DevSecOps build + deploy after merge |
| Feature branches | Branch from current release | Yes — after DevSecOps merge into release |
| `develop` | Integration | **Auto-merged from release at month-end** — not a deploy source |
| `main` | Production mirror | **DevSecOps merge only** — never deploys |

**Production deploy is DevSecOps only** (Govardhan or Kishore) from `moback-ai/devsecops-platform`. Developers open PRs into the **release branch**, pass CI + Security, and request deploy.

- [docs/README.md](docs/README.md) — contributing, developer docs index  
- [docs/DEPLOY.md](docs/DEPLOY.md) — release flow, health checks, rollback  
- [docs/SECURITY_SCANNING.md](docs/SECURITY_SCANNING.md) — Security CI  
- [docs/DEV_ACCESS.md](docs/DEV_ACCESS.md) — CloudWatch log access  

Ops docs (architecture, budget, DevSecOps, runbooks): **`devsecops-platform`** → `apps/interviewcoach/docs/` (private)

## Project layout

```
backend/          Flask API, common/ (llm, speech, storage, redis)
frontend/         Vite + React 19
database/         Schema and SQL migrations
docker/           Dockerfile.prod, compose files
infra/            Pointer only — prod infra is in devsecops-platform
docs/             Developer docs only
scripts/          Local dev and security scan helpers
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

Security scans and unit tests run on PRs. See [docs/SECURITY_SCANNING.md](docs/SECURITY_SCANNING.md) and [docs/DEPLOY.md](docs/DEPLOY.md).

## Security

Report vulnerabilities privately (see [SECURITY.md](SECURITY.md)). Do not file public issues for exploitable bugs.
