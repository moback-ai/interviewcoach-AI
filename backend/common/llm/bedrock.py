"""Amazon Bedrock LLM provider (Converse / ConverseStream).

Works with any Converse-capable model, e.g. OpenAI GPT-5.6 Terra through the
in./global. inference profile. The model is never assumed: BEDROCK_CHAT_MODEL
must be set, and there is no fallback to another model.

Configuration (Secrets Manager JSON in prod, backend/.env on laptops):
  BEDROCK_REGION                     default: AWS_REGION, else ap-south-1
  BEDROCK_CHAT_MODEL                 required — model ID or inference profile ID/ARN
  LLM_MAX_TOKENS                     default output cap when a call passes none
  LLM_TEMPERATURE                    default temperature when a call passes none
  LLM_SEND_TEMPERATURE               auto (default) | true | false
  LLM_REASONING_EFFORT               OpenAI GPT-5.x on Bedrock: none|low|medium|high|xhigh|max
                                     (unset = model default; reasoning tokens use maxTokens)
  LLM_MAX_INPUT_CHARS                reject oversized prompts before calling AWS
  BEDROCK_MAX_ATTEMPTS               botocore attempts incl. first (default 3)
  BEDROCK_CONNECT_TIMEOUT_SECONDS    default 5
  BEDROCK_READ_TIMEOUT_SECONDS       default 120
  BEDROCK_DIAGNOSTICS_CACHE_SECONDS  default 120 (health checks reuse the result)

Credentials come only from the standard AWS chain (instance role, SSO, env,
profile). This module never reads or logs access keys.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Iterator

from common.runtime_config import optional_env

logger = logging.getLogger(__name__)

# Placeholder names callers pass meaning "use the configured default model".
_DEFAULT_MODEL_ALIASES = frozenset({"", "llama3", "llama3.2:3b"})


# ── Errors ────────────────────────────────────────────────────────────────
class BedrockError(RuntimeError):
    """Base class. Subclasses RuntimeError so existing `except` blocks still work."""

    code = "BedrockError"
    retryable = False

    def __init__(self, message: str, *, aws_code: str = "", request_id: str = "") -> None:
        super().__init__(message)
        self.aws_code = aws_code
        self.request_id = request_id


class BedrockConfigError(BedrockError):
    code = "ConfigError"


class BedrockAccessDeniedError(BedrockError):
    code = "AccessDenied"


class BedrockModelNotFoundError(BedrockError):
    code = "ModelNotFound"


class BedrockValidationError(BedrockError):
    code = "ValidationError"


class BedrockThrottledError(BedrockError):
    code = "Throttled"
    retryable = True


class BedrockTimeoutError(BedrockError):
    code = "Timeout"
    retryable = True


class BedrockUnavailableError(BedrockError):
    code = "ServiceUnavailable"
    retryable = True


_AWS_CODE_MAP: dict[str, type[BedrockError]] = {
    "AccessDeniedException": BedrockAccessDeniedError,
    "UnrecognizedClientException": BedrockAccessDeniedError,
    "ExpiredTokenException": BedrockAccessDeniedError,
    "ResourceNotFoundException": BedrockModelNotFoundError,
    "ValidationException": BedrockValidationError,
    "ThrottlingException": BedrockThrottledError,
    "ServiceQuotaExceededException": BedrockThrottledError,
    "TooManyRequestsException": BedrockThrottledError,
    "ModelTimeoutException": BedrockTimeoutError,
    "ModelNotReadyException": BedrockUnavailableError,
    "ServiceUnavailableException": BedrockUnavailableError,
    "InternalServerException": BedrockUnavailableError,
    "ModelErrorException": BedrockUnavailableError,
    "ModelStreamErrorException": BedrockUnavailableError,
}

# ConverseStream error events (camelCase keys inside the event stream).
_STREAM_ERROR_EVENTS: dict[str, str] = {
    "internalServerException": "InternalServerException",
    "modelStreamErrorException": "ModelStreamErrorException",
    "validationException": "ValidationException",
    "throttlingException": "ThrottlingException",
    "serviceUnavailableException": "ServiceUnavailableException",
}

_ARN_RE = re.compile(r"arn:aws[a-zA-Z-]*:[a-z0-9-]+:[a-z0-9-]*:\d{12}:[^\s,;\"']+")
_ACCOUNT_RE = re.compile(r"\b\d{12}\b")


def redact(text: str) -> str:
    """Strip ARNs and account IDs (AccessDenied messages embed the caller role)."""
    text = _ARN_RE.sub("arn:aws:<redacted>", text or "")
    return _ACCOUNT_RE.sub("<account>", text)


def is_fatal_llm_error(exc: BaseException) -> bool:
    """True when retrying cannot help (bad config, missing permission, unknown model)."""
    return isinstance(exc, (BedrockConfigError, BedrockAccessDeniedError, BedrockModelNotFoundError))


def _hint_for(cls: type[BedrockError], message: str) -> str:
    lower = message.lower()
    if "on-demand throughput" in lower or "inference profile" in lower:
        return (
            " Hint: this model cannot be invoked by its bare model ID in this Region; "
            "set BEDROCK_CHAT_MODEL to an inference profile ID (e.g. a geo or global profile)."
        )
    if cls is BedrockAccessDeniedError:
        return (
            " Hint: check bedrock:InvokeModel / InvokeModelWithResponseStream on the inference "
            "profile AND the underlying foundation model in every destination Region, that model "
            "access (AWS Marketplace subscription) is enabled, and for OpenAI models "
            "bedrock:InvokeModel on the account's default project ARN."
        )
    if cls is BedrockModelNotFoundError:
        return " Hint: BEDROCK_CHAT_MODEL may be misspelled or not offered in BEDROCK_REGION."
    return ""


def translate_error(exc: Exception, model_id: str = "") -> BedrockError:
    """Map botocore exceptions to typed BedrockError subclasses."""
    if isinstance(exc, BedrockError):
        return exc
    aws_code, request_id, message = "", "", str(exc)
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        err = response.get("Error") or {}
        aws_code = str(err.get("Code") or "")
        message = str(err.get("Message") or message)
        request_id = str((response.get("ResponseMetadata") or {}).get("RequestId") or "")

    cls: type[BedrockError] | None = _AWS_CODE_MAP.get(aws_code)
    if cls is None:
        name = type(exc).__name__
        if name in ("ReadTimeoutError", "ConnectTimeoutError"):
            cls = BedrockTimeoutError
        elif name in ("EndpointConnectionError", "ConnectionClosedError"):
            cls = BedrockUnavailableError
        elif name in ("NoCredentialsError", "PartialCredentialsError", "TokenRetrievalError",
                      "SSOTokenLoadError", "UnauthorizedSSOTokenError"):
            cls = BedrockAccessDeniedError
            aws_code = aws_code or name
        else:
            cls = BedrockError
    text = f"Bedrock {cls.code}"
    if model_id:
        text += f" (model={model_id})"
    text += f": {redact(message)}{_hint_for(cls, message)}"
    return cls(text, aws_code=aws_code, request_id=request_id)


# ── Config helpers ────────────────────────────────────────────────────────
def _boto3():
    import boto3

    return boto3


def _region() -> str:
    return optional_env("BEDROCK_REGION", optional_env("AWS_REGION", "ap-south-1")) or "ap-south-1"


def _int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(int(optional_env(name, str(default)) or default), hi))
    except (TypeError, ValueError):
        return default


def _max_tokens(override: int | None = None) -> int:
    if override is not None:
        try:
            return max(64, min(int(override), 8192))
        except (TypeError, ValueError):
            pass
    raw = optional_env("LLM_MAX_TOKENS", optional_env("OLLAMA_NUM_PREDICT", "384"))
    try:
        return max(64, min(int(raw or 384), 8192))
    except (TypeError, ValueError):
        return 384


def _temperature(override: float | None = None) -> float:
    if override is not None:
        try:
            return max(0.0, min(float(override), 1.0))
        except (TypeError, ValueError):
            pass
    raw = optional_env("LLM_TEMPERATURE", "0.6")
    try:
        return max(0.0, min(float(raw), 1.0))
    except (TypeError, ValueError):
        return 0.6


def _send_temperature_mode() -> str:
    mode = (optional_env("LLM_SEND_TEMPERATURE", "auto") or "auto").lower()
    return mode if mode in ("auto", "true", "false") else "auto"


_REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")


def _is_openai_model(model_id: str) -> bool:
    # Matches openai.gpt-..., in.openai..., global.openai..., and ARNs naming them.
    return "openai." in model_id


def _reasoning_fields(model_id: str) -> dict[str, Any] | None:
    """additionalModelRequestFields for reasoning effort, or None to omit."""
    effort = (optional_env("LLM_REASONING_EFFORT", "") or "").strip().lower()
    if not effort:
        return None
    if effort not in _REASONING_EFFORTS:
        raise BedrockConfigError(
            f"LLM_REASONING_EFFORT={effort!r} is invalid; use one of: "
            + ", ".join(_REASONING_EFFORTS)
        )
    if not _is_openai_model(model_id):
        logger.warning("LLM_REASONING_EFFORT is set but model %s is not an OpenAI model; "
                       "ignoring it.", model_id)
        return None
    # Converse shape for OpenAI models; a flat `reasoning_effort` is rejected.
    return {"reasoning": {"effort": effort}}


def resolve_chat_model(model: str | None = None) -> str:
    """Explicit model wins; placeholders resolve to BEDROCK_CHAT_MODEL. No hardcoded default."""
    requested = (model or "").strip()
    if requested not in _DEFAULT_MODEL_ALIASES:
        return requested
    configured = optional_env("BEDROCK_CHAT_MODEL", "").strip()
    if not configured:
        raise BedrockConfigError(
            "BEDROCK_CHAT_MODEL is not set. Set it to a verified model ID or inference "
            "profile ID available in BEDROCK_REGION (see docs/BEDROCK_GPT56_TERRA.md)."
        )
    return configured


# ── Message conversion (unchanged behaviour) ─────────────────────────────
def _message_text(msg: dict[str, Any]) -> str:
    content = msg.get("content")
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    return str(content or "").strip()


def _normalize_converse_messages(converse_messages: list[dict]) -> list[dict]:
    """Bedrock Converse requires user-first turns and alternating roles."""
    if not converse_messages:
        return [{"role": "user", "content": [{"text": "Hello"}]}]

    merged: list[dict] = []
    for msg in converse_messages:
        role = msg["role"]
        text = _message_text(msg)
        if not text:
            continue
        if merged and merged[-1]["role"] == role:
            prev = _message_text(merged[-1])
            merged[-1] = {
                "role": role,
                "content": [{"text": f"{prev}\n\n{text}".strip()}],
            }
        else:
            merged.append({"role": role, "content": [{"text": text}]})

    if not merged:
        return [{"role": "user", "content": [{"text": "Hello"}]}]

    # Converse rejects histories that begin with assistant (e.g. interview greeting).
    if merged[0]["role"] == "assistant":
        merged.insert(
            0,
            {
                "role": "user",
                "content": [{"text": "(Interview in progress — continue from the greeting.)"}],
            },
        )

    # Generation turns should end on a user message (several models reject
    # assistant-prefill).
    if merged[-1]["role"] == "assistant":
        merged.append(
            {"role": "user", "content": [{"text": "Please continue."}]}
        )

    return merged


def _to_converse_messages(messages: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    system_blocks: list[dict] = []
    converse_messages: list[dict] = []
    for msg in messages:
        role = (msg.get("role") or "user").strip().lower()
        text = _message_text(msg)
        if not text:
            continue
        if role == "system":
            system_blocks.append({"text": text})
            continue
        if role not in ("user", "assistant"):
            role = "user"
        converse_messages.append(
            {"role": role, "content": [{"text": text}]}
        )
    converse_messages = _normalize_converse_messages(converse_messages)
    return system_blocks, converse_messages


def _input_chars(system_blocks: list[dict], converse_messages: list[dict]) -> int:
    total = sum(len(b.get("text", "")) for b in system_blocks)
    for msg in converse_messages:
        total += sum(len(b.get("text", "")) for b in msg.get("content", []))
    return total


def _is_sampling_rejection(exc: BedrockError) -> bool:
    if not isinstance(exc, BedrockValidationError):
        return False
    lower = str(exc).lower()
    return any(word in lower for word in ("temperature", "top_p", "topp", "sampling"))


# ── Provider ──────────────────────────────────────────────────────────────
class BedrockLLMProvider:
    name = "bedrock"

    def __init__(self, client: Any = None) -> None:
        self._client = client or self._build_client()
        # Models that returned "temperature not supported"; we stop sending it.
        self._no_temperature_models: set[str] = set()
        self._diag_lock = threading.Lock()
        self._diag_cache: tuple[float, dict[str, Any]] | None = None

    @staticmethod
    def _build_client():
        boto3 = _boto3()
        try:
            from botocore.config import Config

            config = Config(
                region_name=_region(),
                connect_timeout=_int_env("BEDROCK_CONNECT_TIMEOUT_SECONDS", 5, 1, 60),
                read_timeout=_int_env("BEDROCK_READ_TIMEOUT_SECONDS", 120, 5, 900),
                # botocore "standard" mode: exponential backoff with jitter on
                # throttling, 5xx and transient connection errors only.
                retries={"mode": "standard",
                         "max_attempts": _int_env("BEDROCK_MAX_ATTEMPTS", 3, 1, 10)},
            )
            return boto3.client("bedrock-runtime", config=config)
        except ImportError:  # pragma: no cover - botocore ships with boto3
            return boto3.client("bedrock-runtime", region_name=_region())

    # -- request building --------------------------------------------------
    def _should_send_temperature(self, model_id: str) -> bool:
        mode = _send_temperature_mode()
        if mode == "false":
            return False
        if mode == "true":
            return True
        return model_id not in self._no_temperature_models

    def _build_kwargs(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        max_tokens: int | None,
        temperature: float | None,
    ) -> dict[str, Any]:
        system_blocks, converse_messages = _to_converse_messages(messages)
        limit = _int_env("LLM_MAX_INPUT_CHARS", 400_000, 1_000, 4_000_000)
        size = _input_chars(system_blocks, converse_messages)
        if size > limit:
            raise BedrockValidationError(
                f"Bedrock ValidationError: prompt is {size} characters, above "
                f"LLM_MAX_INPUT_CHARS={limit}. Trim the input before calling the model."
            )
        inference: dict[str, Any] = {"maxTokens": _max_tokens(max_tokens)}
        if self._should_send_temperature(model_id):
            inference["temperature"] = _temperature(temperature)
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": converse_messages,
            "inferenceConfig": inference,
        }
        if system_blocks:
            kwargs["system"] = system_blocks
        extra = _reasoning_fields(model_id)
        if extra:
            kwargs["additionalModelRequestFields"] = extra
        return kwargs

    def _invoke(self, op: str, model_id: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Call converse/converse_stream; drop temperature once if the model rejects it."""
        method = getattr(self._client, op)
        try:
            return method(**kwargs)
        except Exception as exc:  # noqa: BLE001 - translated below
            err = translate_error(exc, model_id)
            can_retry = (
                _send_temperature_mode() == "auto"
                and "temperature" in kwargs.get("inferenceConfig", {})
                and _is_sampling_rejection(err)
            )
            if not can_retry:
                self._log_failure(op, err)
                raise err from exc
            self._no_temperature_models.add(model_id)
            logger.warning(
                "Bedrock model %s rejected temperature; retrying without it "
                "(set LLM_SEND_TEMPERATURE=false to skip this probe).", model_id,
            )
            retry_kwargs = dict(kwargs)
            retry_kwargs["inferenceConfig"] = {
                k: v for k, v in kwargs["inferenceConfig"].items() if k != "temperature"
            }
            try:
                return method(**retry_kwargs)
            except Exception as exc2:  # noqa: BLE001
                err2 = translate_error(exc2, model_id)
                self._log_failure(op, err2)
                raise err2 from exc2

    @staticmethod
    def _log_failure(op: str, err: BedrockError) -> None:
        # Never log prompts or candidate answers — only the error metadata.
        logger.warning(
            "Bedrock %s failed: code=%s aws_code=%s request_id=%s retryable=%s",
            op, err.code, err.aws_code or "-", err.request_id or "-", err.retryable,
        )

    # -- public API ----------------------------------------------------------
    def chat(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        model_id = resolve_chat_model(model)
        kwargs = self._build_kwargs(model_id, messages, max_tokens, temperature)
        response = self._invoke("converse", model_id, kwargs)
        text = _extract_converse_text(response)
        stop_reason = response.get("stopReason") or ""
        if stop_reason == "max_tokens":
            # Reasoning models spend maxTokens on hidden reasoning first; an empty
            # reply here usually means the budget ran out before any answer text.
            logger.warning(
                "Bedrock response hit maxTokens=%s (model=%s, answer_chars=%d)%s",
                kwargs["inferenceConfig"]["maxTokens"], model_id, len(text),
                " — consider a lower LLM_REASONING_EFFORT" if not text else "",
            )
        raw_usage = response.get("usage") or {}
        usage = {
            "input_tokens": int(raw_usage.get("inputTokens") or 0),
            "output_tokens": int(raw_usage.get("outputTokens") or 0),
            "total_tokens": int(raw_usage.get("totalTokens") or 0),
        }
        if not usage["total_tokens"]:
            usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
        return {
            "message": {"content": text},
            "model": model_id,
            "provider": self.name,
            "usage": usage,
            "stop_reason": stop_reason,
        }

    def chat_stream(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        model_id = resolve_chat_model(model)
        kwargs = self._build_kwargs(model_id, messages, max_tokens, temperature)
        response = self._invoke("converse_stream", model_id, kwargs)
        try:
            for event in response.get("stream", []):
                for key, aws_code in _STREAM_ERROR_EVENTS.items():
                    if key in event:
                        detail = event[key] or {}
                        message = detail.get("message") or detail.get("originalMessage") or key
                        err = translate_error(
                            _StreamEventError(aws_code, str(message)), model_id
                        )
                        self._log_failure("converse_stream", err)
                        raise err
                stop = event.get("messageStop")
                if stop and stop.get("stopReason") == "max_tokens":
                    logger.warning("Bedrock stream hit maxTokens (model=%s)", model_id)
                # Only answer text is streamed; reasoningContent deltas are never
                # shown to candidates or spoken by TTS.
                delta = event.get("contentBlockDelta", {}).get("delta", {})
                text = delta.get("text")
                if text:
                    yield text
        except BedrockError:
            raise
        except Exception as exc:  # botocore EventStreamError, read timeouts mid-stream
            err = translate_error(exc, model_id)
            self._log_failure("converse_stream", err)
            raise err from exc

    def diagnostics(self, *, force: bool = False) -> dict[str, Any]:
        """Cached live probe. Health checks hit this often; model calls are billable."""
        ttl = _int_env("BEDROCK_DIAGNOSTICS_CACHE_SECONDS", 120, 0, 3600)
        with self._diag_lock:
            now = time.time()
            if not force and self._diag_cache and now - self._diag_cache[0] < ttl:
                return dict(self._diag_cache[1], cached=True)
            info = self._probe()
            self._diag_cache = (now, info)
            return dict(info, cached=False)

    def _probe(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "provider": self.name,
            "region": _region(),
            "model": optional_env("BEDROCK_CHAT_MODEL", ""),
            "ready": False,
            "reachable": False,
            "model_available": False,
            "error": "",
            "error_code": "",
        }
        try:
            info["model"] = resolve_chat_model()
            started = time.time()
            self.chat(
                model=info["model"],
                messages=[{"role": "user", "content": "Reply with OK only."}],
                max_tokens=64,
            )
            info.update(ready=True, reachable=True, model_available=True,
                        latency_ms=int((time.time() - started) * 1000))
        except BedrockError as exc:
            info["error"] = redact(str(exc))
            info["error_code"] = exc.code
            # Throttling/validation mean AWS answered; the endpoint is reachable.
            info["reachable"] = isinstance(
                exc, (BedrockThrottledError, BedrockValidationError, BedrockAccessDeniedError,
                      BedrockModelNotFoundError)
            )
        except Exception as exc:  # noqa: BLE001
            info["error"] = redact(str(exc))
            info["error_code"] = type(exc).__name__
        return info


class _StreamEventError(Exception):
    """Adapter so in-stream error events go through translate_error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.response = {"Error": {"Code": code, "Message": message}}


def _extract_converse_text(response: dict[str, Any]) -> str:
    output = response.get("output") or {}
    message = output.get("message") or {}
    parts = message.get("content") or []
    texts = []
    for part in parts:
        if isinstance(part, dict) and part.get("text"):
            texts.append(part["text"])
    return "".join(texts).strip()
