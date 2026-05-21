# Deploy (simple)

Production site: **https://ugaanlabs.ai**

---

## Day-to-day: ship `develop` to production

1. **Merge your feature PR into `develop`** (one PR per feature).

2. **Run deploy**  
   GitHub → **Actions** → **Deploy · Production** → **Run workflow**
   - Branch: `develop`
   - Deploy target: `auto`
   - Click **Run workflow**

3. **Approve production** (second admin)  
   When the run pauses, open the run → **Review deployments** → **Approve** `production`.

4. **Wait for green** (~10–15 minutes).  
   Failed deploys **roll back automatically** — do not merge broken code.

5. **Quick check**
   - https://ugaanlabs.ai/api/health → `"status":"healthy"`
   - https://ugaanlabs.ai/login → page loads, password field visible

---

## Release to `main` (one PR, no deploy)

Use **one PR: `develop` → `main`** when you want `main` to match what is live.

- Example: [PR #72](https://github.com/moback-ai/interviewcoach-AI/pull/72)
- Needs **admin approval** on the PR (branch protection).
- **Does not deploy** — production is already updated from `develop`.

---

## What `auto` deploys

| Changed files | What updates |
|---------------|--------------|
| `frontend/**` | Website (login, dashboard, interview UI) |
| `backend/**` | API server |
| AI scripts / both | AI host (if configured) |

---

## Branches (short)

| Branch | Use |
|--------|-----|
| `develop/<feature>` | Your work → PR into `develop` |
| `develop` | Deploy to production |
| `main` | Stable snapshot only (merge from `develop`) |

---

## Security scans

Run automatically on every PR to `develop`.  
Manual: **Actions** → **Security** → Run workflow.

Workflow index: [.github/workflows/README.md](../.github/workflows/README.md)

Details: [SECURITY_SCANNING.md](SECURITY_SCANNING.md)
