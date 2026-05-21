# Security scanning

This repo runs automated security checks on every PR and push to `develop`. Optional commercial scanners (Veracode, Snyk) can be added when your org provides API credentials.

## What runs automatically (GitHub Actions)

| Tool | What it finds | Workflow job |
|------|----------------|--------------|
| **npm audit** | Vulnerable npm packages (frontend) | `lint-and-scan` |
| **pip-audit** | Vulnerable Python packages (core deps patched; ML CVEs without PyPI fix are documented ignores) | `lint-and-scan` |
| **Bandit** | Common Python security issues in source | `lint-and-scan` |
| **CodeQL** | SQL injection, XSS, auth bugs (JS + Python) | `codeql` |
| **Trivy** | CVEs in dependencies and misconfigurations | `trivy` |
| **Semgrep** | OWASP-style patterns (SAST) | `semgrep` |
| **Gitleaks** | Secrets committed to git | `secret-scan` |
| **Login bundle guard** | Broken login after bad Vite chunk splits | `lint-and-scan` |
| **Playwright** | `/login` and `/forgot-password` smoke tests | `lint-and-scan` |
| **Dependabot** | Weekly PRs for outdated npm/pip/actions | (bot) |

## Veracode (optional — requires license)

Veracode is **not** enabled by default. To use it:

1. Obtain **API ID** and **API key** from your Veracode account.
2. Add GitHub repository secrets:
   - `VERACODE_API_ID`
   - `VERACODE_API_KEY`
3. Run **Actions → Veracode Scan (Manual) → Run workflow**.

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
