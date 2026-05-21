# Capacity and AWS budget (~$600/month)

## Your target

| Goal | Feasible at ~$600/mo? |
|------|------------------------|
| **~100 users logged in** (browsing, upload, questions) | **Yes** — with Plan B split (API + RDS medium) |
| **~100 live AI interviews at the same time** | **No** — Ollama on one box handles ~10–15 concurrent interviews |

“At a time” for interviews is limited by **GPU/CPU on the AI host**, not login count.

---

## Recommended AWS layout (within budget)

See [scripts/aws-plan-b/README.md](../scripts/aws-plan-b/README.md) (~$430–500/mo on-demand, alert at $550).

| Component | Size | Role |
|-----------|------|------|
| Frontend | t3.small | Static React + nginx |
| API | c6i.large | Flask/gunicorn (auth, CRUD, uploads) |
| AI | c6i.2xlarge | Ollama only (`llama3.2:3b`) |
| RDS | db.t3.medium | PostgreSQL |

**Daily schedule** (10:00–20:00 IST stop/start) in `scripts/aws-plan-b/setup-daily-schedule.sh` saves cost outside business hours.

---

## Realistic concurrency

| Workload | Approx. capacity |
|----------|------------------|
| Logins / dashboard / questions | 100+ concurrent |
| Mock interviews (voice + LLM) | **10–15** concurrent |
| Queue beyond that | Users wait or see “try again” |

To approach 100 parallel interviews you would need **multiple AI instances + a job queue** (well above $600/mo).

---

## Code / server tuning (already in repo)

| Area | Setting |
|------|---------|
| DB | `ThreadedConnectionPool` — `DB_POOL_MIN` / `DB_POOL_MAX` (default 2–20) |
| API | gunicorn `1` worker, `8` threads, 300s timeout |
| AI warmup | `ENABLE_AI_WARMUP=false` on API (saves RAM) |
| Frontend | Lazy routes, lazy syntax highlighter, prod strips `console` |

### If you split API from Ollama (Plan B)

In AWS Secrets Manager / API `.env`:

```bash
DB_POOL_MIN=5
DB_POOL_MAX=40
```

On API host, consider gunicorn `2` workers × `4` threads after monitoring RAM.

---

## To grow later (above $600)

1. Second **AI EC2** + round-robin or queue (SQS + worker).
2. **Reserved Instances** or Savings Plans (~30–40% off).
3. Smaller Ollama model for screening; larger model only for feedback.
4. **Redis** only if you run multiple API nodes (sessions).

---

## Monthly checklist

1. AWS Budget alert at **$600** (`scripts/aws-plan-b/set-budget-alert.sh`).
2. `./scripts/cleanup-github-actions-runs.sh --max 10 --days 2` (or wait for daily maintenance job).
3. `./scripts/cleanup-host-artifacts.sh` on servers (keep 2 releases).
