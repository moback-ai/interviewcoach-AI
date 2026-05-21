# Deploy (simple)

Production: **https://ugaanlabs.ai**

Workflow index: [.github/workflows/README.md](../.github/workflows/README.md)

---

## Normal release (no manual button)

1. Open PR: `develop/<your-feature>` → **`develop`**
2. Get **admin approval** on the PR (@govardhanreddy66 or @KFKishore23)
3. **Merge** the PR into `develop`
4. **Deploy · Auto (develop)** starts **Deploy · Production** automatically
5. Second admin: open the run → **Review deployments** → **Approve** `production`
6. Wait for green (~10–15 min). Failed deploys **roll back** automatically.
7. Check:
   - https://ugaanlabs.ai/api/health → `"status":"healthy"`
   - https://ugaanlabs.ai/login → password field visible

Do **not** merge PRs labeled `deploy-failed`.

---

## When you need the manual button

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

## Security scans

Automatic on every PR to `develop`.

Manual: **Actions** → **Security** → Run workflow.

Details: [SECURITY_SCANNING.md](SECURITY_SCANNING.md)
