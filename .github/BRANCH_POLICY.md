# Branch Governance & Deployment Policy

`develop` is the **primary integration branch**. `main` is the frozen baseline and is updated from `develop` **once per month** only.

## Branch model

| Branch | Purpose | Deploy | Merge policy |
|--------|---------|--------|----------------|
| `main` | Original / baseline code | **Never** auto-deployed | Receives `develop` monthly (automated) |
| `develop` | Shared integration (same starting point as `main`) | Auto-deploy on push (after admin-approved PR merges) | Admin-only PR merges |
| `develop/<feature>` | Developer feature work (e.g. `develop/feat-login`) | Auto-deploy on every push | **No auto-merge**; admin merges into `develop` only after **successful** deploy |

## Developer workflow

1. Branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b develop/feat-your-change
   ```
2. Push commits — production deploy runs automatically for that branch.
3. Open a PR: **`develop/feat-your-change` → `develop`** (draft is fine until deploy passes).
4. Wait for deploy to succeed — workflow adds label `deploy-verified` and comments on the PR.
5. **Admin** reviews and merges the PR manually. Failed deploys get `deploy-failed` — do not merge.
6. Merging into `develop` triggers another deploy of `develop` (integration).

Direct pushes to `develop` and `main` should be blocked in branch protection.

## Deployment

| Trigger | Workflow |
|---------|----------|
| Push to `develop` or `develop/**` | `.github/workflows/auto-deploy-develop.yml` → `deploy.yml` |
| Push to `main` | Disabled (`.github/workflows/auto-deploy-main.yml`) |
| Manual | `deploy.yml` (`workflow_dispatch`), default ref `develop` |

Production environment approval still applies inside `deploy.yml`.

## Monthly `main` sync

`.github/workflows/monthly-sync-main-from-develop.yml` runs on the **1st of each month** (and can be run manually). It merges `develop` → `main` and does **not** deploy `main`.

## GitHub settings (repository admin)

Apply to **`develop`** and **`main`**:

- Require pull request before merging
- Require approvals: **1**
- Require review from Code Owners (`.github/CODEOWNERS`)
- Require status check: `Code Quality & Security / lint-and-scan`
- Block force pushes
- Restrict direct pushes (admins only if needed for break-glass)

Recommended:

- Set **default branch** to `develop`
- Do **not** enable auto-merge on PRs targeting `develop`
- Create labels (optional; workflows also create them): `deploy-verified`, `deploy-failed`, `admin-merge-required`

## Feature branch cleanup

`.github/workflows/monthly-branch-cleanup.yml` removes stale **merged** `develop/*` branches older than 30 days.

## Logs, rollback, toolchain

See previous sections in this file for HTTP logs, rollback behavior, host toolchain updates, and log retention (unchanged).
