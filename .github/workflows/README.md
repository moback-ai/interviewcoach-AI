# Workflows (application repo)

| Workflow | When | Purpose |
|----------|------|---------|
| **Security** | PR / push to `develop` | Gitleaks, Trivy, Semgrep |

**There is no production deploy workflow in this repo.**

Production deploy is **DevSecOps only** from `moback-ai/devsecops-platform` — see [docs/DEVSECOPS.md](../docs/DEVSECOPS.md).

Developers: open a PR → merge to `develop` → ask Govardhan or Kishore to deploy.
