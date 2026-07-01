# Architecture — InterviewCoach (application)

Production: **https://www.ugaanlabs.ai**

**AWS topology, deploy diagrams, and infra runbooks** are in the DevSecOps repo:  
`moback-ai/devsecops-platform` → `apps/interviewcoach/docs/ARCHITECTURE.md` (private)

---

## Application stack

| Layer | Technology | Prod notes |
|-------|------------|------------|
| Frontend | Vite + React 19 | `VITE_API_BASE_URL=https://www.ugaanlabs.ai/api` |
| API | Flask + Gunicorn + Socket.IO | `docker/api/Dockerfile.prod` |
| Database | PostgreSQL (RDS) | Via RDS Proxy in prod |
| LLM | Amazon Bedrock | Nova Lite / Pro — `backend/common/llm/bedrock.py` |
| STT | OpenRouter → Amazon | `backend/common/speech/` |
| TTS | Piper (in-container) | Server-side interview voice |
| Storage | S3 | `backend/common/storage_s3.py` |
| Cache | Redis | Rate limits, interview slots |
| Config | AWS Secrets Manager (prod) | See [SECRETS_ONLY.md](SECRETS_ONLY.md) |
| Auth | JWT | 10-minute idle timeout |

Local dev uses Ollama + `backend/.env` (`RUNTIME_CONFIG_ALLOW_ENV=true`).

---

## Repository layout

```
backend/          Flask API, common/ (llm, speech, storage, redis)
frontend/         Vite + React SPA
database/         Schema and SQL migrations
docker/           Dockerfile.prod, compose files
infra/prod/       Reference copy of prod scripts (sync to DevSecOps — do not run here)
docs/             Developer docs; ops docs in devsecops-platform
scripts/          Local dev and security scan helpers
```

---

## Release flow (summary)

1. Developer opens PR → `develop`  
2. **Security** CI must pass (Gitleaks, Trivy, Semgrep)  
3. **DevSecOps** merges  
4. **DevSecOps** builds and deploys from `devsecops-platform`  

Details: [DEVSECOPS.md](DEVSECOPS.md) · [SECURITY_SCANNING.md](SECURITY_SCANNING.md)

---

## Health check

```bash
curl -fsS https://www.ugaanlabs.ai/api/health | jq .
```

Expected on prod: `llm.provider=bedrock`, `config.source=secrets_manager`.
