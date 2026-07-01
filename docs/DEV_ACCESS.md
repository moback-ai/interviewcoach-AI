# Developer AWS access (CloudWatch logs)

**Who:** `ganesh`, `neeraj` (group `InterviewCoach-Developers`)

**Not:** Govardhan, Kishore → `InterviewCoach-DevSecOps` (full prod access)

Production logs are in **AWS CloudWatch only** — there is **no in-app log viewer**.

Full observability guide (retired URLs, more queries): **devsecops-platform** → `apps/interviewcoach/docs/OBSERVABILITY.md` (ask DevSecOps for repo access).

---

## Where to view logs

AWS Console → **CloudWatch** → **Log groups** → **`/interviewcoach/prod/api`** → **Logs Insights**

---

## Retired URLs (Plan B — do not use)

| Retired | Use instead |
|---------|-------------|
| `https://ugaanlabs.ai/admin/logs` | CloudWatch `/interviewcoach/prod/api` |
| `https://ugaanlabs.ai/logs/` | CloudWatch |
| Live tails (`server-backend`, `server-ai`, `deployment-live`, …) | Logs Insights or GitHub Actions (deploy) |

The admin log viewer and public `/logs/` hub were removed when production moved to CloudFront + ASG + Bedrock.

---

## What you can do

- Read `/interviewcoach/prod/api` log streams
- Run **Logs Insights** queries (read-only)
- Change your own IAM console password

## What you cannot do

- Secrets Manager (`interviewcoach/*`)
- EC2, RDS, S3, IAM, deploy, SSH

Policies: `InterviewCoach-Developer-Logs-ReadOnly` + `InterviewCoach-Developer-Deny`

---

## Example Logs Insights query

```
fields @timestamp, @message
| filter @message like /ERROR/ or @message like /login/
| sort @timestamp desc
| limit 100
```

---

## No logs?

API runs **10:00–19:00 IST** only. Off-hours ASG scales to **0** — no instances, no new log streams.
