# Branch Governance & Deployment Policy

This repository enforces admin-gated PR merges and deployments through GitHub Branch Protection, CODEOWNERS, GitHub Actions status checks, and protected GitHub Environments.

## 1) Branch Protection (apply to `main` and `develop`)

Configure in Settings -> Branches, or org-level Rulesets:

- Require a pull request before merging.
- Require approvals = `1` minimum.
- Dismiss stale approvals when new commits are pushed.
- Require review from Code Owners.
- Restrict who can dismiss PR reviews to admins only.
- Block force pushes.
- Do not allow bypassing branch protections, except repository admins if org policy requires it.
- Require status checks to pass before merge:
  - `Code Quality & Security / lint-and-scan`
- Restrict who can push to matching branches to no one, except automation if explicitly needed.

### Admin approval semantics

- Any one admin approval is sufficient, because required approvals = `1` and admins are listed in `.github/CODEOWNERS`.
- Direct pushes to `main` and `develop` must be blocked by branch protection or rulesets.
- All merges into `main` and `develop` must happen through pull requests.

## 2) Deployment Approval & Manual Trigger

- Deployments are manual through `.github/workflows/deploy.yml` (`workflow_dispatch`) and may auto-dispatch after approved merges via `auto-deploy-main.yml`.
- A human must approve the protected GitHub Environment (`production`) before deploy steps run.
- Deploy target options: `all`, `frontend`, `backend`, `database`.

## 3) Requirement: HTTP logs (frontend, backend, database)

Production exposes logs over HTTPS at:

| URL | Content |
|-----|---------|
| `https://ugaanlabs.ai/logs/` | Log hub (static index) |
| `https://ugaanlabs.ai/logs/live.html` | Live deployment log (auto-refresh) |
| `https://ugaanlabs.ai/logs/files/live/deploy-current.log` | Raw deployment log file (public) |
| `https://ugaanlabs.ai/logs/api/<source>` | Runtime logs API (admin Bearer token) |
| `https://ugaanlabs.ai/admin/logs` | Admin UI for live streams and archives |

**Log sources** (via `/logs/api/` or admin UI):

- `backend-error`, `backend-out` — PM2 backend logs
- `frontend-access` — nginx access log (synced from frontend host to `/apps/logs/live/frontend-nginx.log`)
- `database` — PostgreSQL diagnostics snapshot
- `deployment-live` — current deploy log

Log files on the backend host: `/apps/logs` (`live/`, `archive/`).

## 4) Requirement: Rollback on deployment failure

- Before deploy, the workflow snapshots the current `stable` release symlink if missing.
- Backend and frontend deploy steps roll back to `stable` if health checks fail during the same step.
- If the deploy job fails, the **Roll Back To Last Stable Release** step restores:
  - Frontend `current` → last `stable` release
  - Backend `current` → last `stable` release
  - Database from pre-migration backup (when database deploy was selected)
- `stable` is updated only after a successful deploy (**Promote Stable Release**).

## 5) Requirement: Keep toolchain updated during deploy

On each deploy, target EC2 hosts run `scripts/deploy-host-toolchain.sh`:

- `apt-get update` and `apt-get upgrade` (Ubuntu packages)
- Node.js 22 LTS, latest npm, latest PM2
- nginx reload when present

The GitHub Actions runner builds with Node 22. Version audits in the workflow remain advisory for app dependencies.

## 6) Log Retention

- Deployment logs are zipped before cleanup (`scripts/log-maintenance.sh`).
- Monthly workflow: `.github/workflows/log-maintenance.yml`
- If total log storage exceeds 2 GB, older logs are archived and cleaned while recent logs are retained.
