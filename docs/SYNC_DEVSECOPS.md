# Sync to DevSecOps platform

After deployment-related changes in `interviewcoach-AI`, copy them to **`moback-ai/devsecops-platform`**.

## Required sync (this release)

| From (this repo) | To (devsecops-platform) |
|------------------|---------------------------|
| `infra/prod/github-workflows/deploy-prod.yml` | `.github/workflows/interviewcoach-deploy-prod.yml` |
| `infra/prod/scripts/**` | `apps/interviewcoach/aws/prod/scripts/` |
| `infra/prod/cloudformation/prod-compute-stack.yaml` | `apps/interviewcoach/aws/prod/cloudformation/` |
| `infra/prod/cloudformation/prod-stack.yaml` | `apps/interviewcoach/aws/prod/cloudformation/` |
| `.github/actions/pre-deploy-quality-gate/` | `.github/actions/interviewcoach-pre-deploy-quality-gate/` (or equivalent path) |

Or run from devsecops: `bash scripts/sync-interviewcoach-prod.sh`

## One-time AWS ops (DevSecOps only)

1. **ALB health path** — update target group to `/api/health/ready` (or redeploy compute stack)
2. **S3 versioning** — `bash infra/prod/scripts/18-enable-s3-versioning.sh`
3. **Replace deploy workflow** — enable updated `interviewcoach-deploy-prod.yml` in devsecops

## Verify after sync

- [ ] PR CI passes in `interviewcoach-AI` (CI + Security)
- [ ] DevSecOps deploy workflow has quality gate + business hours + rollback steps
- [ ] Smoke test uses `/api/health/ready` (not legacy 503 bypass)
- [ ] ALB routes only to ready instances

See [DEPLOY.md](DEPLOY.md) for the full release flow.
