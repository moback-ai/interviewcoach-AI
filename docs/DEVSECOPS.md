# Production deploy — DevSecOps only

**Only these two people deploy to production:**

| DevSecOps | GitHub |
|-----------|--------|
| Govardhan | `@govardhanreddy66` |
| Kishore | `@KFKishore23` |

Repository: **`moback-ai/devsecops-platform`** (private)

---

## Developers — you deploy via PR, not Actions

1. Open a **PR** to `develop` (not a direct push for releases)
2. Pass **Security** CI
3. Get review and **merge**
4. **Ask Govardhan or Kishore to deploy** (comment on the PR or ping them)

You **cannot**:

- Run **Deploy · Production** (removed from this repo)
- Access `devsecops-platform`, SSH keys, or production secrets
- Trigger production deploy from GitHub Actions on this repo

---

## DevSecOps

Deploy: `devsecops-platform` → **InterviewCoach · Deploy Production**  
Access rules: `devsecops-platform/docs/TEAM_ACCESS.md`
