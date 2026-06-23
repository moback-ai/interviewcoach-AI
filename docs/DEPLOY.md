# Deploy (simple)

Production: **https://ugaanlabs.ai**

Workflow index: [.github/workflows/README.md](../.github/workflows/README.md)

**Production checklist ($650, Plan B, 10am–8pm IST):** [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)

---

## One PR per release (recommended)

Put **all** changes for a release in **one** PR: `develop/<feature>` → `develop`.

1. Investigate and test on the PR (Security runs on the PR).
2. Get **admin approval** on that PR.
3. **Merge once** → one auto-deploy (Option A) or use manual deploy (Option B) for the same commit.

Avoid direct pushes to `develop` and avoid many small merges — each merge triggers deploy workflows.

---

## Normal release — Option A (no manual button)

1. Open PR: `develop/<your-feature>` → **`develop`**
2. Get **admin approval** on the PR (@govardhanreddy66 or @KFKishore23) — **required before merge** or auto-deploy will fail
3. **Merge** the PR into `develop`
4. **Deploy · Auto (develop)** dispatches **Deploy · Production** (light gate: conflicts + pytest).
5. Admin approves **`production`** environment in **Deploy · Production**.
6. Wait for green (~10–15 min). Failed deploys **roll back** automatically.
7. Check:
   - https://ugaanlabs.ai/api/health → `"status":"healthy"`
   - https://ugaanlabs.ai/login → password field visible

Do **not** merge PRs labeled `deploy-failed`.

### If auto-deploy failed after merge

Common cause: PR merged **without** admin `Approve` review (e.g. PR #73).

1. **Option B**: **Actions → Deploy · Production → Run workflow** → `git_ref` = `develop` → approve `production`.
2. Or: ask an admin to **Approve** on the merged PR (if still possible), then re-run **Deploy · Auto (develop)** manually.

---

## Option B — manual deploy button

GitHub → **Actions** → **Deploy · Production** → **Run workflow** (top right)

Use it only if:

- Auto deploy did not start after merge
- You need to re-deploy the **same commit**
- You need `deploy_target: **all**` (force every box)

Inputs: `git_ref` = `develop` or a commit SHA, `deploy_target` = `auto` or `all`.

Alternative: **Deploy · Auto (develop)** → **Run workflow** with branch `develop` or `develop/feat-…` (still needs admin-approved PR rules).

`main` is **never** deployed.

---

## Update `main` (no deploy)

One PR: **`develop` → `main`** when you want `main` to match production.

- Needs **admin PR approval**
- **Does not deploy** — production already came from `develop`

Monthly sync can also open this PR automatically (`Maintenance · Scheduled`).

---

## What `auto` deploys

| Changed paths | Box |
|---------------|-----|
| `frontend/**` | Website |
| `backend/**` (not INTERVIEW/Piper only) | API |
| `backend/INTERVIEW/**`, `backend/Piper/**`, AI scripts | AI host |
| `database/**` | RDS migrations |

---

## Branches

| Branch | Use |
|--------|-----|
| `develop/<feature>` | Your work → PR into `develop` |
| `develop` | Deploy to production |
| `main` | Snapshot only |

---

## Pre-deploy quality gate (light — blocks bad releases)

Runs **once** in **Deploy · Production** before admin approves the `production` environment.

| Check | What it does |
|-------|----------------|
| Merge conflicts | Fails if the deploy ref would conflict with `develop` |
| Backend tests | `pytest backend/tests/` |

**Not repeated here** (already on every PR via **Security**): frontend lint, production build, login bundle check, e2e smoke, Bandit, Trivy, etc.

**Auto-deploy flow:** merge PR → **Deploy · Auto (develop)** dispatches **Deploy · Production** → light gate → admin approves `production` → deploy (~10–15 min).

---

## Security scans

Automatic on every PR to `develop` (separate from the deploy gate).

Manual: **Actions** → **Security** → Run workflow.

Details: [SECURITY_SCANNING.md](SECURITY_SCANNING.md)
