# AWS decommission — Plan B → PROD

**Prod only.** There is no staging or dev environment on AWS. This list is what to **remove or stop** after PROD is live and stable (7+ days).

Do **not** run until DevSecOps confirms prod is healthy.

---

## 1. EC2 instances to terminate

| Resource | Role today | Action |
|----------|------------|--------|
| **AI EC2** | Ollama + Whisper sidecar | **Terminate** (after 7 days stable) |
| **Frontend EC2** | nginx + SPA | **Terminate** when CloudFront + S3 serves static |
| **Old API EC2** | Plan B API only | **Terminate** when new API ASG/ECS is stable |

Keep until cutover complete: at least one API path serving traffic.

---

## 2. Docker / compose (stop using)

| File | Action |
|------|--------|
| `docker/compose.plan-b.yml` | **Archive** — replaced by `docker/compose.prod.yml` |
| `docker/compose.transcribe-host.yml` | **Remove** from deploy |
| `docker/compose.web-host.yml` / `api-host` splits | **Replace** with ALB + ASG or single prod compose |
| Whisper **transcribe sidecar** on port 5001 | **Stop container permanently** |

---

## 3. Secrets Manager — keys to DELETE

Remove from `interviewcoach/prod/app` JSON after prod deploy:

```
OLLAMA_HOST
OLLAMA_HEALTH_URL
OLLAMA_MODEL
OLLAMA_NUM_PREDICT
OLLAMA_DIAGNOSTICS_CACHE_SECONDS
QUESTION_GEN_OLLAMA_TIMEOUT_SECONDS
JD_PARSE_OLLAMA_TIMEOUT_SECONDS
TRANSCRIBE_SERVICE_URL
TRANSCRIBE_INTERNAL_TOKEN
ENABLE_AI_WARMUP
WHISPER_MODEL
WHISPER_BEAM_SIZE
```

---

## 4. Secrets Manager — keys to ADD

Use `backend/secrets.prod.example.json` as the template. Required new keys:

```
LLM_PROVIDER=bedrock
BEDROCK_CHAT_MODEL=apac.amazon.nova-lite-v1:0
STT_PRIMARY=openrouter
STT_FALLBACK=amazon
OPENROUTER_API_KEY
STT_S3_BUCKET
S3_BUCKET
STORAGE_BACKEND=s3
REDIS_URL
```

---

## 5. IAM — permissions to REMOVE

From API EC2/ECS task role (if only used for self-hosted AI):

- SSM/SSH to AI host (if any custom policy)
- Security group rules: API → AI EC2 on 11434, 5001

---

## 6. IAM — permissions to ADD

```
bedrock:InvokeModel
bedrock:InvokeModelWithResponseStream
bedrock:Converse
bedrock:ConverseStream
transcribe:StartTranscriptionJob
transcribe:GetTranscriptionJob
transcribe:DeleteTranscriptionJob
s3:PutObject / GetObject / DeleteObject (user files + stt-temp/)
```

Inference profile ARNs for `apac.amazon.nova-*` in ap-south-1.

---

## 7. Security groups — rules to REMOVE

| Rule | Why |
|------|-----|
| API → AI EC2 **11434** (Ollama) | No Ollama |
| API → AI EC2 **5001** (Whisper) | No sidecar |
| Public ingress to AI EC2 | AI host gone |

---

## 8. DNS / edge — switch

| Before (Plan B) | After (PROD) |
|-----------------|----------------|
| Frontend EC2 public IP / nginx | **CloudFront** → S3 static |
| API via nginx proxy on FE host | **CloudFront** `/api/*` → **ALB** → API |
| `/socket.io/` via nginx | **ALB** WebSocket stickiness |

---

## 9. Storage migration

1. `aws s3 sync /apps/storage/ s3://ic-user-files-prod/` (final sync at cutover)
2. Set `STORAGE_BACKEND=s3` in Secrets Manager
3. After 14 days: remove `/apps/storage` dependency on API disk (optional EBS shrink)

---

## 10. ECR / images

- Keep `interviewcoach-api` and `interviewcoach-web` repos
- **Web image optional** if frontend is S3-only (static upload from CI, not EC2)

---

## 11. Monitoring — remove old alarms

- AI EC2 CPU / Ollama health checks
- Whisper sidecar health on 5001

Add:

- Bedrock throttling / 5xx
- OpenRouter STT failure rate
- API p95 latency, ALB 5xx

---

## 12. Cutover order (prod only)

```
Day 0  Deploy prod API + update Secrets Manager (parallel to old stack if needed)
Day 0  CloudFront → new ALB; verify ugaanlabs.ai
Day 1  Monitor interviews, Piper, head tracking, payments
Day 7  Stop AI EC2 + transcribe sidecar
Day 7  Stop old API/FE EC2 if replaced by ASG
Day 14 Delete AI EC2, old EBS snapshots, unused SG rules
Day 14 Remove OLLAMA_* / TRANSCRIBE_* from secrets (see §3)
```

---

## 13. Rollback (prod emergency)

1. Point CloudFront origin back to Plan B frontend/API
2. Start AI EC2 + restore `OLLAMA_*` and `TRANSCRIBE_SERVICE_URL` in secrets
3. Set `LLM_PROVIDER=ollama` temporarily

Prod code stays in the app; rollback is **config + infra**, not necessarily git revert.

---

## 14. Verification before decommission

- [ ] 7 consecutive days: no P1 incidents
- [ ] `/api/health` → `llm.provider=bedrock`, STT chain includes openrouter
- [ ] No traffic to AI EC2 (check VPC flow logs / SG hit count)
- [ ] Bedrock + OpenRouter bills within budget alerts
