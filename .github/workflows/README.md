# Workflows

| Workflow | When | What you see |
|----------|------|----------------|
| **Security** | Every PR | One job: **Security scan** |
| **Deploy · Production** | Merge → `develop` | Approve production → **Security scan** → deploy |

All free scanners run inside one step (`scripts/security-scan-all.sh`).

Details: [docs/DEPLOY.md](../../docs/DEPLOY.md) · [docs/SECURITY_SCANNING.md](../../docs/SECURITY_SCANNING.md)
