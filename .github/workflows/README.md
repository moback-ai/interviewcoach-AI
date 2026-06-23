# Workflows

| Workflow | When | Runs |
|----------|------|------|
| **Security** | **Every PR** | **PR security gate** — must pass before merge |
| **Security** | Weekly Mon or manual | Full CodeQL, Trivy, Semgrep, e2e |
| **Deploy · Production** | **Merge PR → develop** | Approve production → **security gate** → deploy |
| **Veracode Scan** | Manual | One policy scan (needs API secrets) |
| **Maintenance · Scheduled** | Cron | Log cleanup, etc. |

## On merge to develop

```
Merge PR → develop
    ↓
Deploy · Production
    ├─ Resolve context
    ├─ Authorize
    ├─ Approve production  ← admin
    ├─ Security gate       ← scan before SSH deploy
    └─ Deploy to servers
```

PR **security gate** runs while the PR is open. The same checks run again at deploy time on the merged commit.

Details: [docs/DEPLOY.md](../../docs/DEPLOY.md)
