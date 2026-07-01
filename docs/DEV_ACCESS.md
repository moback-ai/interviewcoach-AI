# Developer AWS access (CloudWatch logs)

**Who:** `ganesh`, `neeraj` (group `InterviewCoach-Developers`)

**Not:** Govardhan, Kishore → `InterviewCoach-DevSecOps` (full prod access)

Production logs are in **AWS CloudWatch only** — there is no in-app log viewer.

## What you can do

- Open **AWS Console → CloudWatch → Log groups → `/interviewcoach/prod/api`**
- Run **Logs Insights** queries (read-only)
- Change your own IAM console password

## What you cannot do

- View or download **Secrets Manager** entries (app secrets, SSH keys, RDS proxy)
- EC2, RDS, S3, IAM, CloudFormation, deploy, SSH to prod

Policies: `InterviewCoach-Developer-Logs-ReadOnly` + `InterviewCoach-Developer-Deny`

## Example Logs Insights query

```
fields @timestamp, @message
| filter @message like /ERROR/ or @message like /login/
| sort @timestamp desc
| limit 100
```

## No logs?

API runs **10:00–19:00 IST** only. Off-hours there are no instances and no new log streams.
