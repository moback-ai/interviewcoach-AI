# Security scanning

Automated security checks run on **PRs** (quick) and **weekly / manual** (full). Optional commercial scanners (Veracode, Snyk) can be added when your org provides API credentials.

## What runs automatically (GitHub Actions)

### On every PR (quick check)

| Tool | What it finds | Workflow job |
|------|----------------|--------------|
| **ESLint** | Frontend lint on changed files | `pr-quick` |
| **pytest** | Backend unit tests (if backend changed) | `pr-quick` |
| **Gitleaks** | Secrets committed to git | `pr-quick` |

### Weekly (Mon 06:00 UTC) or manual dispatch (full scan)

| Tool | What it finds | Workflow job |
|------|----------------|--------------|
| **npm audit** | Vulnerable npm packages (frontend) | `full-scan` |
| **pip-audit** | Vulnerable Python packages | `full-scan` |
| **Bandit** | Common Python security issues in source | `full-scan` |
| **CodeQL** | SQL injection, XSS, auth bugs (JS + Python) | `codeql` |
| **Trivy** | CVEs in dependencies and misconfigurations | `full-scan` |
| **OSV-Scanner** | Cross-ecosystem dependency CVEs (npm + pip) | `osv-scanner` |
| **Semgrep** | OWASP-style patterns (SAST) | `full-scan` |
| **Login bundle guard** | Broken login after bad Vite chunk splits | `full-scan` |
| **Playwright** | `/login` and `/forgot-password` smoke tests | `full-scan` |
| **Dependabot** | Weekly PRs for outdated npm/pip/actions | (bot) |

**No** Security workflow runs on push to `develop` — merge goes straight to **Deploy · Production**.

Manual full scan: **Actions → Security → Run workflow**.

## Veracode (optional — requires license)

Veracode is **not** enabled by default. To use it:

1. Obtain **API ID** and **API key** from your Veracode account.
2. Add GitHub repository secrets:
   - `VERACODE_API_ID`
   - `VERACODE_API_KEY`
3. Run **Actions → Security · Veracode (manual) → Run workflow**.

Results appear in the Veracode portal (policy scans, SCA, etc.). Use this for compliance (SOC2, customer security questionnaires) alongside the free GitHub checks above.

## Snyk (optional alternative)

If you prefer Snyk over pip-audit/npm audit:

1. Create a Snyk org and import the GitHub repo.
2. Add secret `SNYK_TOKEN` and uncomment the Snyk job in `.github/workflows/code-quality-security.yml` (see comment block in that file).

## Local scans

```bash
# Frontend
cd frontend && npm ci --legacy-peer-deps && npm audit --audit-level=high && npm run lint
npm run build && bash ../scripts/verify-frontend-login-bundle.sh dist

# Backend
pip install -r backend/requirements.txt bandit pip-audit
pip-audit
bandit -c .github/bandit.yml -r backend

# Secrets (install gitleaks CLI)
gitleaks detect --source . --config .gitleaks.toml
```

## Performance vs security

Production frontend builds drop `console` and `debugger` to reduce noise and minor bundle cost. Do not re-enable `manualChunks` for React or shared UI libraries without running the login bundle guard script.
