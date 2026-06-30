# Workflows

| Workflow | When | Purpose |
|----------|------|---------|
| **Security** | PR / push to `develop` | SAST, dependency scans |
| **Deploy PROD** | Manual (`workflow_dispatch`) | **All prod builds** — API Docker image, ASG rollout, frontend → S3 |

## Prod deploy (GitHub Actions only)

Do **not** build on Mac or EC2. Use:

**Actions → Deploy PROD → Run workflow**

Required secrets on the `production` environment:

| Secret | Value (from `infra/prod/prod.env`) |
|--------|-------------------------------------|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::328991713462:role/InterviewCoach-GitHubActions-Deploy` |
| `ECR_REGISTRY` | `328991713462.dkr.ecr.ap-south-1.amazonaws.com` |
| `STATIC_S3_BUCKET` | `ic-static-prod` |
| `CLOUDFRONT_DIST_ID` | `E5YX3P309ZTK0` |

One-shot setup: `bash infra/prod/scripts/16-set-github-prod-secrets.sh`

`infra/prod/prod.env` is loaded from the repo on the runner (no secrets in that file).

Emergency local override (not recommended): `ALLOW_LOCAL_PROD_DEPLOY=1` for ASG rollout only.
