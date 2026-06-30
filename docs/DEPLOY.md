# Deploy (application repo)

Production: **https://www.ugaanlabs.ai**

**Developers do not deploy or merge PRs.** DevSecOps only — see [DEVSECOPS.md](DEVSECOPS.md).

---

## Developers

1. Open a **PR** into `develop`
2. Pass **Security** CI
3. **DevSecOps approves and merges** (ganesh/neeraj do not merge)
4. Ask DevSecOps for **build + deploy** if needed

---

## DevSecOps — build once, deploy without build

### 1. Build image (when code changed)

`devsecops-platform` → **InterviewCoach · Build Docker Images**

- `app_git_ref`: merge SHA or `develop`
- `image_tag`: e.g. `prod-20260701-abc1234`

### 2. Deploy rollout only (no Docker build)

`devsecops-platform` → **InterviewCoach · Deploy Production**

- `app_git_ref`: same ref as build
- `image_tag`: **exact tag from step 1** (must exist in ECR)

---

## ASG hours (IST)

| Window | API EC2 |
|--------|---------|
| 10:00–19:00 | ≥ 1 node (up to 4 if CPU > 70%) |
| After 19:00 | 0 nodes |

---

## Branches

| Branch | Use |
|--------|-----|
| `develop/<feature>` | Feature → PR to `develop` |
| `develop` | Integration |
| `main` | Mirror of prod — DevSecOps merges from `develop` |
