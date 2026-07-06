# Security scanning

Three free scanners run on every PR to `release/**`:

| Scanner | What it checks |
|---------|----------------|
| **Gitleaks** | Secrets in git history |
| **Trivy** | Dependency and filesystem CVEs (CRITICAL/HIGH) |
| **Semgrep** | SAST (Python / JavaScript patterns) |

Workflow: `.github/workflows/code-quality-security.yml`

## Local

```bash
bash scripts/security-scan-all.sh
```
