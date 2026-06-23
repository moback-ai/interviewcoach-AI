# Security scanning

Production deploys run **Veracode only** — no other CI security scanners.

## Veracode on deploy

Every **Deploy · Production** run (after admin approves the `production` environment):

1. Packages `frontend`, `backend`, and `scripts`
2. Uploads to Veracode
3. Starts a policy scan in sandbox `develop`
4. Continues to build and deploy servers

### Setup (one time)

1. Veracode account with API credentials
2. GitHub → **Settings → Secrets → Actions**:
   - `VERACODE_API_ID`
   - `VERACODE_API_KEY`

Deploy **fails** if these secrets are missing.

### Results

- Upload status: GitHub Actions log for **Veracode scan**
- Full report: [Veracode portal](https://analysiscenter.veracode.com/) (often 15–60 min after upload)

## What was removed

No automatic PR scans (Gitleaks, CodeQL, Trivy, Semgrep, npm/pip audit, etc.).  
No separate **Security** workflow.

## Reporting vulnerabilities

See [SECURITY.md](../SECURITY.md).
