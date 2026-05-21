## Summary

- Describe the change.

## Branch

- [ ] Source branch uses `develop/<feature-name>` (not `feature/` or `main`)
- [ ] Target branch is `develop`

## Testing

- Describe what was tested.

## Security

- [ ] `Code Quality & Security` workflow is green (CodeQL, Trivy, Semgrep, audits)
- [ ] No secrets or credentials in the diff (Gitleaks / manual review)

## Governance Checklist

- [ ] Admin approval requested from @govardhanreddy66 or @KFKishore23 before merge into `develop`
- [ ] Admin approved this PR before deploy
- [ ] Admin approved the `production` environment in the deploy workflow
- [ ] Wait for production deploy of this branch to succeed (`deploy-verified` label)
- [ ] Do **not** merge if deploy failed (`deploy-failed` label)
- [ ] Deployment impact has been reviewed
