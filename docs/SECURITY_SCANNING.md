# Security scanning

## Gates (before merge and before deploy)

| Gate | When | Job | Blocks |
|------|------|-----|--------|
| **PR security gate** | Every PR to `develop` / `main` | `pr-security-gate` | **Merge** if red |
| **Deploy security gate** | Every Deploy · Production run | `security_gate` | **Deploy** if red |

Both use [.github/actions/security-gate](../.github/actions/security-gate/action.yml):

| Check | Frontend changed | Backend changed | Always |
|-------|------------------|-----------------|--------|
| Gitleaks (secrets) | | | yes |
| Merge conflict vs `develop` | | | PR only |
| ESLint + npm audit + build + login bundle | yes | | |
| pytest + pip-audit + Bandit | | yes | |

At deploy time, scans run for boxes in the deploy plan (`frontend` / `backend` / `all`).

---

## Weekly / manual full scan

**Actions → Security → Run workflow** (or Mondays 06:00 UTC):

| Tool | Purpose |
|------|---------|
| CodeQL | SAST (JS + Python) |
| Semgrep | OWASP-style rules |
| Trivy | HIGH/CRITICAL CVEs |
| Playwright | Login smoke tests |
| npm audit / pip-audit / Bandit | Same as PR gate, full repo |

---

## Veracode (optional — manual)

1. Add secrets `VERACODE_API_ID`, `VERACODE_API_KEY`
2. **Actions → Veracode Scan → Run workflow**

---

## Local scans

```bash
cd frontend && npm ci --legacy-peer-deps && npm audit --audit-level=high && npm run lint
npm run build && bash ../scripts/verify-frontend-login-bundle.sh dist

pip install -r backend/requirements.txt bandit pip-audit pytest
pip-audit && bandit -c .github/bandit.yml -r backend
python -m pytest backend/tests/ -q

gitleaks detect --source . --config .gitleaks.toml
```
