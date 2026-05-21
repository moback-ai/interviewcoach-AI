# Workflows

Five workflows (not counting Dependabot). Fewer **runs**: feature branches only trigger **Security** on the PR; deploy runs after a **merged PR** to `develop` or manual dispatch.

| Workflow | When it runs | What you do |
|----------|----------------|-------------|
| **Security** | PR to `develop` / `main`; push to `develop` after merge; weekly cron | Nothing — automatic |
| **Deploy · Auto (develop)** | **Merged PR** to `develop`, or **Run workflow** (Option A) | Quality gate → approve `production` |
| **Deploy · Production** | Manual or triggered by Auto (Option B) | Quality gate → approve `production` |
| **Maintenance · Scheduled** | Weekly / monthly cron, or manual | Nothing — automatic |
| **Security · Veracode** | Manual only | Add Veracode secrets, then Run |

Direct pushes to `develop` do **not** deploy (use one merged PR or Option B).

Clear old runs: `./scripts/cleanup-github-actions-runs.sh --max 10 --days 2` (also daily via **Maintenance · Scheduled**)

`main` is **not** deployed.

Simple steps: [docs/DEPLOY.md](../../docs/DEPLOY.md)
