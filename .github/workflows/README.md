# Workflows

| Workflow | When it runs | What you do |
|----------|----------------|-------------|
| **Security** | PR → quick check only; full scan weekly (Mon) or manual | Nothing on PR merge |
| **Deploy · Auto (develop)** | **Merged PR** to `develop` | Approve `production` in deploy.yml |
| **Deploy · Production** | Auto-dispatch or manual | Approve `production` → deploy |
| **Maintenance · Scheduled** | Weekly / monthly cron | Nothing |
| **Security · Veracode** | Manual only | Optional |

## Auto-deploy flow (fast)

```
Merge PR → develop
    ↓
Deploy · Auto (develop)     ~30 sec — dispatches deploy.yml
    ↓
Deploy · Production
    ↓
Admin approves production   @govardhanreddy66 / @KFKishore23
    ↓
Deploy to servers           ~10–15 min
```

No pre-deploy quality gate. PR **Security · quick check** runs lint/pytest/gitleaks on changed files only.

Full CodeQL / Trivy / Semgrep / e2e: **weekly** or **Actions → Security → Run workflow**.

`main` is **not** deployed.

Details: [docs/DEPLOY.md](../../docs/DEPLOY.md)
