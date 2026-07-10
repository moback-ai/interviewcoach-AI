# Documentation (application repo)

This folder is for **developers** working in `moback-ai/interviewcoach-AI`.

**Architecture, DevSecOps, deploy, budget, runbooks, and diagrams** live in the private DevSecOps repo only:

**`moback-ai/devsecops-platform`** → `apps/interviewcoach/docs/`  
Ask **Govardhan** or **Kishore** for access.

---

## Contributing

1. Branch from the current **`release/<month>-<year>`** (e.g. `release/july-2026`)
2. Open a **PR** into that **release branch** only (not `develop` or `main`)
3. Pass **CI** (lint, build, pytest) and **Security** (Gitleaks, Trivy, Semgrep) — see [SECURITY_SCANNING.md](SECURITY_SCANNING.md)
4. Request **DevSecOps** review and merge (developers do not merge)
5. Ask DevSecOps for **Build Production** + **Deploy Production** when ready

Infrastructure and AWS scripts are **not** in this repo — see [infra/README.md](../infra/README.md).

---

## Docs in this repo

| Document | Purpose |
|----------|---------|
| [DEPLOY.md](DEPLOY.md) | Release flow, health checks, rollback, business hours |
| [SYNC_DEVSECOPS.md](SYNC_DEVSECOPS.md) | What lives in each repo (app vs DevSecOps) |
| [SECURITY_SCANNING.md](SECURITY_SCANNING.md) | Security CI on PRs |
| [DEV_ACCESS.md](DEV_ACCESS.md) | CloudWatch log access (developers) |
| [SECRETS_ONLY.md](SECRETS_ONLY.md) | How prod config loads (local dev vs Secrets Manager) |

---

## Ops docs (DevSecOps repo)

| Document | Purpose |
|----------|---------|
| `DEVSECOPS_HANDOFF.md` | **Start here** — current prod handoff |
| `SCRIPTS_GUIDE.md` | **Full script catalog and deploy flow** |
| `DEVSECOPS_GUIDE.md` | Roles, CI/CD, playbooks |
| `ARCHITECTURE_PORTS_AND_SECURITY.md` | Ports, security groups, network |
| `OBSERVABILITY.md` | CloudWatch; retired `/admin/logs` URLs |
| `DEPLOY.md` / `PROD_RUNBOOK.md` | Release and bootstrap |
