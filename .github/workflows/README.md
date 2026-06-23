# Workflows (application repo)

| Workflow | When | Who runs it |
|----------|------|-------------|
| **Security** | Every PR to `develop` / `main`; push to `develop` | Automatic |
| **Security · Veracode** | Manual (optional) | DevSecOps / security |

**Production deploy is not on this repo.** After your PR merges to `develop`, ask **Govardhan or Kishore** to deploy from `moback-ai/devsecops-platform`.

Details: [docs/DEVSECOPS.md](../../docs/DEVSECOPS.md) · [docs/DEPLOY.md](../../docs/DEPLOY.md)
