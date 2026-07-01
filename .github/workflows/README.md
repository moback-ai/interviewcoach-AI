# Workflows (application repo)

**Ops docs:** `moback-ai/devsecops-platform` → `apps/interviewcoach/docs/`  
**Developers:** [docs/README.md](../docs/README.md)

| Workflow | When | Purpose |
|----------|------|---------|
| **Security** | PR / push to `develop` | Gitleaks, Trivy, Semgrep |

**There is no production deploy workflow in this repo.**

Production deploy is **DevSecOps only** from `moback-ai/devsecops-platform`.

Developers: open a PR → pass Security CI → ask Govardhan or Kishore to merge and deploy.
