# Deployment guide (application repo)

Production deploy is **DevSecOps only** from `moback-ai/devsecops-platform`.  
This document describes the release flow, safety gates, and rollback paths implemented in this repo.

Ops runbooks and architecture diagrams live in **devsecops-platform** → `apps/interviewcoach/docs/`.

---

## Release flow

```text
PR → CI (lint + tests) + Security (Gitleaks, Trivy, Semgrep)
  → DevSecOps merge to develop
  → DevSecOps: InterviewCoach · Release to Production
      1. Quality gate (lint, build, pytest)
      2. Build API image → ECR (optional)
      3. Deploy API / frontend (path-based)
      4. Smoke tests
      5. Auto-rollback on API smoke failure
```

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
| `infra/**` | Manual review — no auto-deploy |

Use separate `deploy_api` / `deploy_frontend` inputs in the DevSecOps workflow to deploy only what changed.

---

## Health checks

| Endpoint | Used by | Behavior |
|----------|---------|----------|
| `/api/health/live` | Docker HEALTHCHECK | Always 200 when process is up |
| `/api/health/ready` | ALB target group, deploy smoke | 200 only when DB, config, LLM, and STT are ready |
| `/api/health` | External monitoring, humans | Full diagnostics; `status` is `healthy` or `degraded` |

After changing ALB health path, update the live CloudFormation stack or target group in AWS.

---

## Database migrations

1. Add SQL under `database/migrations/` (filename order matters).
2. Migrations must be **backward compatible** with the currently running API.
3. DevSecOps applies pending migrations before or during API deploy when `database/**` changes.
4. Never apply `database/schema.sql` on production — use incremental migrations only.

See [database/README.md](../database/README.md).

---

## Rollback

### API (fast — ~3–5 minutes)

Redeploy the previous ECR tag without rebuilding:

```bash
# DevSecOps only — from devsecops-platform with app synced
IMAGE_TAG=prod-YYYYMMDD-<sha> bash infra/prod/scripts/07b-rollback-api-asg.sh
```

Or run **InterviewCoach · Release to Production** with `deploy_api=true` and an older `git_ref`, skipping build if the image already exists in ECR.

The deploy workflow captures the previous image tag and **auto-rolls back** if post-deploy smoke fails.

### Frontend

1. Enable S3 versioning (once): `infra/prod/scripts/18-enable-s3-versioning.sh`
2. Restore a previous object version in `ic-static-prod`, then invalidate CloudFront.

---

## Business hours

API ASG scales to **0 instances after 19:00 IST** for cost savings.  
Prod deploy and smoke tests are **blocked outside 10:00–19:00 IST** unless `allow_off_hours=true` (emergency only).

---

## Local verification before requesting deploy

```bash
# Frontend
cd frontend && npm run lint && npm run build:check

# Backend
pip install -r backend/requirements-ci.txt
python -m pytest backend/tests/ -q

# Optional E2E
cd frontend && npm run test:e2e
```

---

## Syncing to DevSecOps

`infra/prod/` is a **reference copy**. After changes here:

1. Sync to `moback-ai/devsecops-platform` → `apps/interviewcoach/aws/prod/`
2. Copy `infra/prod/github-workflows/deploy-prod.yml` → devsecops `.github/workflows/interviewcoach-deploy-prod.yml`
3. Run one-time ops scripts from devsecops only (`18-enable-s3-versioning.sh`, CloudFormation updates)

Do **not** run `infra/prod/scripts/*` from this application repo.

---

## Who deploys

| Role | Action |
|------|--------|
| Developers | Open PR, pass CI + Security, request deploy |
| DevSecOps (Govardhan, Kishore) | Merge, run production workflow, handle rollback |

See [.github/BRANCH_POLICY.md](../.github/BRANCH_POLICY.md).
