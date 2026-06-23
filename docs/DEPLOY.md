# Deploy (application repo)

Production: **https://ugaanlabs.ai**

**Developers do not deploy.** Production deploy is **DevSecOps only** — see [DEVSECOPS.md](DEVSECOPS.md).

---

## Developers — release via PR

1. Open a **PR** into `develop` from `develop/<feature>`
2. Wait for **Security** CI (lint, tests, gitleaks)
3. Get **PR approval** and **merge**
4. In the PR (or Slack), **request deploy** from **Govardhan or Kishore**
5. DevSecOps deploys from `moback-ai/devsecops-platform` after merge

There is **no** deploy workflow on this repo. Do **not** use Actions → Run workflow for production.

---

## What to put in your PR

- What changed and how to test
- Whether you need a **production deploy** after merge (yes/no)
- Any DB migration notes (`database/**` changes)

---

## DevSecOps — deploy

1. Confirm merge commit on `develop`
2. `devsecops-platform` → **Actions** → **InterviewCoach · Deploy Production**
3. Input `app_git_ref` = merge SHA or `develop`

---

## Branches

| Branch | Use |
|--------|-----|
| `develop/<feature>` | Your work → PR into `develop` |
| `develop` | Integration; DevSecOps deploys from here |
| `main` | Snapshot only — **not** deployed |
