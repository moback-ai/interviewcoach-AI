# Infrastructure (DevSecOps repo only)

Production AWS scripts, CloudFormation, nginx, and deploy workflows live in the **private DevSecOps repo** — not here.

**Canonical path:** `moback-ai/devsecops-platform` → `apps/interviewcoach/aws/prod/`

| What | Where |
|------|--------|
| Prod scripts & CFN | `devsecops-platform/apps/interviewcoach/aws/prod/` |
| Build / deploy workflows | `devsecops-platform/.github/workflows/interviewcoach-*.yml` |
| Ops docs | `devsecops-platform/apps/interviewcoach/docs/` |

Developers: change application code in this repo (`backend/`, `frontend/`, `database/`, `docker/`). Ask **Govardhan** or **Kishore** for infra or deploy changes.
