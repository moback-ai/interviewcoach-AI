# Branch Governance & Deployment Policy

This repository enforces **admin-gated PR merges and deployments** through GitHub Branch Protection, CODEOWNERS, and GitHub Actions environments.

## 1) Branch Protection (apply to `main` and `develop`)

Configure in **Settings → Branches** (or org-level Rulesets):

- ✅ **Require a pull request before merging**.
- ✅ **Require approvals** = `1` minimum.
- ✅ **Dismiss stale approvals** when new commits are pushed.
- ✅ **Require review from Code Owners** (admins are code owners).
- ✅ **Restrict who can dismiss PR reviews** to admins only.
- ✅ **Block force pushes**.
- ✅ **Do not allow bypassing branch protections** (except repository admins if your org policy requires).
- ✅ **Require status checks to pass** before merge:
  - `Code Quality & Security / lint-and-scan`
- ✅ **Restrict who can push to matching branches** to no one (except automation if explicitly needed).

### Admin approval semantics

- Any one admin approval is sufficient, because `required approvals = 1` and admins are listed in `.github/CODEOWNERS`.

## 2) Deployment Approval & Manual Trigger

- Deployments are **manual only** through `.github/workflows/deploy.yml` using `workflow_dispatch`.
- A human must explicitly provide:
  - `git_ref`
  - target `environment` (`dev` / `uat` / `prod`)
  - explicit confirmation text `APPROVED`
- Deployments also require **environment protection approval** in GitHub Environments by admins.
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

For runtime observability requirements (CPU, memory, disk, API latency, uptime, errors, and container health), expose:

- live logs via HTTP/HTTPS (e.g., Grafana/Loki/Kibana)
- real-time log search/filtering
- metrics dashboards and alerting

> This is delivered by deployment/runtime infrastructure and monitoring stack integration, not by branch protection alone.
