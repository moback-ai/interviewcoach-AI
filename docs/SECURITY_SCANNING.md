# Security scanning

## Quick summary

| When | What runs |
|------|-----------|
| **Every PR** | ESLint (if frontend changed), pytest (if backend changed), Gitleaks |
| **Weekly Mon or manual** | CodeQL, Trivy, Semgrep, Bandit, npm/pip audit, Playwright smoke |
| **Manual — one Veracode scan** | **Veracode Scan** workflow (requires license + API secrets) |

---

## Veracode (one scan — compliance / customer questionnaires)

Veracode is **not free**. You need a Veracode account and scan credits.

### Setup (one time)

1. Get **API ID** and **API key** from [Veracode](https://analysiscenter.veracode.com/) → API Credentials.
2. In GitHub: **Settings → Secrets and variables → Actions** → add:
   - `VERACODE_API_ID`
   - `VERACODE_API_KEY`

### Run the scan

1. **Actions → Veracode Scan → Run workflow**
2. Leave sandbox as `develop` (or change if your org uses another sandbox name)
3. Wait for the workflow to upload the zip (a few minutes)
4. Open the **Veracode portal** for full results (policy scan often takes **15–60 minutes**)

One workflow, one upload, one policy scan per run. Re-run manually before releases or when a customer asks for a security report.

---

## Free GitHub checks (automatic)

### On every PR

| Tool | Purpose |
|------|---------|
| ESLint | Frontend lint on changed files |
| pytest | Backend unit tests |
| Gitleaks | Secrets in git |

### Weekly (Mon 06:00 UTC) or **Actions → Security → Run workflow**

| Tool | Purpose |
|------|---------|
| CodeQL | SAST (JS + Python) |
| Semgrep | OWASP-style rules |
| Trivy | HIGH/CRITICAL CVEs |
| Bandit | Python security patterns |
| npm audit / pip-audit | Dependency CVEs |
| Playwright | Login page smoke tests |

No Security workflow on push to `develop` — merge goes to **Deploy · Production** only.

---

## Local scans

```bash
# Frontend
cd frontend && npm ci --legacy-peer-deps && npm audit --audit-level=high && npm run lint
npm run build && bash ../scripts/verify-frontend-login-bundle.sh dist

# Backend
pip install -r backend/requirements.txt bandit pip-audit
pip-audit
bandit -c .github/bandit.yml -r backend

# Secrets
gitleaks detect --source . --config .gitleaks.toml
```

---

## Optional: Snyk

If you prefer Snyk over npm/pip audit, add `SNYK_TOKEN` and import the repo in Snyk. Not required if you use Veracode + the free checks above.
