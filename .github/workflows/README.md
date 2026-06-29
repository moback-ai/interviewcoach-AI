# Workflows

| Workflow | When | Purpose |
|----------|------|---------|
| **Security** | PR / push to `develop` | SAST, dependency scans |
| **Deploy PROD** | Manual (`workflow_dispatch`) | **All prod builds** — API Docker image, ASG rollout, frontend → S3 |

## Prod deploy (GitHub Actions only)

Do **not** build on Mac or EC2. Use:

**Actions → Deploy PROD → Run workflow**

Required secrets on the `production` environment:

| Secret | Example |
|--------|---------|
| `AWS_DEPLOY_ROLE_ARN` | IAM role for OIDC |
| `ECR_REGISTRY` | `328991713462.dkr.ecr.ap-south-1.amazonaws.com` |
| `STATIC_S3_BUCKET` | `ic-static-prod` |
| `CLOUDFRONT_DIST_ID` | `E5YX3P309ZTK0` |

`infra/prod/prod.env` is loaded from the repo on the runner (no secrets in that file).

Emergency local override (not recommended): `ALLOW_LOCAL_PROD_DEPLOY=1` for ASG rollout only.
