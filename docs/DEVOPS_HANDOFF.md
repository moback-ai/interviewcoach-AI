# DevOps handoff — InterviewCoach (dev team)

**Site:** https://ugaanlabs.ai  
**API health:** https://ugaanlabs.ai/api/health  
**Repo:** https://github.com/moback-ai/interviewcoach-AI  
**Region:** `ap-south-1`

---

## What was updated

### Infrastructure

- Split setup: Frontend | API | AI (Ollama) | RDS
- Servers run **Mon–Fri 10:00–19:30 IST** only (off weekends and outside those hours)

### Application

- One Ollama call per interview turn
- Live text streaming during AI replies in the interview UI
- Queue when interview AI is busy
- Voice transcription on the **AI server** (internal, not public)
- Deploy checks on PR: lint, pytest, gitleaks (quick check); full Security scan weekly or manual

### Related docs

- [DEPLOY.md](DEPLOY.md)
- [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)

---

## Production hosts

| Role | Public IP | Private IP |
|------|-----------|------------|
| Frontend | `3.110.248.130` | `172.31.2.39` |
| API | `15.207.92.161` | `172.31.36.78` |
| AI | `13.200.28.73` | `172.31.46.208` |

---

## Rules for developers (push & deploy)

- Work on `develop/<your-feature>` → PR into **`develop`**
- **Do not push directly to `develop`**
- Merge PR into **`develop`** → **Deploy · Production** runs once → **production** approval (**@govardhanreddy66** / **@KFKishore23**)
- PR **GitHub Approve** review before merge is **not** required
- Production deploys from **`develop` only** — `main` is not deployed
- Manual deploy: **Actions → Deploy · Production** → `git_ref` = `develop` → admin approves **production** environment
- After deploy, verify:
  - https://ugaanlabs.ai/api/health
  - https://ugaanlabs.ai/login

---

## Log URLs (browser)

| What | URL |
|------|-----|
| **Admin log viewer** (login as admin) | https://ugaanlabs.ai/admin/logs |
| Live tail — backend | https://ugaanlabs.ai/admin/logs?view=live&source=server-backend |
| Live tail — backend errors | https://ugaanlabs.ai/admin/logs?view=live&source=backend-error |
| Live tail — API failures | https://ugaanlabs.ai/admin/logs?view=live&source=api-failures |
| Live tail — deploy | https://ugaanlabs.ai/admin/logs?view=live&source=deployment-live |
| Live tail — frontend / nginx | https://ugaanlabs.ai/admin/logs?view=live&source=server-frontend |
| Live tail — AI / Ollama | https://ugaanlabs.ai/admin/logs?view=live&source=server-ai |
| **Public logs hub** | https://ugaanlabs.ai/logs/ |
| Live deploy file (HTTP) | https://ugaanlabs.ai/logs/files/live/deploy-current.log |
| Live logs page | https://ugaanlabs.ai/logs/live.html |

### Log sources in admin UI

`deployment-live`, `api-failures`, `server-backend`, `server-frontend`, `server-ai`, `server-db`, `backend-error`, `backend-out`, `frontend-access`, `database`, `ai-diagnostics`

---

## Logs (SSH — if admin UI is not enough)

| Service | Command / path |
|---------|----------------|
| API | `pm2 logs backend` (on API host) |
| AI / Ollama | `journalctl -u ollama` (on AI host) |
| Whisper | `pm2 logs transcribe` (on AI host, if voice is used) |
| Web | `/var/log/nginx/` (on frontend host) |

---

## Code checks — what runs, pass vs fail

### On every PR (workflow: **Security · PR quick check**)

Runs when you open/update a PR to `develop` or `main` (changed areas only).

| Check | Pass | Fail (PR shows red) |
|-------|------|---------------------|
| Frontend ESLint | No blocking errors on changed files | Lint errors |
| Backend pytest | `backend/tests/` pass (if backend changed) | Any test failure |
| Gitleaks | No secrets in changed commits | Secret detected |

