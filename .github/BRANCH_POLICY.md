# Branch policy

**All ops documentation:** `moback-ai/devsecops-platform` → `apps/interviewcoach/docs/DEVSECOPS_GUIDE.md` (private)

**Developers:** [docs/README.md](../docs/README.md)

| Branch | Purpose |
|--------|---------|
| `release/<month>-<year>` | **Active month** — open PRs here (e.g. `release/july-2026`) |
| Feature branches | Branch from current release → PR into release only |
| `develop` | Integration — **auto-merged from release at month-end** |
| `main` | Production mirror — **DevSecOps merge only** |

Do **not** open PRs to `develop` or `main`.

## Who approves and merges PRs

**Only DevSecOps** may approve and merge pull requests:

| DevSecOps | GitHub |
|-----------|--------|
| Govardhan | `@govardhanreddy66` |
| Kishore | `@KFKishore23` |

Developers (ganesh, neeraj) open PRs into the **release branch**; they do **not** merge.

Enforced via `.github/CODEOWNERS` (required review from DevSecOps).

## Deploy flow

1. **PR** — pass CI + Security in `interviewcoach-AI` (target: `release/<month>-<year>`)
2. **Merge** — DevSecOps merges into the release branch
3. **Build** — devsecops-platform → **InterviewCoach · Build Production** (uses release branch only)
4. **Deploy** — **InterviewCoach · Deploy Production** (auto tag from latest build)

Build and deploy **never** use `develop` or `main` for app code.

Details: devsecops-platform → `apps/interviewcoach/docs/DEPLOY.md`

## ASG schedule (IST)

| Time | API instances |
|------|----------------|
| **10:00–19:00** | At least **1** (scale up to **4** if CPU > 70%) |
| **After 19:00** | **0** (cost saving) |

CPU autoscale only runs during business hours when `min ≥ 1`.
