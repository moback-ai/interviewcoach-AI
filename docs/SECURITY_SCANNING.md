# Security scanning

One **Security scan** step runs every free checker in the background (`scripts/security-scan-all.sh`).  
Detailed output stays in the job log; the UI shows a single pass/fail.

## When it runs

| When | Profile | Includes |
|------|---------|----------|
| **Every PR** | `quick` | Gitleaks, ESLint, build, pytest, Trivy, Semgrep |
| **Before deploy** | `quick` | Same (PR already scanned; no duplicate Playwright) |

## Scanners (all free)

Gitleaks · ESLint · build · pytest · Trivy · Semgrep

## Local

```bash
SECURITY_SCAN_PROFILE=quick bash scripts/security-scan-all.sh
```

## Veracode

Paid only — not used. Optional later if your org buys a license.
