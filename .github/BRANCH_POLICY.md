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

- Deployments are manual only through `.github/workflows/deploy.yml` using `workflow_dispatch`.
- A human must explicitly provide:
  - `git_ref`
  - target `environment` (`dev` / `uat` / `prod`)
  - deploy target (`all` / `frontend` / `backend` / `database`)
  - explicit confirmation text `APPROVED`
- Deployments require protected GitHub Environment approval by admins for the selected environment.
- Manual deployment dispatch is additionally limited to approved admins, or approved automation with an `approved_by` value.
- Without explicit approval, deployment is blocked.

## 3) Notifications (admins only)

Use GitHub notification routing so only admins are recipients for:

- merge events
- deployment events
- deployment failures

Recommended implementation:

- Route workflow failure/deploy notifications to admin-only Slack/Teams/email destinations.
- Keep repository watchers limited to admins for deploy channels.

## 4) Observability & Logs

The deployment workflow publishes live deployment logs over HTTP/HTTPS:

- live deployment log page: `/logs/live.html`
- raw and archived log files: `/logs/files/`
- stable deployment metadata: `/logs/files/live/latest-stable.json`

The backend admin logs page also exposes authenticated, admin-only live runtime streams and archived log downloads.

For full runtime observability requirements (CPU, memory, disk, API latency, uptime, errors, and container health), integrate the deployment/runtime infrastructure with a monitoring stack such as Grafana/Loki/Prometheus, CloudWatch, or another approved provider.

## 5) Rollback & Stable Release Tracking

- If deployment fails, the workflow rolls back frontend/backend to the last stable release.
- The last stable release is updated only after a successful deployment.
- Deployment status, selected ref, resolved commit, approver, environment, and log URLs are recorded in GitHub Actions summaries and live deployment logs.

## 6) Log Retention

- Deployment logs are zipped before cleanup.
- Log maintenance runs monthly.
- If total log storage exceeds 2 GB, older logs are archived and cleaned while recent logs are retained.
