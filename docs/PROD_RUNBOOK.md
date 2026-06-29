# Production deploy runbook

**Prod only.** No staging. Execute in order: **AWS → DevSecOps → Code**. Pause if any step fails.

**Config model:** All application settings live in Secrets Manager (`interviewcoach/prod/app`). Prod API containers receive only `AWS_REGION` and `AWS_SECRETS_MANAGER_SECRET_ID` — no `.env` on servers.

Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Pre-deploy checklist

- [ ] Fill `backend/secrets.prod.example.json` with real prod values (do not commit secrets)
- [ ] OpenRouter API key ready
- [ ] AWS CLI logged in (`ap-south-1`)
- [ ] Copy `infra/prod/` → devsecops-platform (or run from app repo)
- [ ] `chmod +x infra/prod/scripts/*.sh`

---

## Deploy timeline

| Phase | Step | Script |
|-------|------|--------|
| **1 AWS** | Enable Bedrock models | `01-aws-bedrock.sh` |
| **1 AWS** | S3 buckets (CloudFormation) | `02-aws-cloudformation.sh` or `02b-rename-s3-stack.sh` |
| **1 AWS** | Push secrets JSON → Secrets Manager | `03-aws-secrets-manager.sh` |
| **1 AWS** | Attach IAM policy to API role | `04-aws-iam-attach.sh` |
| **2 Build** | API + frontend on **GitHub Actions** | `.github/workflows/deploy-prod.yml` |
| **3 Code** | ASG rollout + S3 sync (same workflow) | `06-code-deploy-api-asg.sh` |
| **3 Code** | Verify health | `curl API:5000/api/health` |
| **3 Code** | Migrate storage → S3 | `07b-migrate-legacy-storage.sh` |
| **3 Code** | Frontend build → S3 | `08-code-frontend.sh` |
| **3 Code** | CloudFront + ACM (us-east-1) | `09-code-cloudfront-deploy.sh` |
| **3 Code** | DNS cutover (Namecheap) | `09b-namecheap-dns-cutover.sh` or `09-code-cutover.sh` |
| **3 Code** | Prod smoke test | (below) |
| **Monitor** | CloudWatch / Bedrock / OpenRouter | ongoing |

**After 7 stable days:** `10-cleanup-decommission.sh` + [AWS_DECOMMISSION.md](AWS_DECOMMISSION.md)

All scripts live under `infra/prod/scripts/`.

---

## Phase 1 — AWS

### 1. Bedrock
```bash
bash infra/prod/scripts/01-aws-bedrock.sh
```

### 2. S3 buckets
```bash
bash infra/prod/scripts/02-aws-cloudformation.sh
# Or if renaming an existing legacy S3 stack:
bash infra/prod/scripts/02b-rename-s3-stack.sh
```

### 3. Secrets Manager
```bash
SECRETS_FILE=backend/secrets.prod.example.json \
  bash infra/prod/scripts/03-aws-secrets-manager.sh
```

### 4. IAM
```bash
bash infra/prod/scripts/04-aws-iam-attach.sh
```

---

## Phase 2 — Build & deploy (GitHub Actions only)

```text
Actions → Deploy PROD → Run workflow
```

Do not run `docker build` or `npm run build` locally for prod. Scripts `05-devsecops-build-ecr.sh` and `08-code-frontend.sh` exit unless `GITHUB_ACTIONS=true`.

Deploy Hybrid compute (one-time infra): `CONFIRM=YES bash infra/prod/scripts/14-aws-deploy-prod-compute.sh`

---

## Phase 3 — Code deploy

### Deploy API
```bash
# GitHub Actions only — see .github/workflows/deploy-prod.yml
```

Container env (only):
```yaml
AWS_REGION: ap-south-1
AWS_SECRETS_MANAGER_SECRET_ID: interviewcoach/prod/app
```

### Health (before cutover)
```bash
curl -fsS http://API_IP:5000/api/health | jq .
# Expect: llm.provider=bedrock, config.source=secrets_manager
```

### Storage migration
```bash
bash infra/prod/scripts/07b-migrate-legacy-storage.sh
```

### Frontend
```bash
bash infra/prod/scripts/08-code-frontend.sh
```

### CloudFront + DNS cutover
```bash
bash infra/prod/scripts/09-code-cloudfront-deploy.sh
bash infra/prod/scripts/09a-acm-validation-dns.sh   # if cert pending
bash infra/prod/scripts/09b-namecheap-dns-cutover.sh
curl -fsS https://www.ugaanlabs.ai/api/health
```

Update `infra/prod/prod.env` with `CF_DIST_ID` and `CF_DOMAIN` from script output.

### Hardening + monitoring
```bash
# All-in-one (set ALARM_EMAIL in prod.env first):
bash infra/prod/scripts/13-prod-hardening-all.sh

# Or step by step:
bash infra/prod/scripts/10c-harden-api-security-group.sh   # closes :5000; SSH auto-detect if SSH_AUTO_DETECT_IP=1
bash infra/prod/scripts/11-aws-alarm-sns-topic.sh        # needs ALARM_EMAIL
bash infra/prod/scripts/12-aws-cloudwatch-alarms.sh
bash infra/prod/scripts/09d-acm-cleanup-pending.sh
bash infra/prod/scripts/09c-cloudfront-cfn-reconcile.sh

# Rotate OpenRouter key (revoke old key at openrouter.ai after):
OPENROUTER_API_KEY=sk-or-v1-... bash infra/prod/scripts/03b-rotate-openrouter-key.sh
```

CI deploy workflow: `.github/workflows/deploy-prod.yml` (requires GitHub `production` environment secrets).

---

## Prod smoke test

- [ ] Login
- [ ] Upload resume
- [ ] Start interview — mic → STT → Bedrock reply
- [ ] Piper voice plays
- [ ] Head tracking calibrates
- [ ] Payment page loads
- [ ] Two browser tabs = independent head tracking

---

## Rollback

1. CloudFront → previous origins
2. Restore required keys in Secrets Manager
3. Restart previous API host

---

## Decommission (after 7 stable days)

```bash
bash infra/prod/scripts/10-cleanup-decommission.sh
```

See [AWS_DECOMMISSION.md](AWS_DECOMMISSION.md) for full checklist.
