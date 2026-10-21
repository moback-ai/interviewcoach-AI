# GPT-5.6 Terra on Amazon Bedrock (ap-south-1)

The API calls LLMs only through `backend/common/llm/bedrock.py` (Bedrock Runtime **Converse** /
**ConverseStream** via boto3). GPT-5.6 Terra supports both on `bedrock-runtime`, so no OpenAI SDK,
OpenAI API key, or separate integration is used. Switching models is a configuration change.

## 1. Verified identifiers (AWS model card, October 2026)

| Item | Value |
|---|---|
| Catalog / base model ID | `openai.gpt-5.6-terra` — **not callable directly from ap-south-1** |
| India geo profile | `in.openai.gpt-5.6-terra` → routes to ap-south-1 and ap-south-2 only |
| Global profile | `global.openai.gpt-5.6-terra` → any commercial Region, ~9% cheaper |
| APIs on bedrock-runtime | Converse ✔, streaming ✔, Responses/Chat Completions ✔, InvokeModel ✘ |
| Context / max output | 1,050,000 / 128,000 tokens |
| Marketplace product | `prod-oxu3iqwrwktjm` |

This app defaults to the **India geo profile** so candidate resumes and answers are processed only
in India. Use the global profile only if that is acceptable. Re-check before go-live:

```bash
aws bedrock get-inference-profile --region ap-south-1 \
  --inference-profile-identifier in.openai.gpt-5.6-terra
```

## 2. Reasoning effort (read this before go-live)

GPT-5.6 is a reasoning model: hidden reasoning tokens are spent from each call's `maxTokens` before
any answer text. Many calls in this app cap output at 64–384 tokens (classifiers, short interviewer
replies), so the model default effort can return **empty or cut-off replies**.

`LLM_REASONING_EFFORT` (sent as `additionalModelRequestFields: {"reasoning": {"effort": ...}}`):

| Value | Use |
|---|---|
| `none` | **Start here.** Behaves like the non-reasoning model the prompts were built for; lowest latency and cost. |
| `low` | Try next for better answer evaluation; watch logs for `hit maxTokens` warnings. |
| `medium`+ | Not recommended for live interview turns (latency, token budget, 120 s CloudFront limit). |

Reasoning text is never shown to candidates or spoken by TTS: only answer text is returned/streamed.
If replies come back empty, the log line `Bedrock response hit maxTokens=... answer_chars=0` names
the cause.

## 3. AWS account setup (needs console access)

1. **Model access.** Bedrock console (ap-south-1) → Model catalog → GPT-5.6 Terra. Accept the
   OpenAI EULA / AWS Marketplace offer. The identity doing the first call or subscription needs
   `aws-marketplace:Subscribe` and `aws-marketplace:ViewSubscriptions`.
2. **IAM for the API role** (EC2 instance role in prod, your SSO role locally). Replace `ACCOUNT_ID`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeGpt56Terra",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": [
        "arn:aws:bedrock:ap-south-1:ACCOUNT_ID:inference-profile/in.openai.gpt-5.6-terra",
        "arn:aws:bedrock:ap-south-1:ACCOUNT_ID:inference-profile/global.openai.gpt-5.6-terra",
        "arn:aws:bedrock:ap-south-1::foundation-model/openai.gpt-5.6-terra",
        "arn:aws:bedrock:ap-south-2::foundation-model/openai.gpt-5.6-terra",
        "arn:aws:bedrock:*::foundation-model/openai.gpt-5.6-terra",
        "arn:aws:bedrock:ap-south-1:ACCOUNT_ID:project/default"
      ]
    }
  ]
}
```

   - The foundation-model ARN must cover every destination Region of the profile (ap-south-1 and
     ap-south-2 for `in.`). The `*` Region line is needed only for the global profile; remove it
     if you use `in.` only.
   - The `project/default` ARN is stated as required for GPT-5.6 on `bedrock-runtime` in AWS's
     model card. If an `AccessDenied` names `project/default`, this line is missing.
3. **SCPs** must allow ap-south-2 (for `in.`) or global routing (for `global.`).
4. **Quota.** Bedrock counts each output token as 10 tokens against tokens-per-minute and reserves
   the full `maxTokens` up front. Request a TPM increase for the profile sized for peak concurrent
   interviews, and keep `LLM_MAX_TOKENS` modest (it is the cap used when a call passes none).

## 4. Configuration

| Key | Default | Purpose |
|---|---|---|
| `BEDROCK_REGION` | `AWS_REGION`, else `ap-south-1` | Source Region |
| `BEDROCK_CHAT_MODEL` | **none — required** | e.g. `in.openai.gpt-5.6-terra`. No silent fallback. |
| `LLM_REASONING_EFFORT` | unset (model default) | `none` recommended to start (§2). Ignored for non-OpenAI models. |
| `LLM_SEND_TEMPERATURE` | `auto` | Drops temperature automatically if the model rejects it |
| `LLM_MAX_TOKENS` | `384` (clamped 64–8192) | Output cap when a call passes none |
| `LLM_MAX_INPUT_CHARS` | `400000` | Rejects oversized prompts before calling AWS |
| `BEDROCK_MAX_ATTEMPTS` | `3` | botocore attempts, exponential backoff on throttling/5xx |
| `BEDROCK_CONNECT_TIMEOUT_SECONDS` / `BEDROCK_READ_TIMEOUT_SECONDS` | `5` / `120` | Keep read timeout under ~110 s behind CloudFront |
| `BEDROCK_DIAGNOSTICS_CACHE_SECONDS` | `120` | Health probes reuse one live check |
| `READINESS_STRICT_AI` | `false` | `true` makes LLM/STT outages fail `/api/health/ready` |

Credentials come only from the AWS credential chain. Never put AWS keys or Bedrock API keys in
`.env` or Secrets Manager for this app.

## 5. Run locally

```bash
aws sso login --profile <your-profile>
cd backend
cp .env.example .env            # DB values; BEDROCK_CHAT_MODEL / LLM_REASONING_EFFORT are preset
export AWS_PROFILE=<your-profile>

