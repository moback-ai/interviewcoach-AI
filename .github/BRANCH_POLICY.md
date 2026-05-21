# Branch Governance & Deployment Policy

`develop` is the **primary integration branch**. `main` is the frozen baseline and is updated from `develop` **once per month** only.

## Branch model

| Branch | Purpose | Deploy | Merge policy |
|--------|---------|--------|----------------|
| `main` | Original / baseline code | **Never** | Monthly auto-sync from `develop` |
| `develop` | Shared integration | After **admin PR approval** + **production environment approval** | Admin-only PR merges |
| `develop/<feature>` | Developer feature work | Same dual approval; **no auto-merge** | Admin merges into `develop` only after **successful** deploy |

## Deployment approvals (all branches, including `develop/feat-*`)

Every production deploy requires **both**:

1. **Admin PR approval** — an open PR (`develop/feat-*` → `develop`) or merged PR (`develop`) with approval from @govardhanreddy66 or @KFKishore23
2. **Production environment approval** — an admin clicks **Review deployments → Approve** on the `production` environment in the `deploy.yml` run

Nothing is copied to servers until both gates pass.

## Failed deploy = automatic rollback

- Before deploy, the workflow snapshots the current **stable** release on each host.
- If health checks fail, the job restores `current` → `stable` immediately (per host).
- The finalize step runs a full rollback if any deploy stage fails.
- **Stable is promoted only after a fully successful deploy** — failed code is never promoted.

## Developer workflow

1. `git checkout develop && git pull`
2. `git checkout -b develop/feat-your-change`
3. Open PR → `develop` and get **admin approval** on the PR
4. Push commits → `auto-deploy-develop.yml` validates PR approval and starts `deploy.yml`
5. **Admin approves** the `production` environment in GitHub Actions
6. If deploy succeeds → label `deploy-verified` on the PR → **admin merges** manually
7. If deploy fails → label `deploy-failed`, servers stay on last stable — **do not merge**

## Triggers

| Event | Behavior |
|-------|----------|
| Push to `develop` / `develop/**` | Validates admin PR approval → dispatches `deploy.yml` |
| `deploy.yml` | Requires `production` environment approval → deploy with rollback |
| Push to `main` | No deploy |
| Monthly cron | `develop` → `main` only (no deploy) |

## GitHub settings (admin)

- Default branch: `develop`
- Protect `develop` and `main` (PR required, code owners, lint check)
- **Disable auto-merge** on PRs
- `production` environment: required reviewers = admins only
- Labels: `deploy-verified`, `deploy-failed`, `admin-merge-required`

## Logs, rollback detail, toolchain

HTTP logs, per-step rollback, host toolchain updates, and log retention behave as documented in the deploy workflow (`deploy.yml`).
