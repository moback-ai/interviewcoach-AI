# Deploy (simple)

Production: **https://ugaanlabs.ai**

Workflow index: [.github/workflows/README.md](../.github/workflows/README.md)

**Production checklist ($650, Plan B, Mon–Fri 10am–7:30pm IST):** [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)

---

## Release flow

1. Open PR → **`develop`**
2. Wait for **Security scan** (one check — all free scanners inside)
3. **Merge**
4. **Deploy · Production** → approve **production** → **Security scan** again → deploy
5. Verify https://ugaanlabs.ai/api/health and /login

---

## Manual deploy (fallback)

**Actions → Deploy · Production → Run workflow**

- `git_ref`: `develop` or commit SHA
- `deploy_target`: `auto` or `all`
- Approve **`production`** → Veracode scan → deploy

`main` is **never** deployed.

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

Details: [SECURITY_SCANNING.md](SECURITY_SCANNING.md)
