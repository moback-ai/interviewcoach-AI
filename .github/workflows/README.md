# Workflows (application repo — developers)

**Only CI and Security run here.** No build, deploy, merge, delete, or infra workflows.

| Workflow | When | Purpose |
|----------|------|---------|
| **CI** | PR / push to `release/**` | Frontend lint + build, backend pytest |
| **Security** | PR / push to `release/**` | Gitleaks, Trivy, Semgrep |

**All production operations** (build, deploy, rollback, monthly release, maintenance, AWS scripts) are **DevSecOps only** in `moback-ai/devsecops-platform`.

Developers: open a PR into **`release/<month>-<year>`** → pass CI + Security → ask Govardhan or Kishore to merge and deploy.

Ops docs: devsecops-platform → `apps/interviewcoach/docs/`
