# Sync to DevSecOps platform

After **infra script or CloudFormation** changes in `infra/prod/`, sync to **`moback-ai/devsecops-platform`**.

**Do not** add deploy/build workflows to this repo — they live only in devsecops-platform.

## Required sync

| From (this repo) | To (devsecops-platform) |
|------------------|---------------------------|
| `infra/prod/scripts/**` | `apps/interviewcoach/aws/prod/scripts/` |
| `infra/prod/cloudformation/**` | `apps/interviewcoach/aws/prod/cloudformation/` |
| `infra/prod/nginx/**` | `apps/interviewcoach/aws/prod/nginx/` |
| `infra/prod/prod.env` | `apps/interviewcoach/aws/prod/prod.env` |

From devsecops-platform:

```bash
bash scripts/sync-interviewcoach-prod.sh
```

Workflow templates are maintained in **devsecops-platform** only:

- `.github/workflows/interviewcoach-build-prod.yml`
- `.github/workflows/interviewcoach-deploy-prod.yml`
- Reference copies under `apps/interviewcoach/aws/prod/github-workflows/` (devsecops repo)

## Verify after sync

- [ ] PR CI + Security pass in `interviewcoach-AI`
- [ ] DevSecOps runs **Build Production** + **Deploy Production** from devsecops-platform

See [DEPLOY.md](DEPLOY.md).
