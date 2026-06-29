# PROD — DevSecOps pack (local)

Copy this entire folder to **`moback-ai/devsecops-platform`** → `apps/interviewcoach/aws/prod/`

**Prod only.** No staging. Execute on **Monday** using `docs/MONDAY_RUNBOOK.md`.

## Migration order

1. **Phase 1 — AWS** (`01`–`04`): Bedrock, CloudFormation S3, Secrets Manager, IAM
2. **Phase 2 — DevSecOps** (`05`): ECR build/push (+ optional GitHub workflow)
3. **Phase 3 — Code** (`06`–`09`): Deploy API, migrate storage, frontend, cutover
4. **Phase 4 — Cleanup** (`10`): Decommission Plan B

## Secrets-only config

All application settings are stored in Secrets Manager secret **`interviewcoach/prod/app`**.

Prod API containers receive only:

```yaml
AWS_REGION: ap-south-1
AWS_SECRETS_MANAGER_SECRET_ID: interviewcoach/prod/app
```

Template: `backend/secrets.prod.example.json`  
Push script: `scripts/03-aws-secrets-manager.sh`

Laptop testing: set `RUNTIME_CONFIG_ALLOW_ENV=true` and use `backend/.env.prod.example`.

## Contents

| Path | Purpose |
|------|---------|
| `iam/api-task-role-policy.json` | IAM policy for API EC2/ECS task |
| `iam/trust-ec2.json` | EC2 instance trust policy |
| `cloudformation/prod-params.example.json` | Stack parameters |
| `cloudformation/prod-stack.yaml` | S3 buckets |
| `scripts/01-aws-bedrock.sh` | Bedrock model access checklist |
| `scripts/02-aws-cloudformation.sh` | Deploy S3 stack |
| `scripts/03-aws-secrets-manager.sh` | Create/update secrets JSON |
| `scripts/04-aws-iam-attach.sh` | Attach API IAM policy |
| `scripts/05-devsecops-build-ecr.sh` | Build Dockerfile.prod → ECR |
| `scripts/06-code-deploy-api.sh` | Deploy API on EC2/ASG |
| `scripts/07-code-migrate-storage.sh` | Sync /apps/storage → S3 |
| `scripts/08-code-frontend.sh` | Build React → S3 → invalidate CF |
| `scripts/09-code-cutover.sh` | Final traffic switch |
| `scripts/10-cleanup-decommission.sh` | Stop AI EC2 + old hosts |
| `github-workflows/deploy-prod.yml` | GitHub Actions for devsecops-platform |

## Prerequisites

- AWS account, region `ap-south-1`
- Existing RDS (`interviewcoach-db`)
- ECR repos: `interviewcoach-api`, `interviewcoach-web`
- OpenRouter API key
- Domain: `ugaanlabs.ai`

## Monday

Open **`docs/MONDAY_RUNBOOK.md`** in the application repo and follow step-by-step.
