# Deploy (simple)

Production: **https://ugaanlabs.ai**

Workflow index: [.github/workflows/README.md](../.github/workflows/README.md)

**Production checklist ($650, Plan B, Mon–Fri 10am–7:30pm IST):** [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)

---

## One PR per release (recommended)

Put **all** changes for a release in **one** PR: `develop/<feature>` → `develop`.

1. Investigate and test on the PR (Security runs on the PR).
2. Get **admin approval** on that PR.
3. **Merge once** → one auto-deploy (Option A) or use manual deploy (Option B) for the same commit.

Avoid direct pushes to `develop` and avoid many small merges — each merge triggers deploy workflows.

---

## Normal release

1. Open PR: `develop/<your-feature>` → **`develop`**
2. Wait for **PR security gate** green (gitleaks + lint/tests/audits on changed code)
3. **Merge** the PR into `develop`
4. **Deploy · Production** starts automatically
5. Admin approves **`production`** environment
6. **Security gate** runs again on the release commit, then deploy (~10–15 min)
7. Verify https://ugaanlabs.ai/api/health and /login

Do **not** merge PRs labeled `deploy-failed`.

### If auto-deploy failed after merge

Common cause: PR merged **without** admin `Approve` review (e.g. PR #73).

1. **Option B**: **Actions → Deploy · Production → Run workflow** → `git_ref` = `develop` → approve `production`.
2. Or: re-run the failed **Deploy · Production** workflow from the merge commit.

---

## Option B — manual deploy button

GitHub → **Actions** → **Deploy · Production** → **Run workflow** (top right)

Use it only if:

- Auto deploy did not start after merge
- You need to re-deploy the **same commit**
- You need `deploy_target: **all**` (force every box)

Inputs: `git_ref` = `develop` or a commit SHA, `deploy_target` = `auto` or `all`.

Alternative: **Deploy · Production** → **Run workflow** with `git_ref` = `develop` or a commit SHA.

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

## Security scans (before merge and before deploy)

| When | Gate | What runs |
|------|------|-----------|
| **Every PR** | **PR security gate** (must pass to merge) | Gitleaks, merge-conflict check, lint, build, npm/pip audit, Bandit, pytest (on changed areas) |
| **Before deploy** | **Security gate** in Deploy · Production | Same checks on the release commit (for boxes being deployed) |
| **Weekly / manual** | Full Security workflow | CodeQL, Trivy, Semgrep, Playwright e2e |
| **Manual** | **Veracode Scan** | One policy scan (needs API secrets) |

Do **not** merge if **PR security gate** is red. Deploy is blocked if **Security gate** fails after production approval.
