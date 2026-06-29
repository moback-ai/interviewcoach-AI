# PROD — DevSecOps pack

Copy this folder to **`moback-ai/devsecops-platform`** → `apps/interviewcoach/aws/prod/`  
Or run scripts directly from this application repo.

**Prod only.** No staging.  
Architecture: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) · Runbook: [docs/MONDAY_RUNBOOK.md](../../docs/MONDAY_RUNBOOK.md)

---

## Migration order

1. **Phase 1 — AWS** (`01`–`04`, optional `02b`): Bedrock, S3, Secrets Manager, IAM
2. **Phase 2 — DevSecOps** (`05`): ECR build/push (+ GitHub workflow in devsecops-platform)
3. **Phase 3 — Code** (`06`–`09`): API, storage, frontend, CloudFront, DNS cutover
4. **Phase 4 — Cleanup** (`10`): Decommission Plan B

All scripts source `prod.env` via `load-prod-env.sh`.

---

## Secrets-only config

Prod API containers receive only:

```yaml
AWS_REGION: ap-south-1
AWS_SECRETS_MANAGER_SECRET_ID: interviewcoach/prod/app
```

Template: `backend/secrets.prod.example.json`  
Push: `scripts/03-aws-secrets-manager.sh`  
Details: [docs/SECRETS_ONLY.md](../../docs/SECRETS_ONLY.md)

---

## Contents

| Path | Purpose |
|------|---------|
| `prod.env` | Resolved infra names (no secrets) — edit once, scripts pick up automatically |
| `iam/api-task-role-policy.json` | IAM policy for API EC2 task |
| `iam/trust-ec2.json` | EC2 instance trust policy |
| `cloudformation/prod-stack.yaml` | S3 buckets (static + user files, Retain) |
| `cloudformation/prod-stack-import.yaml` | Import existing buckets into renamed stack |
| `cloudformation/prod-cloudfront.yaml` | CloudFront: S3 static + EC2 API origin |
| `github-workflows/deploy-prod.yml` | GitHub Actions template for devsecops-platform |

### Scripts

| Script | Purpose |
|--------|---------|
| `01-aws-bedrock.sh` | Bedrock model access checklist |
| `02-aws-cloudformation.sh` | Deploy S3 stack |
| `02b-rename-s3-stack.sh` | Rename `interviewcoach-prod-hybrid-s3` → `interviewcoach-prod-s3` (import retain) |
| `03-aws-secrets-manager.sh` | Create/update secrets JSON |
| `04-aws-iam-attach.sh` | Attach API IAM policy |
| `05-devsecops-build-ecr.sh` | Build `Dockerfile.prod` → ECR |
| `05-build-on-ec2.sh` | Build on EC2 when local Docker unavailable |
| `06-code-deploy-api.sh` | Deploy API container on EC2 |
| `07-code-migrate-storage.sh` | Sync EC2 `/apps/storage` → S3 |
| `07b-migrate-legacy-storage.sh` | Legacy Plan B S3 buckets + EC2 → `ic-user-files-prod` |
| `08-code-frontend.sh` | Build React → S3 (+ CloudFront invalidation) |
| `09-code-cloudfront-deploy.sh` | ACM cert (us-east-1) + CloudFront stack |
| `09a-acm-validation-dns.sh` | Print ACM DNS validation CNAMEs |
| `09b-namecheap-dns-cutover.sh` | Namecheap API: point `@`/`www` at CloudFront (preserves MX) |
| `09-code-cutover.sh` | Manual DNS cutover confirmation |
| `10-cleanup-decommission.sh` | Stop AI EC2 + old hosts |
| `load-prod-env.sh` | Source `prod.env` |
| `ssh-prod.sh` | SSH helper using `prod.env` keys |

---

## Prerequisites

- AWS account, region `ap-south-1`
- RDS (`interviewcoach-db`)
- ECR repos: `interviewcoach-api`, `interviewcoach-web`
- OpenRouter API key (in Secrets Manager, not `prod.env`)
- Domain: `ugaanlabs.ai` (Namecheap)
