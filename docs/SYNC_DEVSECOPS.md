# Repository split (application vs DevSecOps)

**All production infrastructure lives in `moback-ai/devsecops-platform` only.**

This application repo contains **source code** and **developer tooling** — not AWS deploy scripts or workflows.

| This repo (`interviewcoach-AI`) | DevSecOps repo |
|--------------------------------|----------------|
| `backend/`, `frontend/`, `database/`, `docker/` | `apps/interviewcoach/aws/prod/` (scripts, CFN, nginx) |
| CI + Security workflows | Build, Deploy, Rollback workflows |
| Developer docs (`docs/`) | Ops docs (`apps/interviewcoach/docs/`) |

## When you need an infra change

1. Open a ticket or ask **Govardhan** / **Kishore**
2. DevSecOps edits `devsecops-platform/apps/interviewcoach/aws/prod/` and runs workflows from that repo
3. Application changes still go through PR → `release/<month>-<year>` here

See [DEPLOY.md](DEPLOY.md) and [infra/README.md](../infra/README.md).
