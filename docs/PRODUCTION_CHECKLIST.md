# Production checklist ($650/month cap)

Production URL: **https://ugaanlabs.ai**

Use this before/after every production release. Details: [DEPLOY.md](DEPLOY.md), [CAPACITY_AND_BUDGET.md](CAPACITY_AND_BUDGET.md), [scripts/aws-plan-b/README.md](../scripts/aws-plan-b/README.md).

---

## 1. Budget and hours

| Item | Target |
|------|--------|
| AWS monthly budget alert | **$650** |
| Expected actual spend | **~$350–430** (Plan B + 10h/day EC2) |
| Server uptime | **10:00–20:00 IST only** (`scripts/aws-plan-b/setup-daily-schedule.sh`) |
| Region | **ap-south-1** |

---

## 2. AWS layout (Plan B)

| Host | Type | Role |
|------|------|------|
| Frontend | `t3.small` | Static React + nginx → API |
| API | `c6i.large` | Flask/gunicorn only |
| AI | `c6i.2xlarge` | **Ollama only** (no `pm2 backend`) |
| RDS | `db.t3.medium` | PostgreSQL (can stay 24/7) |

One-time (or after infra change):

```bash
cd scripts/aws-plan-b
./optimize-550.sh --apply --split-api
./setup-daily-schedule.sh --apply   # if not already enabled
./set-budget-alert.sh --apply       # set limit to 650
```

GitHub secret **`BACKEND_HOST`** = API server public IP (`outputs.env` → `API_PUBLIC_IP`).

---

## 3. Secrets / environment (API server)

Store in **AWS Secrets Manager** (`interviewcoach/prod/app`) or API `.env`. Do not commit secrets.

### Required

| Variable | Production value |
|----------|------------------|
| `DB_HOST` / `DB_*` | RDS private endpoint |
| `JWT_SECRET` | Strong random string |
| `DOMAIN` | `https://ugaanlabs.ai` |
| `STORAGE_PATH` | `/apps/storage` |
| `PUBLIC_STORAGE_URL` | `https://ugaanlabs.ai/storage` |
| `OLLAMA_HOST` | `http://<AI_PRIVATE_IP>:11434` |
| `OLLAMA_HEALTH_URL` | `http://<AI_PRIVATE_IP>:11434/api/tags` |
| `OLLAMA_MODEL` | `llama3.2:3b` |
| `OLLAMA_NUM_PREDICT` | `384` (lower = faster replies) |
| `SMTP_*` / `MAIL_FROM` | Live SMTP |

### Performance (interviews + uploads)

| Variable | Production value |
|----------|------------------|
| `INTERVIEW_SERVER_TTS` | `false` (use browser voices in UI) |
| `INTERVIEW_FAST_WRAPUP` | `true` |
| `INTERVIEW_RESPONSE_TIMEOUT_SECONDS` | `45` |
| `QUESTION_GEN_FORCE_LOCAL` | `true` |
| `JD_PARSE_USE_OLLAMA` | `false` |
| `WHISPER_MODEL` | `base` |
| `WHISPER_BEAM_SIZE` | `1` |
| `DB_POOL_MIN` | `5` |
| `DB_POOL_MAX` | `40` |

### API server only

| Variable | Production value |
|----------|------------------|
| `ENABLE_AI_WARMUP` | `false` |

### AI server only

| Variable | Production value |
|----------|------------------|
| `ENABLE_AI_WARMUP` | `true` (optional; faster first mic use) |

After env change on API:

```bash
# On API host
pm2 restart backend
```

On AI host (once per deploy / model change):

```bash
ollama pull llama3.2:3b
systemctl is-active ollama
```

---

## 4. Deploy to production

### Before merge

- [ ] All release changes in **one PR** → `develop`
- [ ] **Security** workflow green on the PR
- [ ] **Admin Approve** on PR (@govardhanreddy66 or @KFKishore23) — required for auto-deploy

### Option A — Auto (normal)

1. Merge approved PR into `develop`
2. **Deploy · Auto (develop)** → quality gate → **Deploy · Production**
3. Admin approves **`production`** environment in GitHub
4. Wait for green (~10–15 min); failed deploys roll back

### Option B — Manual (fallback)

**Actions → Deploy · Production → Run workflow**

- `git_ref`: `develop` or commit SHA  
- `deploy_target`: `auto` (or `all` if needed)  
- Approve **`production`** environment  

### If auto-deploy failed after merge

Usually: PR merged **without** admin approval. Use **Option B** above.

---

## 5. After deploy — verify

```bash
curl -s https://ugaanlabs.ai/api/health | python3 -m json.tool
```

| Check | Expected |
|-------|----------|
| `status` | `healthy` |
| `ollama.ready` | `true` (during 10am–8pm IST when AI is up) |
| Login page | https://ugaanlabs.ai/login — password field visible |
| Interview | Pick **Ava / Mira / Noah** (browser voice), not Classic |

---

## 6. Capacity (do not over-promise)

| Load | Supported |
|------|-----------|
| ~100 users logged in (open hours) | Yes |
| ~10–15 live AI interviews at once | Yes |
| 100 parallel AI interviews | No (not this budget) |

---

## 7. Ongoing maintenance

| Task | How often | Command / workflow |
|------|-----------|-------------------|
| Prune GitHub Actions runs | Daily (automated) | **Maintenance · Scheduled** |
| Host release cleanup (keep 2) | Weekly | `scripts/cleanup-host-artifacts.sh` |
| Log trim | Weekly | **Maintenance · Scheduled** |
| Manual Actions cleanup | As needed | `./scripts/cleanup-github-actions-runs.sh --max 10 --days 2` |

---

## 8. Code optimizations (in repo)

| Change | Benefit |
|--------|---------|
| `InterviewManager.from_config` | No temp JSON file per interview turn |
| Session caches question config | Skips repeat DB question queries |
| `OLLAMA_NUM_PREDICT` | Caps LLM length → faster replies |
| Intro stage skips duplicate `assess_intro` | One fewer Ollama call when job Q&A done |
| Browser voice default (Ava) | No server TTS wait |

---

## 9. Do not (stays under $650)

- Run all EC2 **24/7** unless you accept higher bills  
- Second AI server without raising budget  
- `INTERVIEW_SERVER_TTS=true` in production (slow)  
- Merge to `develop` without admin PR approval  
- Deploy from `main`  
- Commit `.env` or credentials to git  

---

## Quick links

| Doc | Purpose |
|-----|---------|
| [DEPLOY.md](DEPLOY.md) | Deploy steps A & B |
| [CAPACITY_AND_BUDGET.md](CAPACITY_AND_BUDGET.md) | Cost and concurrency |
| [.github/workflows/README.md](../.github/workflows/README.md) | CI workflow names |
