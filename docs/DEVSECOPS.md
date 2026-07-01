# Production deploy — who does what

**Only DevSecOps deploys to production** (Govardhan or Kishore) from **`moback-ai/devsecops-platform`**.

Full ops guide (diagrams, playbooks): `apps/interviewcoach/docs/DEVSECOPS_GUIDE.md` in the DevSecOps repo — **private**; ask DevSecOps for access.

---

## Developers (ganesh, neeraj)

1. Open a **PR** to `develop` → pass **Security** CI
2. **DevSecOps approves and merges** (you do not merge)
3. Ask DevSecOps for **build + deploy** when you need a release

### AWS access (CloudWatch only)

| Allowed | Blocked |
|---------|---------|
| CloudWatch Logs on `/interviewcoach/prod/api` | Secrets Manager, EC2, deploy, SSH |

See [DEV_ACCESS.md](DEV_ACCESS.md).

---

## DevSecOps

See **`devsecops-platform`** → `apps/interviewcoach/docs/DEVSECOPS.md`

Do **not** run `infra/prod/scripts/*` from this repo — scripts call `require-devsecops.sh` and exit here.

---

## Service hours (IST)

| Time | API |
|------|-----|
| **10:00 – 19:00** | Live |
| **19:00 – 10:00** | Off — maintenance banner on frontend |
