# Workflows

| Workflow | When it runs | What you do |
|----------|----------------|-------------|
| **Security** | Every PR + push to `develop` | Nothing — automatic |
| **Deploy · Auto (develop)** | Push / merge to `develop` (with admin-approved PR) | Quality gate runs first; then approve `production` in deploy |
| **Deploy · Production** | Manual, or triggered by Auto | Quality gate → approve `production` → deploy (rejected if gate fails) |
| **Maintenance · Scheduled** | Weekly / monthly cron | Nothing — automatic |
| **Security · Veracode** | Manual only | Add Veracode secrets, then Run |

`main` is **not** deployed. Use **Deploy · Production** from `develop` only.

Simple steps: [docs/DEPLOY.md](../../docs/DEPLOY.md)
