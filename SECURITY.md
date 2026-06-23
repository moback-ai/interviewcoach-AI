# Security Policy

## Supported versions

| Branch    | Supported |
|-----------|-----------|
| `develop` | Yes       |
| `main`    | Yes       |

## Reporting a vulnerability

Email security concerns to your team admin (do not open public issues for exploitable bugs).

Include:

- Steps to reproduce
- Impact (data exposure, auth bypass, RCE, etc.)
- Affected URLs or API routes

We aim to acknowledge reports within **3 business days**.

## Automated checks

| When | Checks |
|------|--------|
| **Every PR** | Gitleaks, ESLint (frontend), pytest (backend) |
| **Weekly / manual** | CodeQL, Semgrep, Trivy, Bandit, npm/pip audit, Playwright |

## Veracode (one manual scan)

Add `VERACODE_API_ID` and `VERACODE_API_KEY` secrets, then run **Actions → Veracode Scan → Run workflow**.

See [docs/SECURITY_SCANNING.md](docs/SECURITY_SCANNING.md).
