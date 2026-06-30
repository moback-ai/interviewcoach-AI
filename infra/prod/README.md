# PROD — DevSecOps pack (reference copy)

**Do not run production scripts from this application repo.**

Copy this folder to **`moback-ai/devsecops-platform`** → `apps/interviewcoach/aws/prod/`  
Or run from devsecops: `bash scripts/sync-interviewcoach-prod.sh`  
All production operations (deploy, secrets, SSH, AWS changes) run **only** from devsecops-platform.

**Prod only.** No staging.  
Architecture: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) · Runbook: [docs/PROD_RUNBOOK.md](../../docs/PROD_RUNBOOK.md) · Access: [docs/DEVSECOPS.md](../../docs/DEVSECOPS.md)

---

## Who runs what

| Role | Repository | Actions |
|------|------------|---------|
| **Developers** | `moback-ai/interviewcoach-AI` | PR → `develop`, Security CI only |
| **DevSecOps** | `moback-ai/devsecops-platform` | Deploy, secrets, SSH, AWS infra scripts |

Deploy workflow template: `github-workflows/deploy-prod.yml` → copy to devsecops-platform `.github/workflows/`

---

## Migration order

1. **Phase 1 — AWS** (`01`–`04`, optional `02b`): Bedrock, S3, Secrets Manager, IAM
2. **Phase 2 — Build & deploy** (devsecops-platform **InterviewCoach · Deploy Production** only)
3. **Phase 3 — Code** (`07`–`09`, `14`): storage, CloudFront, DNS; one-time compute stack
4. **Phase 4 — Cleanup** (`10`): Decommission Plan B

Scripts in this folder call `require-devsecops.sh` and **exit** if run from interviewcoach-AI.

---

## Secrets-only config

Prod API containers receive only:

```yaml
AWS_REGION: ap-south-1
AWS_SECRETS_MANAGER_SECRET_ID: interviewcoach/prod/app
```

Template: `backend/secrets.prod.example.json`  
Push: `scripts/03-aws-secrets-manager.sh` (DevSecOps only)  
Details: [docs/SECRETS_ONLY.md](../../docs/SECRETS_ONLY.md)

---

## Contents

| Path | Purpose |
|------|---------|
| `prod.env` | Resolved infra names (no secrets) — edit once, sync copy to devsecops |
| `iam/api-task-role-policy.json` | IAM policy for API EC2 task |
| `iam/trust-ec2.json` | EC2 instance trust policy |
| `cloudformation/prod-stack.yaml` | S3 buckets (static + user files, Retain) |
| `cloudformation/prod-stack-import.yaml` | Import existing buckets into renamed stack |
| `cloudformation/prod-cloudfront.yaml` | CloudFront: S3 static + ALB API origin |
| `github-workflows/deploy-prod.yml` | **Copy to devsecops-platform** — not used in this repo |
| `cloudformation/prod-compute-stack.yaml` | ALB + ASG + ElastiCache |

### Scripts (DevSecOps only)

| Script | Purpose |
|--------|---------|
| `require-devsecops.sh` | Blocks execution from application repo |
| `01-aws-bedrock.sh` | Bedrock model access checklist |
| `02-aws-cloudformation.sh` | Deploy S3 stack |
| `02b-rename-s3-stack.sh` | Rename `interviewcoach-prod-hybrid-s3` → `interviewcoach-prod-s3` (import retain) |
| `03-aws-secrets-manager.sh` | Create/update secrets JSON |
| `04-aws-iam-attach.sh` | Attach API IAM policy |
| `05-devsecops-build-ecr.sh` | Build `Dockerfile.prod` → ECR (devsecops Actions) |
| `05-build-on-ec2.sh` | **Disabled** |
| `06-code-deploy-api-asg.sh` | Roll out ECR image to ASG (devsecops Actions) |
| `06-code-deploy-api.sh` | Wrapper → `06-code-deploy-api-asg.sh` |
| `07-code-migrate-storage.sh` | Sync API `/apps/storage` → S3 |
| `07b-migrate-legacy-storage.sh` | Legacy Plan B S3 buckets + EC2 → `ic-user-files-prod` |
| `08-code-frontend.sh` | Build React → S3 (devsecops Actions) |
| `09-code-cloudfront-deploy.sh` | ACM cert (us-east-1) + CloudFront stack |
| `09a-acm-validation-dns.sh` | Print ACM DNS validation CNAMEs |
| `09b-namecheap-dns-cutover.sh` | Namecheap API: point `@`/`www` at CloudFront (preserves MX) |
| `09-code-cutover.sh` | Manual DNS cutover confirmation |
| `10-cleanup-decommission.sh` | Stop AI EC2 + old hosts |
| `10c-harden-api-security-group.sh` | Harden ASG API SG: close :5000; optional SSH CIDR lockdown |
| `12-aws-cloudwatch-alarms.sh` | ASG + RDS CloudWatch alarms |
| `15-aws-schedule-business-hours.sh` | ASG scale 10:00–19:00 IST |
| `16-set-github-prod-secrets.sh` | Push secrets to **devsecops-platform** `production` env |
| `cloudfront/apex-to-www.js` | CloudFront function source (apex → www redirect) |
| `load-prod-env.sh` | Source `prod.env` (read-only safe) |
| `ssh-prod.sh` | SSH to ASG API instance (DevSecOps only) |

---

## Prerequisites

- AWS account, region `ap-south-1`
- RDS (`interviewcoach-db`)
- ECR repos: `interviewcoach-api`, `interviewcoach-web`
- OpenRouter API key (in Secrets Manager, not `prod.env`)
- Domain: `www.ugaanlabs.ai` (canonical; apex redirects via CloudFront)
