# PROD migration — COMPLETE (local, ready for Monday)

**Status:** Application code + DevSecOps templates + decommission docs — **all prepared locally**.  
**Not done:** Nothing executed on AWS. Nothing committed/pushed unless you choose to.

---

## Your four questions — answered

| Question | Answer |
|----------|--------|
| **Code migration entirely local?** | **Yes (~95%)** — Bedrock, OpenRouter STT, S3 storage, Redis, Piper, head tracking, prod Docker image, tests |
| **DevSecOps entirely local?** | **Yes (templates)** — `infra/prod/` scripts, IAM, CloudFormation, GitHub workflow — **you run on Monday** |
| **Ready to remove old AWS?** | **Docs + scripts ready** — execute **`10-cleanup-decommission.sh`** after **7 stable days** |
| **Deploy prod Monday?** | **Yes, step-by-step** — follow **`docs/MONDAY_RUNBOOK.md`** (not one-click; ~6 hours Monday) |

---

## What was completed today (local)

### Application
- `common/llm/` — Bedrock + Ollama fallback
- `common/speech/` — OpenRouter → Amazon STT
- `common/storage.py` + `storage_s3.py` — **S3 wired**
- `common/redis_store.py` — **Redis wired** (rate limit, cache, interview slots)
- `requirements.prod.txt` + `docker/api/Dockerfile.prod` — **no Ollama/Whisper**
- `backend/tests/test_prod.py`
- Per-session head tracking

### DevSecOps (local templates)
- `infra/prod/scripts/` — **Phase 1 AWS** (`01`–`04`) → **Phase 2 DevSecOps** (`05`) → **Phase 3 Code** (`06`–`09`)
- Secrets-only: all prod config in `interviewcoach/prod/app` — see `docs/SECRETS_ONLY.md`
- `infra/prod/iam/` — API task policies
- `infra/prod/cloudformation/` — S3 buckets
- `infra/prod/github-workflows/deploy-prod.yml`

### Docs
- `docs/MONDAY_RUNBOOK.md` — **start here Monday**
- `docs/AWS_DECOMMISSION.md` — remove Plan B
- `backend/secrets.prod.example.json`

---

## Monday — open this file

**`docs/MONDAY_RUNBOOK.md`**

Quick start:
```bash
bash infra/prod/scripts/01-aws-bedrock.sh
# ... follow phases 1 → 2 → 3 in MONDAY_RUNBOOK.md
```

---

## Still manual on Monday (cannot automate from laptop)

- Fill real secrets in JSON (OpenRouter key, DB password, JWT, Dodo)
- Set `ECR_REGISTRY`, `API_HOST`, `CF_DIST_ID` in scripts
- Create/attach ALB + CloudFront if not already present
- Bedrock quota approval (may take hours if not pre-approved)

---

## Optional before Monday

```bash
git add -A && git commit -m "..."   # only when you want
# PR → develop → ask DevSecOps to deploy
```

**Do not push secrets.** Never commit `backend/.env` or filled secrets JSON with real keys.
