from __future__ import annotations

from typing import Any, Iterator, Protocol


class LLMProvider(Protocol):
    name: str

    def chat(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Return Ollama-compatible shape: {"message": {"content": "..."}}."""

    def chat_stream(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        ...

    def diagnostics(self) -> dict[str, Any]:
        ...