**Fix:** open the failed PR → **Checks** tab → read the red job log → fix code → push again.

---

### Full Security scan (weekly Mon or manual)

| Check | Pass | Fail |
|-------|------|------|
| Frontend production build | `npm run build` succeeds | Build error |
| Login bundle guard | Password field not broken by bad JS chunks | Bundle script fail |
| Playwright smoke | `/login` and `/forgot-password` e2e | E2E timeout or assertion fail |
| npm audit | No **high+** vulnerabilities | High/critical npm issues |
| pip-audit | Production deps clean | Known vulns in requirements |
| Bandit | Python security scan (backend) | High-severity findings |
| Semgrep | `p/ci` rules | Rule violations (`--error`) |
| Trivy | Filesystem scan | **CRITICAL** or **HIGH** CVEs |
| CodeQL | JS/TS + Python SAST | GitHub security alerts (advisory) |

Run manually: **Actions → Security → Run workflow**.

---

### On merge to develop (workflow: **Deploy · Production**)

**No** separate quality gate or Security run on push. Merge triggers **one** Deploy · Production run.

| Step | What happens |
|------|----------------|
| Resolve context | Validates PR merge (skips direct push to `develop`) |
| Authorize | Confirms admin-approved merge |
| Approve production | Admin approves GitHub `production` environment |
| Deploy | SSH to EC2 + RDS migrations; rollback on failure |

**Common deploy failures (not code):**

| Issue | What devs see |
|-------|----------------|
| Direct push to `develop` (no PR merge) | Deploy skipped |
| Production environment not approved | Deploy job waits/fails until admin approves in Actions |

---

### Run checks locally (before PR)

```bash
# Frontend
cd frontend && npm ci --legacy-peer-deps
npm run lint
npm run build
bash ../scripts/verify-frontend-login-bundle.sh dist

# Backend
pip install -r backend/requirements.txt pytest
python -m pytest backend/tests/ -q
```

---

### Production runtime errors (live site — not CI)

| Symptom | Likely cause | Where to look |
|---------|----------------|---------------|
| `503` / “AI is busy” on interview | Too many parallel interviews | Admin logs → `api-failures` |
| Connection / timeout errors | Before 10:00 or after 19:30 IST Mon–Fri, or anytime Sat–Sun | EC2/RDS stopped by daily schedule |
| Interview slow / timeout message | Ollama slow or overloaded | `server-ai`, `backend-error` |
| Voice not transcribing | Whisper sidecar down on AI | `server-ai`, `pm2 logs transcribe` |
| Login page blank / no password field | Bad frontend chunk split | Re-run login bundle script locally |

---

## Log access — request, approval, grant, revoke

Admin logs are **not public**. Access is granted only after an approved **domain email** request. There is **no shared DevOps mailbox** — use the approvers’ **personal moback.com emails** below. **Slack** is for pings only; approval must be on the **email thread**.

**Log viewer:** https://ugaanlabs.ai/admin/logs (after access is granted)

**GitHub / deploy admins (unchanged — do not add log viewers here):** only **@govardhanreddy66** and **@KFKishore23** can approve PRs and production deploys. `ADMIN_LOG_VIEWER_EMAILS` gives **app log UI only** — not GitHub repo access, not merge rights, not AWS.

**Contacts (approvers + grant access on server):**

| Channel | Contact |
|---------|---------|
| Email | `govardhanr@moback.com`, `kishoren@moback.com` |
| Slack | **Govardhan Reddy G**, **Kishore** (optional ping only) |

---

### Quick guide — how to request (for devs)

1. Send email **To:** `govardhanr@moback.com`, `kishoren@moback.com` (both addresses — or **To** one, **Cc** the other).
2. Use subject: `[Log Access] Request — <Your Name> — <YYYY-MM-DD>`
3. Include: app username, app email, reason, from/until dates (template below).
4. Optional: Slack message to **Govardhan Reddy G** or **Kishore** — “Sent log access email, subject: …”
5. Wait for **Approved** reply on the same email thread, then **Access granted** reply.
6. Log in at https://ugaanlabs.ai and open https://ugaanlabs.ai/admin/logs

