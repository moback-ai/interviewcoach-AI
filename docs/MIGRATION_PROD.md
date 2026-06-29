# PROD migration — status

**Branch:** `develop` (in repo)  
**Domain:** https://ugaanlabs.ai  
**Region:** ap-south-1

Application code, DevSecOps scripts, CloudFormation templates, and runbooks are **committed to this repository**. Execute on AWS using the phased scripts under `infra/prod/scripts/`.

---

## Summary

| Area | Status |
|------|--------|
| Application (Bedrock, S3, Redis, secrets-only) | **In repo** |
| DevSecOps scripts + CloudFormation | **In repo** |
| CloudFront + ACM + Namecheap DNS cutover | **Scripts ready** — see runbook |
| Legacy Plan B decommission | **After 7 stable days** — [AWS_DECOMMISSION.md](AWS_DECOMMISSION.md) |

---

## What changed (Plan B → PROD)

### Application
- `common/llm/` — Bedrock (+ Ollama fallback for local dev)
- `common/speech/` — OpenRouter → Amazon Transcribe chain
- `common/storage.py` + `storage_s3.py` — S3-backed storage
- `common/redis_store.py` — Redis for rate limit, cache, interview slots
- `requirements.prod.txt` + `docker/api/Dockerfile.prod` — no Ollama/Whisper in prod image
- Per-session head tracking
- `backend/tests/test_prod.py`

### Infrastructure
- S3 buckets: `ic-static-prod`, `ic-user-files-prod` (`prod-stack.yaml`, Retain policy)
- CloudFront: S3 static + EC2 API origin (`prod-cloudfront.yaml`)
- Secrets-only config: `interviewcoach/prod/app` in Secrets Manager
- `infra/prod/prod.env` — resolved infra names (no secrets)

### DevSecOps scripts (phases)

| Phase | Scripts |
|-------|---------|
| **1 — AWS** | `01` Bedrock · `02` S3 CFN · `02b` stack rename/import · `03` secrets · `04` IAM |
| **2 — Build** | `05-devsecops-build-ecr.sh` · `05-build-on-ec2.sh` |
| **3 — Deploy** | `06` API · `07` storage · `07b` legacy S3 · `08` frontend · `09` CloudFront · `09a` ACM DNS · `09b` Namecheap cutover |
| **4 — Cleanup** | `10` decommission · `10a`/`10b` legacy cleanup |

Full timeline: [MONDAY_RUNBOOK.md](MONDAY_RUNBOOK.md)  
Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Quick start (DevSecOps)

```bash
# Source infra names
source infra/prod/scripts/load-prod-env.sh

# Phase 1
bash infra/prod/scripts/01-aws-bedrock.sh
bash infra/prod/scripts/02-aws-cloudformation.sh   # or 02b if renaming hybrid stack
SECRETS_FILE=backend/secrets.prod.example.json bash infra/prod/scripts/03-aws-secrets-manager.sh
bash infra/prod/scripts/04-aws-iam-attach.sh

# Phase 2
bash infra/prod/scripts/05-devsecops-build-ecr.sh

# Phase 3
bash infra/prod/scripts/06-code-deploy-api.sh
bash infra/prod/scripts/07b-migrate-legacy-storage.sh
bash infra/prod/scripts/08-code-frontend.sh
bash infra/prod/scripts/09-code-cloudfront-deploy.sh
bash infra/prod/scripts/09b-namecheap-dns-cutover.sh   # or 09-code-cutover.sh (manual DNS)
```

---

## Manual steps (cannot fully automate)

- Fill real secrets in JSON before `03-aws-secrets-manager.sh` (never commit real keys)
- Bedrock model access / quota approval in AWS console
- Namecheap API whitelist IP for automated DNS (`09b`)

---

## Security

**Do not commit:** `backend/.env`, filled secrets JSON with real API keys or passwords.

Template only: `backend/secrets.prod.example.json`
