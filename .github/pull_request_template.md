## What changed

-

## Checklist

- [ ] Target branch is `develop` (feature PR) or `main` (release PR from `develop` only)
- [ ] Tested locally

## Deploy

**Feature PRs:** merge to `develop` → **Deploy · Production** (Veracode scan, then deploy; admin approves production).

**Release PR (`develop` → `main`):** one PR only; see [docs/DEPLOY.md](../docs/DEPLOY.md).
