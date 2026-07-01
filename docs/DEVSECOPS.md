# Production deploy — DevSecOps only

**Full guide (roles, diagrams, step-by-step):** [DEVSECOPS_GUIDE.md](DEVSECOPS_GUIDE.md)

**Only these two people deploy to production:**

| DevSecOps | GitHub |
|-----------|--------|
| Govardhan | `@govardhanreddy66` |
| Kishore | `@KFKishore23` |

Repository: **`moback-ai/devsecops-platform`** (private)

---

## Developers (ganesh, neeraj)

1. Open a **PR** to `develop` → pass Security CI
2. **DevSecOps approves and merges** (developers do not merge)
3. Ask DevSecOps for **build + deploy** if needed

### AWS access (CloudWatch only — no in-app log UI)

| Allowed | Blocked |
|---------|---------|
| CloudWatch Logs read on `/interviewcoach/prod/api` | Secrets Manager (all `interviewcoach/*` incl. SSH keys) |
| Change own IAM password | EC2, RDS, S3, IAM, CFN, Bedrock, etc. |

See [DEV_ACCESS.md](DEV_ACCESS.md).

---

## DevSecOps — release flow

1. Sync `infra/prod/` → `devsecops-platform` (`scripts/sync-interviewcoach-prod.sh`)
2. **Build once:** Actions → **InterviewCoach · Build Docker Images** → note `image_tag`
3. **Deploy rollout:** Actions → **InterviewCoach · Deploy Production** → same `image_tag` (no API Docker build)
4. IAM: `devsecops-platform/scripts/apply-iam-policies.sh --apply`

### Safety controls

| Control | What it does |
|---------|----------------|
| `check-devsecops-actor.sh` | Blocks non-DevSecOps from build/deploy workflows (primary gate) |
| GitHub `production` environment | Second approval on Team/Enterprise; optional on Free (use actor gate) |
| `05a-verify-ecr-image.sh` | Deploy fails if image tag missing in ECR |
| `require-devsecops.sh` | Prod scripts cannot run from application repo |
| Branch protection + CODEOWNERS | Only DevSecOps merges `develop` / `main` |

### One-time GitHub setup

```bash
ALLOW_LOCAL_PROD_DEPLOY=1 bash infra/prod/scripts/16-set-github-prod-secrets.sh
ALLOW_LOCAL_PROD_DEPLOY=1 bash infra/prod/scripts/16b-set-github-prod-environment.sh
```

---

## Service hours (IST)

| Time | API |
|------|-----|
| **10:00 – 19:00** | Live (ASG min 1, max 4) |
| **19:00 – 10:00** | Off (ASG 0) — maintenance banner on frontend |

Banner auto-hides when service opens. See [DEVSECOPS_GUIDE.md § Service hours](DEVSECOPS_GUIDE.md#service-hours-ist).

---

## Repo scripts

`infra/prod/scripts/*` require DevSecOps (`require-devsecops.sh`) except `load-prod-env.sh`.
