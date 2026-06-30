# Production deploy — DevSecOps only

**Only these two people deploy to production:**

| DevSecOps | GitHub |
|-----------|--------|
| Govardhan | `@govardhanreddy66` |
| Kishore | `@KFKishore23` |

Repository: **`moback-ai/devsecops-platform`** (private)

---

## Developers — you deploy via PR, not Actions

1. Open a **PR** to `develop` (not a direct push for releases)
2. Pass **Security** CI
3. Get review and **merge**
4. **Ask Govardhan or Kishore to deploy** (comment on the PR or ping them)

You **cannot**:

- Run production deploy workflows (none exist on this repo)
- Run `infra/prod/scripts/*` (blocked by `require-devsecops.sh`)
- Access `devsecops-platform`, SSH keys, AWS deploy roles, or production secrets

---

## DevSecOps

1. Sync `infra/prod/` from interviewcoach-AI → `devsecops-platform/apps/interviewcoach/aws/prod/` when scripts change
2. Copy `infra/prod/github-workflows/deploy-prod.yml` → devsecops `.github/workflows/interviewcoach-deploy-prod.yml` (if not already)
3. Secrets on **devsecops-platform** `production` environment: run `16-set-github-prod-secrets.sh` from devsecops copy
4. Deploy: **Actions → InterviewCoach · Deploy Production**  
   - `app_git_ref`: merge SHA or `develop`

Access rules: `devsecops-platform/docs/TEAM_ACCESS.md`

---

## What runs where

| Action | Repository |
|--------|------------|
| Code, PRs, Security CI | `moback-ai/interviewcoach-AI` |
| Prod build, ASG rollout, S3 sync | `moback-ai/devsecops-platform` |
| AWS infra scripts, SSH, secrets | `moback-ai/devsecops-platform` (copied scripts) |
