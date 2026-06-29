# Monday PROD cutover — step by step

**Prod only.** No staging. Execute in order: **AWS → DevSecOps → Code**. Pause if any step fails.

**Config model:** All application settings live in Secrets Manager (`interviewcoach/prod/app`). Prod API containers receive only `AWS_REGION` and `AWS_SECRETS_MANAGER_SECRET_ID` — no `.env` on servers.

**Before Monday:** fill real values in `backend/secrets.prod.example.json` (do not commit secrets).

---

## Sunday night (prep)

- [ ] Fill `backend/secrets.prod.example.json` with real prod values
- [ ] OpenRouter API key ready
- [ ] AWS CLI logged in (`ap-south-1`)
- [ ] Copy `infra/prod/` → devsecops-platform (or run from app repo)
- [ ] `chmod +x infra/prod/scripts/*.sh`

---

## Monday timeline

| Time | Phase | Step | Script |
|------|-------|------|--------|
| **9:00** | **1 AWS** | Enable Bedrock models | `01-aws-bedrock.sh` |
| **9:30** | **1 AWS** | S3 buckets (CloudFormation) | `02-aws-cloudformation.sh` |
| **10:00** | **1 AWS** | Push secrets JSON → Secrets Manager | `03-aws-secrets-manager.sh` |
| **10:30** | **1 AWS** | Attach IAM policy to API role | `04-aws-iam-attach.sh` |
| **11:00** | **2 DevSecOps** | Build + push ECR (`Dockerfile.prod`) | `05-devsecops-build-ecr.sh` |
| **11:30** | **3 Code** | Deploy API to prod EC2/ASG | `06-code-deploy-api.sh` |
| **12:00** | **3 Code** | **Lunch / verify** `curl API:5000/api/health` |
| **13:00** | **3 Code** | Migrate storage → S3 (+ legacy buckets) | `07b-migrate-legacy-storage.sh` |
| **13:30** | **3 Code** | Frontend build → S3 | `08-code-frontend.sh` |
| **14:00** | **3 Code** | CloudFront + ACM (us-east-1) | `09-code-cloudfront-deploy.sh` |
| **14:15** | **3 Code** | DNS cutover (Namecheap) | `09b-namecheap-dns-cutover.sh` or `09-code-cutover.sh` |
| **14:30** | **3 Code** | **Prod smoke test** (below) |
| **15:00+** | Monitor | CloudWatch / Bedrock / OpenRouter bills |

**Week 2:** `10-cleanup-decommission.sh` + `docs/AWS_DECOMMISSION.md`

All scripts live under `infra/prod/scripts/`.

---

## Phase 1 — AWS

### 1. Bedrock
```bash
bash infra/prod/scripts/01-aws-bedrock.sh
```

### 2. S3 buckets
```bash
# Fresh deploy:
bash infra/prod/scripts/02-aws-cloudformation.sh

# If hybrid stack exists (rename + import with Retain):
bash infra/prod/scripts/02b-rename-s3-stack.sh
```

### 3. Secrets Manager (single source of truth)
Edit JSON with real keys, then:
```bash
SECRETS_FILE=backend/secrets.prod.example.json \
  bash infra/prod/scripts/03-aws-secrets-manager.sh
```

Prod API reads **only** this secret. Required keys are validated at startup.

### 4. IAM
```bash
INSTANCE_ROLE_NAME=interviewcoach-api-role \
  bash infra/prod/scripts/04-aws-iam-attach.sh
```

---

## Phase 2 — DevSecOps

### 5. Build & push
```bash
export ECR_REGISTRY=YOUR_ACCOUNT.dkr.ecr.ap-south-1.amazonaws.com
export IMAGE_TAG=prod-$(date +%Y%m%d)
bash infra/prod/scripts/05-devsecops-build-ecr.sh
```

Optional: wire `infra/prod/github-workflows/deploy-prod.yml` in devsecops-platform.

---

## Phase 3 — Code deploy

### 6. Deploy API
```bash
export API_HOST=ec2-user@YOUR_API_IP
bash infra/prod/scripts/06-code-deploy-api.sh
```

Container env (only):
```yaml
AWS_REGION: ap-south-1
AWS_SECRETS_MANAGER_SECRET_ID: interviewcoach/prod/app
```

### 7. Health (before cutover)
```bash
curl -fsS http://API_IP:5000/api/health | jq .
# Expect: llm.provider=bedrock, stt.chain=["openrouter","amazon"], config.source=secrets_manager
```

### 8. Storage migration
```bash
# Legacy Plan B buckets + EC2 /apps/storage → ic-user-files-prod
bash infra/prod/scripts/07b-migrate-legacy-storage.sh
```

### 9. Frontend
```bash
export STATIC_BUCKET=ic-static-prod
export CF_DIST_ID=YOUR_DIST_ID
bash infra/prod/scripts/08-code-frontend.sh
```

### 10. CloudFront + DNS cutover

Deploy CloudFront (requests ACM in us-east-1 if needed):
```bash
bash infra/prod/scripts/09-code-cloudfront-deploy.sh
```

If cert is pending, add validation CNAMEs at Namecheap:
```bash
bash infra/prod/scripts/09a-acm-validation-dns.sh
```

DNS cutover — automated (preserves email MX):
```bash
NAMECHEAP_API_USER=youruser \
NAMECHEAP_API_KEY=... \
NAMECHEAP_USERNAME=youruser \
bash infra/prod/scripts/09b-namecheap-dns-cutover.sh
```

Or manual confirmation:
```bash
bash infra/prod/scripts/09-code-cutover.sh
curl -fsS https://ugaanlabs.ai/api/health
```

Update `infra/prod/prod.env` with `CF_DIST_ID` and `CF_DOMAIN` from script output.

---

## Prod smoke test (after cutover)

- [ ] Login
- [ ] Upload resume
- [ ] Start interview — mic → STT → Bedrock reply
- [ ] Piper voice plays
- [ ] Head tracking calibrates
- [ ] Payment page loads
- [ ] Two browser tabs = independent head tracking

---

## Rollback (if broken)

1. CloudFront → old Plan B origins
2. Restore legacy keys in Secrets Manager (`OLLAMA_*`, `TRANSCRIBE_SERVICE_URL`)
3. Restart old API + AI EC2

---

## After 7 stable days

```bash
bash infra/prod/scripts/10-cleanup-decommission.sh
bash scripts/aws-decommission-checklist.sh
```

Terminate: **AI EC2**, Whisper sidecar, old frontend EC2.

---

## Ready for Monday?

| Requirement | In repo? | Execute when? |
|-------------|----------|---------------|
| Application code (secrets-only) | **Yes** | Phase 3 |
| DevSecOps scripts + CloudFormation | **Yes** | Phases 1–3 |
| AWS resources live | Run scripts | Phase 1 |
| Remove old AWS | **Doc ready** | Week 2 |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full prod topology.
