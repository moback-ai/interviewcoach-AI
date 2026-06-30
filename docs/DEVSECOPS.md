# Production deploy — DevSecOps only

**Only these two people deploy to production:**

| DevSecOps | GitHub |
|-----------|--------|
| Govardhan | `@govardhanreddy66` |
| Kishore | `@KFKishore23` |

Repository: **`moback-ai/devsecops-platform`** (private)

---

## Developers (ganesh, neeraj)

1. Open a **PR** to `develop` → pass Security CI → merge
2. Ask **Govardhan or Kishore** to deploy from devsecops-platform

### AWS access (read-only logs)

| Allowed | Blocked |
|---------|---------|
| CloudWatch Logs read on `/interviewcoach/prod/*` | Secrets Manager (all `interviewcoach/*` incl. SSH keys) |
| Change own IAM password | EC2, RDS, S3, IAM, CFN, Bedrock, etc. |

**Console:** `ap-south-1` → CloudWatch → Log groups → `/interviewcoach/prod/api`

See [DEV_ACCESS.md](DEV_ACCESS.md).

---

## DevSecOps

1. Sync `infra/prod/` → `devsecops-platform/apps/interviewcoach/aws/prod/`
2. Deploy: **Actions → InterviewCoach · Deploy Production**
3. IAM: `devsecops-platform/scripts/apply-iam-policies.sh --apply`

---

## Repo scripts

`infra/prod/scripts/*` require DevSecOps (`require-devsecops.sh`) except `load-prod-env.sh`.
