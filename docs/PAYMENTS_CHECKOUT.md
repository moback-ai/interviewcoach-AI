# Abandoned checkout intents (app contract)

When a user starts Dodo checkout and leaves midway, the API keeps a
`checkout_intents` row (`status = pending`) with an `expires_at`. Those rows
must be **expired** (not deleted) so payment history and support audits stay intact.

## What the application already does

| Behavior | Where |
|----------|--------|
| Create pending intent + `expires_at` | `POST /api/checkout` |
| Expire this intent if past `expires_at` on poll | `GET /api/checkout/<id>/status` |
| Batch-expire stale pending intents | `POST /api/internal/checkout-intents/expire-stale` |
| Show failed / expired attempts in payments UI | `GET /api/payments` |

Batch expire sets `status = expired` and `failure_reason = abandoned`.

## Internal endpoint (for DevSecOps scheduler)

```http
POST https://www.ugaanlabs.ai/api/internal/checkout-intents/expire-stale?limit=500
X-Internal-Token: <CHECKOUT_MAINTENANCE_TOKEN>
```

Successful response:

```json
{ "success": true, "expired_count": 3 }
```

Without a matching token the API returns **403**.

Optional query: `limit` (1–5000, default 500).

## Secrets Manager keys (optional but required for the sweeper)

Add to `interviewcoach/prod/app` JSON (see `backend/secrets.prod.example.json`):

| Key | Required? | Notes |
|-----|-----------|--------|
| `CHECKOUT_MAINTENANCE_TOKEN` | For sweeper | Long random secret (e.g. `openssl rand -hex 32`). Shared only with the scheduler. |
| `DODO_CHECKOUT_EXPIRY_MINUTES` | No | Default **30**. How long a pending intent stays open. |

Restart API after updating the secret so instances reload config.

## Service hours constraint

API ASG scales to **0 outside 10:00–19:00 IST** (see [DEPLOY.md](DEPLOY.md)).  
The sweeper must call the **live** API, so schedule it **only during business hours** (and/or once at morning scale-up). Night runs will fail while there are no instances.

Expire-on-status-poll still cleans an intent when a user returns during hours.

## DevSecOps ask (copy/paste)

1. Add `CHECKOUT_MAINTENANCE_TOKEN` (random) to Secrets Manager `interviewcoach/prod/app`.
2. Optionally set `DODO_CHECKOUT_EXPIRY_MINUTES` (e.g. `30`).
3. Create an **EventBridge** schedule every **15 minutes**, **10:00–19:00 IST**, that `POST`s the expire-stale URL with header `X-Internal-Token`.
4. Do **not** truncate `checkout_intents`; expiry is the supported cleanup.

Infra for the schedule lives in **`moback-ai/devsecops-platform`**, not this app repo.
