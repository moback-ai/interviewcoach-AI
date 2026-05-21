# Workflows

| Workflow | When it runs | What you do |
|----------|----------------|-------------|
| **Security** | Every PR + push to `develop` | Nothing — automatic |
| **Deploy · Auto (develop)** | Push / merge to `develop` (with admin-approved PR) | Approve `production` in the deploy run |
| **Deploy · Production** | Manual, or triggered by Auto | Actions → Run → branch `develop`, target `auto` |
| **Maintenance · Scheduled** | Weekly / monthly cron | Nothing — automatic |
| **Security · Veracode** | Manual only | Add Veracode secrets, then Run |

`main` is **not** deployed. Use **Deploy · Production** from `develop` only.

Simple steps: [docs/DEPLOY.md](../../docs/DEPLOY.md)
