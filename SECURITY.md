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

## Automated checks (every PR / `develop` push)

- **CodeQL** — JavaScript + Python SAST
- **Semgrep** — OWASP-style rules
- **Trivy** — CRITICAL/HIGH CVEs in repo files
- **Gitleaks** — secrets in git history
- **npm audit** (high+) and **pip-audit** (patched core deps)
- **Bandit** — Python high-severity issues
- **Playwright** — `/login` and `/forgot-password` smoke tests
- **Login bundle guard** — prevents broken login deploys

## Optional commercial scanning

**Veracode:** add `VERACODE_API_ID` and `VERACODE_API_KEY` secrets, then run **Veracode Scan (Manual)**.

See [docs/SECURITY_SCANNING.md](docs/SECURITY_SCANNING.md) for local commands and ML dependency risk notes.
