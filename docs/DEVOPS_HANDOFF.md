# DevOps handoff — InterviewCoach (dev team)

**Site:** https://ugaanlabs.ai  
**API health:** https://ugaanlabs.ai/api/health  
**Repo:** https://github.com/moback-ai/interviewcoach-AI  
**Region:** `ap-south-1`

---

## What was updated

### Infrastructure

- Split setup: Frontend | API | AI (Ollama) | RDS
- Servers run **10:00–20:00 IST** only (off outside those hours)

### Application

- One Ollama call per interview turn
- Live text streaming during AI replies in the interview UI
- Queue when interview AI is busy
- Service blocked outside **10:00–20:00 IST**
- Voice transcription on the **AI server** (internal, not public)
- Deploy checks: lint, build, tests, merge conflicts before production

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
- **Admin approval** required before merge: **@govardhanreddy66** or **@KFKishore23**
- Production deploys from **`develop` only** — `main` is not deployed
- If deploy fails: **Actions → Deploy · Production → Run workflow** with `git_ref` = `develop`
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

### On every PR (workflow: **Security**)

Runs when you open/update a PR to `develop` or `main` (only changed areas, unless full scheduled run).

| Check | Pass | Fail (PR shows red) |
|-------|------|---------------------|
| Frontend ESLint | No blocking errors (up to **200 warnings** allowed) | Lint errors over limit |
| Frontend production build | `npm run build` succeeds | Build error |
| Login bundle guard | Password field not broken by bad JS chunks | `verify-frontend-login-bundle.sh` fails |
| Playwright smoke | `/login` and `/forgot-password` e2e | E2E timeout or assertion fail |
| Backend pytest | `backend/tests/` all pass | Any test failure |
| npm audit | No **high+** vulnerabilities | High/critical npm issues |
| pip-audit | Production deps clean | Known vulns in requirements |
| Bandit | Python security scan (backend) | High-severity findings |
| Semgrep | `p/ci` rules | Rule violations (`--error`) |
| Trivy | Filesystem scan | **CRITICAL** or **HIGH** CVEs |
| CodeQL | JS/TS + Python SAST | GitHub security alerts (advisory) |
| Gitleaks | No secrets in git history | Secret detected in commit |
| Governance scripts | Workflow YAML + shell scripts valid | Syntax/check script fail |

**Fix:** open the failed PR → **Checks** tab → read the red job log → fix code → push again.

---

### Before production deploy (workflow: **Quality gate**)

Runs automatically before **Deploy · Production**. **Deploy is blocked** if any step below fails.

| Check | Pass | Fail (deploy stopped) |
|-------|------|------------------------|
| Merge conflicts | No `<<<<<<<` vs `develop` | Conflicts with `develop` |
| Frontend ESLint | `npm run lint` clean | Lint errors |
| Frontend build | Production build OK | Build error |
| Login bundle guard | Login page bundle OK | Bundle script fail |
| Backend pytest | All unit tests pass | Test failure |

**Pass message in CI:** `Quality gate passed` — then production deploy can continue (after admin environment approval).

**Common deploy failures (not code):**

| Issue | What devs see |
|-------|----------------|
| PR merged without admin **Approve** | Auto-deploy skips or stops |
| Quality gate red | Fix code/conflicts, merge again or manual redeploy |
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
| “Outside operating hours” | Before 10:00 or after 20:00 IST | Service hours banner |
| Interview slow / timeout message | Ollama slow or overloaded | `server-ai`, `backend-error` |
| Voice not transcribing | Whisper sidecar down on AI | `server-ai`, `pm2 logs transcribe` |
| Login page blank / no password field | Bad frontend chunk split | Re-run login bundle script locally |

---

## Log access — request, approval, grant, revoke

Admin logs are **not public**. Access is granted only after an approved **domain email** request. Use **Slack** only to notify (not as the official approval record).

**Log viewer:** https://ugaanlabs.ai/admin/logs (after access is granted)

**Who can approve:** @govardhanreddy66 or @KFKishore23 (or designated admin on the email thread)

**DevOps mailbox (example):** `devops@ugaanlabs.ai` — replace with your real alias

### Flow

1. Requester sends **Request** email (template below) → DevOps + Admin CC
2. Admin replies on the **same thread** with **Approval** (template below)
3. DevOps adds username or email to AWS secret / API env:
   - `ADMIN_LOG_VIEWER_USERNAMES` and/or `ADMIN_LOG_VIEWER_EMAILS`
4. DevOps restarts API: `pm2 restart backend` (or `apply-backend-env.sh --apply`)
5. DevOps sends **Grant** email on the same thread
6. Optional: short Slack post — “Log access granted to &lt;user&gt; until &lt;date&gt;”
7. On expiry or offboarding: remove from env, restart backend, send **Revoke** email

### Email template — Request (requester → DevOps + Admin)

```
Subject: [Log Access] Request — <Your Name> — <YYYY-MM-DD>

To: devops@ugaanlabs.ai
Cc: <admin@ugaanlabs.ai>

Hi,

I request access to production admin logs for InterviewCoach.

App username: <username>
App email: <your@company-domain.com>
Reason: <incident / debugging / release support — be specific>
Access needed from: <YYYY-MM-DD>
Access needed until: <YYYY-MM-DD> (max 30 days unless approved otherwise)

I confirm I will not share log contents outside the team and will use access only for the stated reason.

Thanks,
<Name>
```

### Email template — Approval (admin reply-all on same thread)

```
Subject: Re: [Log Access] Request — <Name> — <YYYY-MM-DD>

Approved.

Approver: <Admin name>
Approved for: <username / email>
Valid from: <YYYY-MM-DD>
Valid until: <YYYY-MM-DD>

DevOps: please grant per SOP and reply when done.
```

### Email template — Grant (DevOps reply-all on same thread)

```
Subject: Re: [Log Access] Request — <Name> — <YYYY-MM-DD>

Access granted.

User: <username> / <email>
Granted at: <YYYY-MM-DD HH:MM IST>
Expires: <YYYY-MM-DD>
URL: https://ugaanlabs.ai/admin/logs

Please log in with your app account and open the link above.
If access does not work within 15 minutes, reply on this thread.

DevOps
```

### Email template — Revoke (DevOps reply-all on same thread)

```
Subject: Re: [Log Access] Request — <Name> — access revoked

Log access has been revoked for <username / email> as of <YYYY-MM-DD HH:MM IST>.

Reason: <expiry / offboarding / request closed>

DevOps
```

### DevOps checklist (grant)

- [ ] Approval email present on thread from authorized admin
- [ ] Add to `ADMIN_LOG_VIEWER_USERNAMES` and/or `ADMIN_LOG_VIEWER_EMAILS` in Secrets Manager
- [ ] `apply-backend-env.sh --apply` or `pm2 restart backend` on API host
- [ ] Send Grant email with expiry date
- [ ] Calendar reminder to revoke on expiry date

### DevOps checklist (revoke)

- [ ] Remove username/email from viewer lists
- [ ] Restart backend
- [ ] Send Revoke email
- [ ] Confirm user cannot open `/admin/logs`

---

## Status

- Production is live and synced on GitHub
- Devs: pull **`develop`** and branch from it for new work
- Log access: **email request + admin approval** (templates above); not public
