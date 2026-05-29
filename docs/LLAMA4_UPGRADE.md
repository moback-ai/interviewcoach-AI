# Llama 4 upgrade (not enabled on current production)

## Current production

| Setting | Value |
|---------|--------|
| AI instance | `c6i.2xlarge` (8 vCPU, **16 GB RAM**, no GPU) |
| Ollama model | `llama3.2:3b` (~2 GB quantized) |
| Interview concurrency | ~10–15 (`INTERVIEW_MAX_CONCURRENT=12`) |

## Why Llama 4 is not a drop-in upgrade

Official Ollama tags ([library/llama4](https://ollama.com/library/llama4)):

| Tag | Download size | Notes |
|-----|---------------|--------|
| `llama4` / `llama4:scout` | **~67 GB** | Scout — 17B active MoE |
| `llama4:maverick` | **~245 GB** | Maverick — not viable on a single box |

On **CPU-only** hosts with 16 GB RAM, Scout will not run reliably (OOM, very slow replies, concurrency near **1**).

## Recommended path to Llama 4

1. **Resize or replace the AI host** — e.g. `r6i.4xlarge` (128 GB RAM) minimum for Scout on CPU, or a **GPU** instance (`g5.2xlarge`+) for acceptable latency.
2. **Pull the model on the AI host:**
   ```bash
   ollama pull llama4:scout
   ```
3. **Update AWS Secrets Manager** (`interviewcoach/prod/app`):
   ```json
   "OLLAMA_MODEL": "llama4:scout"
   ```
4. **Lower concurrency** — start with `INTERVIEW_MAX_CONCURRENT=2` and tune.
5. **Restart API** (`pm2 restart backend`) and verify `/api/health` → `ollama.model_available: true`.

FFmpeg 8.1.1 is independent of the LLM upgrade; use `scripts/install-ffmpeg-8.sh` on the API host.
