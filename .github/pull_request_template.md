## What changed

-

## Checklist

- [ ] Target branch is `develop` (feature PR) or `main` (release PR from `develop` only)
- [ ] Tested locally
- [ ] Security workflow green (if code changed)

## Deploy

**Feature PRs:** merge to `develop` → deploy runs automatically (admin approves production in Actions).

**Release PR (`develop` → `main`):** one PR only; see [docs/DEPLOY.md](../docs/DEPLOY.md).