python scripts/bedrock_smoke_test.py          # credentials, profile, Converse, ConverseStream
python scripts/bedrock_smoke_test.py --coach  # plus one sample answer evaluation

bash ../scripts/dev-local.sh                  # then the frontend per README
```

Expected output (abridged):

```
▶ Configuration
  ✔ region=ap-south-1
  ✔ model=in.openai.gpt-5.6-terra
  ✔ reasoning_effort=none
▶ AWS credentials (standard credential chain)
  ✔ authenticated as a assumed-role in account ****1234
▶ Inference profile lookup
  ✔ routes to: ap-south-1, ap-south-2
▶ Converse (non-streaming)
  ✔ reply='OK' stop=end_turn latency=...ms usage={...}
▶ ConverseStream (streaming)
  ✔ 1 chunk(s): 'OK'
All Bedrock checks passed.
```

## 6. Health / diagnostic check

`GET /api/health` → `services.llm` (no credentials, ARNs or account IDs are returned):

```json
{ "provider": "bedrock", "ready": true, "reachable": true,
  "model": "in.openai.gpt-5.6-terra", "model_available": true, "error": "" }
```

On failure `ready` is `false` and `error` is redacted, e.g.
`Bedrock AccessDenied (model=in.openai.gpt-5.6-terra): User: arn:aws:<redacted> is not authorized ... Hint: ...`.
LLM/STT outages are reported under `readiness.degraded` and do not fail `/api/health/ready`, so the
ASG does not replace healthy instances during a Bedrock blip (`READINESS_STRICT_AI=true` restores
the old behaviour).

## 7. Troubleshooting

| Symptom (code in logs / health) | Likely cause | Fix |
|---|---|---|
| `ConfigError: BEDROCK_CHAT_MODEL is not set` | Key missing | Set it; there is intentionally no default. |
| `ValidationError ... on-demand throughput isn't supported` | Bare `openai.gpt-5.6-terra` used | Use `in.openai.gpt-5.6-terra` or `global.openai.gpt-5.6-terra`. |
| `ModelNotFound` | Typo, or wrong `BEDROCK_REGION` | Region must be ap-south-1 (or another source Region of the profile). |
| `AccessDenied ... inference-profile` / `foundation-model` | IAM missing a resource | Apply §3; include ap-south-2 for `in.`. |
| `AccessDenied ... project/default` | Project ARN missing from IAM | Add `arn:aws:bedrock:ap-south-1:ACCOUNT_ID:project/default`. |
| `AccessDenied` mentioning subscription / Marketplace | Model access not enabled | Complete §3 step 1. |
| `AccessDenied ... explicit deny` | SCP blocks ap-south-2 or global routing | Org admin change, or switch profile type. |
| `ConfigError: LLM_REASONING_EFFORT=...` | Unsupported value | Use none, low, medium, high, xhigh or max. |
| `ValidationError` mentioning `reasoning` | Effort parameter rejected | Unset `LLM_REASONING_EFFORT` and report it; the request shape may have changed. |
| Empty replies, log `hit maxTokens ... answer_chars=0` | Reasoning used the output budget | Lower `LLM_REASONING_EFFORT` (to `none`). |
| `Throttled` | TPM/RPM quota (output tokens count 10×) | Request an increase; lower `LLM_MAX_TOKENS`. |
| `Timeout` / 504 through the site | Slow generation vs 120 s CloudFront limit | Lower effort; keep read timeout ≤ 110 s. |
| Credentials errors on laptop | SSO session expired | `aws sso login --profile ...` |

Config, permission and model-not-found errors are fatal: the app's retry loops stop immediately
instead of re-sending requests that cannot succeed.