**Slack-only requests are not accepted** — send email first.

---

### Quick guide — how to approve (Govardhan / Kishore)

**If request came by email:**

1. Open the email thread.
2. **Reply all** with the Approval template below.
3. Whoever has server access: add user to `ADMIN_LOG_VIEWER_USERNAMES` and/or `ADMIN_LOG_VIEWER_EMAILS` (AWS Secrets Manager), restart API (`apply-backend-env.sh --apply` or `pm2 restart backend` on API host).
4. **Reply all** again with the Grant template below.

**If request came by Slack only:**

Reply: *“Please email govardhanr@moback.com and kishoren@moback.com with the log access request details. We approve on the email thread only.”*

---

### Full flow

1. Requester emails **both** approvers (see template)
2. Optional Slack ping for visibility
3. **Govardhan** or **Kishore** replies **Approved** on same thread
4. Approver (or whoever runs AWS) updates env + restarts API
5. Approver sends **Access granted** on same thread
6. On expiry/offboarding: remove from env, restart, send **Revoke** email

### Email template — Request (requester → approvers)

```
Subject: [Log Access] Request — <Your Name> — <YYYY-MM-DD>

To: govardhanr@moback.com, kishoren@moback.com

Hi,

I request access to production admin logs for InterviewCoach.

App username: <username>
App email: <your@moback.com or login email>
Reason: <incident / debugging / release support — be specific>
Access needed from: <YYYY-MM-DD>
Access needed until: <YYYY-MM-DD> (max 30 days unless approved otherwise)

I confirm I will not share log contents outside the team and will use access only for the stated reason.

Thanks,
<Name>
```

### Email template — Approval (Govardhan or Kishore — reply all)

```
Subject: Re: [Log Access] Request — <Name> — <YYYY-MM-DD>

Approved.

Approver: <Govardhan Reddy G / Kishore>
Approved for: <username / email>
Valid from: <YYYY-MM-DD>
Valid until: <YYYY-MM-DD>

Will grant access on server and confirm on this thread.
```

### Email template — Grant (reply all after env update + restart)

```
Subject: Re: [Log Access] Request — <Name> — <YYYY-MM-DD>

Access granted.

User: <username> / <email>
Granted at: <YYYY-MM-DD HH:MM IST>
Expires: <YYYY-MM-DD>
URL: https://ugaanlabs.ai/admin/logs

Please log in with your app account and open the link above.
If access does not work within 15 minutes, reply on this thread.

<Govardhan / Kishore>
```

### Email template — Revoke (DevOps reply-all on same thread)

```
Subject: Re: [Log Access] Request — <Name> — access revoked

Log access has been revoked for <username / email> as of <YYYY-MM-DD HH:MM IST>.

Reason: <expiry / offboarding / request closed>

<Govardhan / Kishore>
```

### Checklist — grant (Govardhan / Kishore)

- [ ] Approval email present on thread from **`govardhanr@moback.com` or `kishoren@moback.com`**
- [ ] Add to `ADMIN_LOG_VIEWER_USERNAMES` and/or `ADMIN_LOG_VIEWER_EMAILS` in Secrets Manager
- [ ] `apply-backend-env.sh --apply` or `pm2 restart backend` on API host
- [ ] Send Grant email with expiry date
- [ ] Calendar reminder to revoke on expiry date

### Checklist — revoke (Govardhan / Kishore)

- [ ] Remove username/email from viewer lists
- [ ] Restart backend
- [ ] Send Revoke email
- [ ] Confirm user cannot open `/admin/logs`

---

## Status

- Production is live and synced on GitHub
- Devs: pull **`develop`** and branch from it for new work
- Log access: email **govardhanr@moback.com** + **kishoren@moback.com** (no shared DevOps mailbox); Slack **Govardhan Reddy G** / **Kishore** for pings only
