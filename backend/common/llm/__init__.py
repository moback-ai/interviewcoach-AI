"""LLM providers for prod (Bedrock) and local dev (Ollama)."""
from common.llm.bedrock import BedrockError, is_fatal_llm_error
from common.llm.factory import chat, chat_stream, get_llm_diagnostics, provider_name

__all__ = [
    "BedrockError",
    "chat",
    "chat_stream",
    "get_llm_diagnostics",
    "is_fatal_llm_error",
    "provider_name",
]
