# Workflows

| Workflow | When | Runs |
|----------|------|------|
| **Security** | PR only (quick check) | Lint / pytest / Gitleaks on changed files |
| **Security** | Weekly Mon or manual | Full CodeQL, Trivy, OSV-Scanner, Semgrep, e2e |
| **Deploy · Production** | **Merge PR → develop** | **One run**: approve production → deploy |
| **Deploy · Production** | Manual dispatch | Same single workflow |
| **Maintenance · Scheduled** | Cron | Log cleanup, etc. |

## On merge to develop (one workflow run)

```
Merge PR #92 → develop
    ↓
Deploy · Production  (single run #63)
    ├─ Resolve context
    ├─ Authorize
    ├─ Approve production  ← admin
    └─ Deploy to servers
```

**No** separate Deploy · Auto run. **No** Security run on push to develop.

PR **Security · quick check** runs once while the PR is open (before merge).

Details: [docs/DEPLOY.md](../../docs/DEPLOY.md)
