# Branch policy

**All ops documentation:** `moback-ai/devsecops-platform` → `apps/interviewcoach/docs/DEVSECOPS_GUIDE.md` (private)

**Developers:** [docs/README.md](../docs/README.md)

| Branch | Purpose |
|--------|---------|
| `develop/<feature>` | Feature work → PR into `develop` |
| `develop` | Integration — **merge DevSecOps only** |
| `main` | Production mirror — **merge DevSecOps only** from `develop` |

## Who approves and merges PRs

**Only DevSecOps** may approve and merge pull requests:

| DevSecOps | GitHub |
|-----------|--------|
| Govardhan | `@govardhanreddy66` |
| Kishore | `@KFKishore23` |

Developers (ganesh, neeraj) open PRs; they do **not** merge.

Enforced via `.github/CODEOWNERS` (required review from DevSecOps).

**GitHub Actions (devsecops-platform):** build and deploy workflows gate on `check-devsecops-actor.sh`; deploy uses `production` environment reviewers.

## Deploy flow

1. **PR** — pass CI (lint, build, pytest) + Security in `interviewcoach-AI`
2. **Merge** — DevSecOps merges to `develop`
3. **Build image once** — devsecops → **InterviewCoach · Release to Production** (`deploy_api=true`)
4. **Deploy rollout only** — same workflow with existing ECR tag, or `07b-rollback-api-asg.sh` for rollback

Deploy gates: quality gate, business hours (10:00–19:00 IST), ECR CVE scan, smoke tests, auto-rollback on API failure.  
Details: [docs/DEPLOY.md](../docs/DEPLOY.md)

## ASG schedule (IST)

| Time | API instances |
|------|----------------|
| **10:00–19:00** | At least **1** (scale up to **4** if CPU > 70%) |
| **After 19:00** | **0** (cost saving) |

CPU autoscale only runs during business hours when `min ≥ 1`.
