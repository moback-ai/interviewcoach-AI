# Branch policy (short)

| Branch | Purpose |
|--------|---------|
| `develop/<feature>` | Feature work → one PR into `develop` |
| `develop` | **Deploy to production** |
| `main` | Stable copy of production — **one PR** from `develop`, no deploy |

## Deploy & release

**See [docs/DEPLOY.md](../docs/DEPLOY.md)** — simple steps (5 steps to production).

## Rules

- Every production deploy needs **admin PR approval** + **production environment approval** in GitHub Actions.
- Failed deploy **rolls back** automatically.
- Do not merge PRs labeled `deploy-failed`.

## Security

**Veracode** runs on every production deploy. See [docs/SECURITY_SCANNING.md](../docs/SECURITY_SCANNING.md).
