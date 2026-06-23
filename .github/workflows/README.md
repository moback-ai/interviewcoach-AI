# Workflows

| Workflow | When | Runs |
|----------|------|------|
| **Deploy · Production** | Merge PR → `develop` or manual | Approve production → **Veracode scan** → deploy |
| **Maintenance · Scheduled** | Cron | Log cleanup, etc. |

## On merge to develop

```
Merge PR → develop
    ↓
Deploy · Production
    ├─ Resolve context
    ├─ Authorize
    ├─ Approve production  ← admin
    ├─ Veracode scan       ← only security scan
    └─ Deploy to servers
```

Details: [docs/DEPLOY.md](../../docs/DEPLOY.md)
