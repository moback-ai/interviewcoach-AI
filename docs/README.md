# Documentation (application repo)

This folder is for **developers** working in `moback-ai/interviewcoach-AI`.

**Architecture, DevSecOps, deploy, budget, runbooks, and diagrams** live in the private DevSecOps repo only:

**`moback-ai/devsecops-platform`** → `apps/interviewcoach/docs/`  
Ask **Govardhan** or **Kishore** for access.

---

## Contributing

1. Branch from `develop`: `develop/<feature>`
2. Open a **PR** into `develop`
3. Pass **Security** CI (Gitleaks, Trivy, Semgrep) — see [SECURITY_SCANNING.md](SECURITY_SCANNING.md)
4. Request **DevSecOps** review and merge (developers do not merge)
5. Ask DevSecOps for production **build + deploy** when needed

Do **not** run `infra/prod/scripts/*` from this repo.

---

## Docs in this repo

| Document | Purpose |
|----------|---------|
| [SECURITY_SCANNING.md](SECURITY_SCANNING.md) | Security CI on PRs |
| [DEV_ACCESS.md](DEV_ACCESS.md) | CloudWatch log access (developers) |
| [SECRETS_ONLY.md](SECRETS_ONLY.md) | How prod config loads (local dev vs Secrets Manager) |

---

## Ops docs (DevSecOps repo)

| Document | Purpose |
|----------|---------|
| `DEVSECOPS_GUIDE.md` | Roles, CI/CD, playbooks |
| `ARCHITECTURE.md` | AWS overview |
| **`ARCHITECTURE_PORTS_AND_SECURITY.md`** | **Ports, security groups, network diagram** |
| **`OBSERVABILITY.md`** | **CloudWatch; retired `/admin/logs` URLs** |
| `CAPACITY_AND_BUDGET.md` | Cost and concurrency |
| `DEPLOY.md` / `PROD_RUNBOOK.md` | Release and bootstrap |
