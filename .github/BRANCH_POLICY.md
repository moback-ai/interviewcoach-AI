# Deployment and Branch Governance Policy

## Admin approvers

- `@govardhanreddy66`
- `@KFKishore23`

## Pull request rules

- All changes targeting `main` must go through a pull request.
- Exactly one admin approval from Govardhan or Kishore is required before merge.
- Direct pushes to `main` are not allowed.
- Routine Teams notifications are not required for every merge or deployment.

## Deployment rules

- A merge into `main` deploys only after the merged pull request has at least one admin approval.
- The deployment workflow deploys the latest approved commit on `main`.
- The deployment workflow does not require a second protected-environment approval on top of the approved pull request.
- If deployment fails, the app rolls back to the last stable release.
- The last stable release is updated only after a full successful deployment.

## Logs

- Live deployment logs are published over HTTP at `/logs/live.html`.
- Raw and archived log files are exposed at `/logs/files/`.
- Recent logs stay available for debugging.

## Log retention

- Deployment logs are zipped before cleanup.
- Log maintenance runs monthly.
- If total log storage exceeds 2 GB, older logs are archived and cleaned while recent logs are retained.

## Branch cleanup

- Branch cleanup runs monthly.
- Feature branches older than 30 days are treated as stale.
- Branches already merged into `main` are deleted automatically by the cleanup workflow.
- Old unmerged branches are reported for admin review before deletion.

## Required GitHub settings

1. Require a pull request before merging into `main`.
2. Require 1 approving review on `main`.
3. Require the `Enforce Policy` status check from the `PR Governance` workflow.
4. Block direct pushes to `main`.
5. Keep auto-delete branch enabled after merge if available.
