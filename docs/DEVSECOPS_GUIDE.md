# DevSecOps documentation (moved)

**Production operations docs** — roles, architecture diagrams, deploy playbooks, runbooks — live in the **private** DevSecOps repo:

**`moback-ai/devsecops-platform`** → `apps/interviewcoach/docs/`

| Doc (DevSecOps repo) | Contents |
|----------------------|----------|
| `DEVSECOPS_GUIDE.md` | Main reference — Mermaid diagrams, CI/CD, playbooks |
| `ARCHITECTURE.md` | AWS topology, request flow |
| `DEPLOY.md` | Build once → deploy rollout |
| `PROD_RUNBOOK.md` | Infra bootstrap |
| `diagrams/` | Draw.io exports + diagram index |

Ask **Govardhan** or **Kishore** for access.

---

## In this repo (developers)

| Doc | Contents |
|-----|----------|
| [DEVSECOPS.md](DEVSECOPS.md) | PR flow, who merges, who deploys |
| [DEV_ACCESS.md](DEV_ACCESS.md) | CloudWatch log access |
| [SECURITY_SCANNING.md](SECURITY_SCANNING.md) | Security CI (Gitleaks, Trivy, Semgrep) |
| [SECRETS_ONLY.md](SECRETS_ONLY.md) | Prod secrets model + local dev |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Application stack (summary) |
