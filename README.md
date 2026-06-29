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
| `develop` | Integration (default) | Yes — via DevSecOps after merged PR |
| `develop/<feature>` | Feature work | Yes — after admin PR approval |
| `main` | Monthly snapshot | **Never** deploys |

**Production deploy is DevSecOps only** (Govardhan or Kishore) from `moback-ai/devsecops-platform`. Developers release by merging a PR to `develop` and requesting deploy.

- [docs/DEPLOY.md](docs/DEPLOY.md) — developer release flow  
- [docs/DEVSECOPS.md](docs/DEVSECOPS.md) — who deploys and how  
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — prod topology (CloudFront, Bedrock, S3)  
- [docs/PROD_RUNBOOK.md](docs/PROD_RUNBOOK.md) — production deploy steps  
- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — team requirements map  

## Project layout

```
backend/          Flask API, common/ (llm, speech, storage, redis)
frontend/         Vite + React 19
database/         Schema and SQL migrations
docker/           Dockerfile.prod, compose files
infra/prod/       CloudFormation, IAM, deploy scripts, prod.env
docs/             Architecture, deploy runbooks, security
scripts/          Dev, deploy, security scan helpers
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

Security scans run on PRs. See [docs/SECURITY_SCANNING.md](docs/SECURITY_SCANNING.md).

## Security

Report vulnerabilities privately (see [SECURITY.md](SECURITY.md)). Do not file public issues for exploitable bugs.
