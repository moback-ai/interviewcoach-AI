# Deployment guide (application repo)

Production deploy is **DevSecOps only** from `moback-ai/devsecops-platform`.  
This document describes the release flow developers follow in **this** repo.

Ops runbooks and architecture: **devsecops-platform** → `apps/interviewcoach/docs/`.

---

## Release flow

```text
PR → release/<month>-<year> (CI + Security)
  → DevSecOps merge into release branch
  → devsecops-platform: InterviewCoach · Build Production
  → devsecops-platform: InterviewCoach · Deploy Production (auto tag, smoke, rollback)
```

At month-end, release is **auto-merged into `develop`**. Build/deploy never use `develop` or `main`.

| Step | Where it runs | Blocks deploy? |
|------|---------------|----------------|
| CI | `interviewcoach-AI` on every PR | Yes (merge gate) |
| Security | `interviewcoach-AI` on every PR | Yes |
| Quality gate | `devsecops-platform` before deploy | Yes |
| Business hours (10:00–19:00 IST) | Deploy workflow | Yes (unless emergency flag) |
| ECR image scan (CRITICAL CVEs) | After API build | Yes |
| Smoke tests | After deploy | Yes (+ auto-rollback for API) |

---

## What deploys when

| Changed paths | Typical deploy action |
|---------------|----------------------|
| `frontend/**` | Frontend only → S3 + CloudFront invalidation |
| `backend/**`, `docker/api/**` | API build + ASG rolling refresh |
| `database/migrations/**` | Apply migrations, then API deploy |

DevSecOps toggles `deploy_api` / `deploy_frontend` in the Deploy workflow.

---

## Health checks

| Endpoint | Used by | Behavior |
|----------|---------|----------|
| `/api/health/live` | Docker HEALTHCHECK | Always 200 when process is up |
| `/api/health/ready` | ALB target group, deploy smoke | 200 when DB, config, LLM, and STT are ready |
| `/api/health` | External monitoring | Full diagnostics |

---

## Database migrations

1. Add SQL under `database/migrations/` (filename order matters).
2. Migrations must be **backward compatible** with the currently running API.
3. DevSecOps applies pending migrations during API deploy when `database/**` changes.

See [database/README.md](../database/README.md).

---

## Rollback

Ask DevSecOps to run **InterviewCoach · Rollback API** or **Deploy Production** with a previous image tag in `devsecops-platform`. The deploy workflow auto-rolls back API if smoke tests fail.

---

## Business hours

API ASG scales to **0 instances after 19:00 IST**. Deploy is blocked outside **10:00–19:00 IST** unless DevSecOps sets `allow_off_hours=true`.

---

## Local verification before requesting deploy

```bash
cd frontend && npm run lint && npm run build:check
python -m pytest backend/tests/ -q
```

---

## Who deploys

| Role | Action |
|------|--------|
| Developers | Open PR, pass CI + Security, request deploy |
| DevSecOps (Govardhan, Kishore) | Merge, run build + deploy workflows, handle rollback |

See [.github/BRANCH_POLICY.md](../.github/BRANCH_POLICY.md).
