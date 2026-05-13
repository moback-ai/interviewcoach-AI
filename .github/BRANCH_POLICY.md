# Branch Governance Policy

## Admin approvers

- `@govardhanreddy66`
- `@KFKishore23`

## Merge rules

- All changes targeting `main` must go through a pull request.
- Non-admin pull requests targeting `main` must be approved by Govardhan or Kishore before merge.
- Admin-authored feature branches do not require a second admin approval, but they should still use a pull request into `main`.
- The team must be notified before any pull request is merged.
- Nobody should merge directly into `main` without following this flow.

## Deployment rules

- A merge into `main` should trigger deployment automatically.
- The deployment workflow continues to respect any protected-environment approvals configured in GitHub.

## Branch cleanup

- Branch cleanup runs monthly.
- Feature branches older than 30 days are treated as stale.
- Branches already merged into `main` are deleted automatically by the cleanup workflow.
- Old unmerged branches are reported for admin review before deletion.

## Required GitHub settings

Apply these repository settings in GitHub so the policy is enforced on `main`:

1. Require a pull request before merging.
2. Block direct pushes to `main`.
3. Require the `Enforce Policy` status check from the `PR Governance` workflow.
4. Keep auto-delete branch enabled after merge if the repository setting is available.

The repo files in this folder support those settings, but GitHub branch protection still has to be enabled in the repository settings UI.
