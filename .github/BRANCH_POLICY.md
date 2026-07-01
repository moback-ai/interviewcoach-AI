# Branch policy

**DevSecOps ops guide:** `moback-ai/devsecops-platform` → `apps/interviewcoach/docs/DEVSECOPS_GUIDE.md` (private)  
**Developer summary:** [docs/DEVSECOPS.md](../docs/DEVSECOPS.md)

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

1. **Build image once** — devsecops → **InterviewCoach · Build Docker Images**
2. **Deploy rollout only** — devsecops → **InterviewCoach · Deploy Production** (existing ECR tag, no build)

See [docs/DEVSECOPS.md](../docs/DEVSECOPS.md).

## ASG schedule (IST)

| Time | API instances |
|------|----------------|
| **10:00–19:00** | At least **1** (scale up to **4** if CPU > 70%) |
| **After 19:00** | **0** (cost saving) |

CPU autoscale only runs during business hours when `min ≥ 1`.
