# Secrets-only configuration (PROD)

## Overview

Production API instances do **not** use `.env` files or per-key environment variables. All settings live in one AWS Secrets Manager JSON object.

| Environment | How config loads |
|-------------|------------------|
| **Prod EC2 / ECS** | `AWS_SECRETS_MANAGER_SECRET_ID` → fetch JSON at startup |
| **Laptop** | `RUNTIME_CONFIG_ALLOW_ENV=true` + `backend/.env` (from `.env.prod.example`) |

## Bootstrap env vars (prod only)

These are the **only** process environment variables allowed on prod servers:

| Variable | Example |
|----------|---------|
| `AWS_REGION` | `ap-south-1` |
| `AWS_SECRETS_MANAGER_SECRET_ID` | `interviewcoach/prod/app` |

Everything else (`DB_*`, `JWT_SECRET`, `OPENROUTER_API_KEY`, `LLM_PROVIDER`, etc.) must be keys inside the secret JSON.

## Secret template

Copy and fill:

```
backend/secrets.prod.example.json
```

Push to AWS (DevSecOps only — `devsecops-platform`):

```bash
# From devsecops-platform checkout:
bash apps/interviewcoach/aws/prod/scripts/03-aws-secrets-manager.sh
```

The script validates required keys and creates the secret if it does not exist.

## Code paths

- `backend/common/runtime_config.py` — loads secrets or env (laptop only)
- `backend/common/secrets_schema.py` — required key list + startup validation
- `backend/app.py` — calls `validate_secrets_config()` on boot

All modules use `require_env()` / `optional_env()` from `runtime_config` — never `os.getenv()` for app config.

## Updating prod config

1. Edit local JSON (never commit real secrets)
2. Re-run `03-aws-secrets-manager.sh`
3. Restart API containers (no code deploy needed for most key changes)

## Health check

After deploy:

```bash
curl -fsS http://API:5000/api/health | jq .config
```

Expect `"source": "secrets_manager"` on prod.
