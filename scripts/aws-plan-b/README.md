# AWS Plan B (~$550/month) — smooth & fast production

## What this stack does

| Server | Type | Role |
|--------|------|------|
| `interviewcoach-frontend` | t3.small | React static + nginx → API |
| `interviewcoach-api` | c6i.large | Flask/gunicorn (2 workers) |
| `interviewcoach-backend` | c6i.2xlarge | **Ollama only** |
| `interviewcoach-db` | db.t3.medium | PostgreSQL |

**Not included** (saves cost; add later if needed):
- Redis / ElastiCache — only needed for multi-node sessions; rate limits use in-memory today
- CloudFront — optional for static CDN (~$5–15/mo at low traffic)

## Monthly cost (on-demand, ap-south-1)

| Item | ~$/mo |
|------|-------|
| Frontend t3.small | 15 |
| API c6i.large | 62 |
| AI c6i.2xlarge (Ollama) | 248 |
| RDS db.t3.medium | 52 |
| EBS / transfer | 30 |
| **Total** | **~430–500** |

Budget alert: **$550/month** → `set-budget-alert.sh --apply`

## Scripts

```bash
cd scripts/aws-plan-b
chmod +x *.sh

./optimize-550.sh                    # preview all steps
./optimize-550.sh --apply            # secrets + budget (infra if not done)
./optimize-550.sh --apply --split-api  # full split API/Ollama
```

| Script | Purpose |
|--------|---------|
| `plan-b-setup.sh` | RDS medium, frontend small, optional API EC2 |
| `bootstrap-api-server.sh` | Copy backend release to API, pip + pm2 |
| `update-frontend-nginx.sh` | nginx `/api` → API private IP |
| `apply-backend-env.sh` | Plan B flags in Secrets Manager + restart |
| `set-budget-alert.sh` | AWS Budget at $550 |

## After split — GitHub deploy

Update GitHub secret **`BACKEND_HOST`** → API public IP (`outputs.env` → `API_PUBLIC_IP`).

Manual Deploy → backend (and frontend when needed).

## Capacity (realistic)

- **~100 logins at once** — OK with RDS medium
- **~10–15 live interviews** — OK with split API + Ollama box
- **100 parallel AI interviews** — not feasible at this budget

## Verify

```bash
curl -s https://ugaanlabs.ai/api/health | python3 -m json.tool
# expect: api_revision fast-upload-v3, ollama ready
```
