"""Provider abstraction for LLM calls.

All AI features call ``get_provider().generate(...)``. The concrete provider
is selected at runtime by the ``LLM_PROVIDER`` environment variable. Failures
return an ``AIResponse`` with ``success=False`` rather than raising — AI is
always optional and should never block CRM operations.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from app.config import settings

logger = logging.getLogger("legacy_crm.ai")


@dataclass
class AIResponse:
    content: str
    provider: str
    model: str
    tokens_used: int = 0
    duration_ms: int = 0
    success: bool = True
    error: Optional[str] = None


class AIProvider:
    name = "base"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str = "text",
    ) -> AIResponse:
        raise NotImplementedError


# ---------- None ----------


class NoneProvider(AIProvider):
    """No-op provider. Returns an empty, successful response.

    Used in production environments with AI disabled and as the default
    in test environments unless explicitly overridden.
    """

    name = "none"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str = "text",
    ) -> AIResponse:
        logger.info("AI generate skipped (provider=none)")
        return AIResponse(
            content="",
            provider="none",
            model="none",
            tokens_used=0,
            duration_ms=0,
            success=True,
            error=None,
        )


# ---------- Mock (test only) ----------


class MockProvider(AIProvider):
    """Deterministic provider for tests. Echoes a synthesized response.

    Selected when ``LLM_PROVIDER=mock`` or via ``set_provider()`` override
    inside a test fixture.
    """

    name = "mock"

    def __init__(self, model: str = "mock-1", canned: Optional[str] = None):
        self.model = model
        self.canned = canned

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str = "text",
    ) -> AIResponse:
        if self.canned is not None:
            content = self.canned
        else:
            content = (
                f"[MOCK AI] system={system_prompt[:40]!r} "
                f"user={user_prompt[:40]!r}"
            )
        return AIResponse(
            content=content,
            provider="mock",
            model=self.model,
            tokens_used=len(content.split()),
            duration_ms=1,
            success=True,
        )


# ---------- Ollama ----------


class OllamaProvider(AIProvider):
    """HTTP client for a local Ollama server (OpenAI-compatible endpoint)."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str = "text",
    ) -> AIResponse:
        import httpx  # local import keeps test boot fast

        url = f"{self.base_url}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format == "json":
            body["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            response = httpx.post(url, json=body, timeout=self.timeout)
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Ollama call failed: %s", exc)
            return AIResponse(
                content="",
                provider="ollama",
                model=self.model,
                duration_ms=int((time.perf_counter() - started) * 1000),
                success=False,
                error=str(exc),
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            payload = response.json()
            choices = payload.get("choices") or []
            content = (
                choices[0].get("message", {}).get("content", "")
                if choices
                else ""
            )
            usage = payload.get("usage") or {}
            tokens = int(usage.get("total_tokens") or 0)
        except Exception as exc:
            logger.warning("Ollama response parse failed: %s", exc)
            return AIResponse(
                content="",
                provider="ollama",
                model=self.model,
                duration_ms=elapsed_ms,
                success=False,
                error=f"Parse error: {exc}",
            )
        return AIResponse(
            content=content.strip(),
            provider="ollama",
            model=self.model,
            tokens_used=tokens,
            duration_ms=elapsed_ms,
            success=True,
        )


# ---------- Claude ----------


class ClaudeProvider(AIProvider):
    """Anthropic Claude API. Imports the SDK lazily so it's only required
    when this provider is actually selected."""

    name = "claude"

    def __init__(self, api_key: str, model: str, timeout: float):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str = "text",
    ) -> AIResponse:
        try:
            from anthropic import Anthropic  # type: ignore
        except ImportError as exc:
            logger.warning("anthropic SDK not installed: %s", exc)
            return AIResponse(
                content="",
                provider="claude",
                model=self.model,
                success=False,
                error=f"anthropic SDK missing: {exc}",
            )

        client = Anthropic(api_key=self.api_key, timeout=self.timeout)
        started = time.perf_counter()
        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            logger.warning("Claude call failed: %s", exc)
            return AIResponse(
                content="",
                provider="claude",
                model=self.model,
                duration_ms=int((time.perf_counter() - started) * 1000),
                success=False,
                error=str(exc),
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            blocks = message.content or []
            text_parts = [b.text for b in blocks if getattr(b, "type", None) == "text"]
            content = "".join(text_parts).strip()
            usage = getattr(message, "usage", None)
            tokens = 0
            if usage is not None:
                tokens = int(
                    (getattr(usage, "input_tokens", 0) or 0)
                    + (getattr(usage, "output_tokens", 0) or 0)
                )
        except Exception as exc:
            logger.warning("Claude response parse failed: %s", exc)
            return AIResponse(
                content="",
                provider="claude",
                model=self.model,
                duration_ms=elapsed_ms,
                success=False,
                error=f"Parse error: {exc}",
            )

        return AIResponse(
            content=content,
            provider="claude",
            model=self.model,
            tokens_used=tokens,
            duration_ms=elapsed_ms,
            success=True,
        )


# ---------- Factory + override ----------


_provider_override: Optional[AIProvider] = None


def set_provider(provider: Optional[AIProvider]) -> None:
    """Override the active provider, primarily for tests."""
    global _provider_override
    _provider_override = provider


def get_provider() -> AIProvider:
    if _provider_override is not None:
        return _provider_override
    if not settings.ai_enabled:
        return NoneProvider()

    name = (settings.llm_provider or "none").lower()
    if name == "claude":
        if not settings.claude_api_key:
            logger.warning("LLM_PROVIDER=claude but CLAUDE_API_KEY is not set")
            return NoneProvider()
        return ClaudeProvider(
            api_key=settings.claude_api_key,
            model=settings.llm_model or "claude-sonnet-4-20250514",
            timeout=settings.ai_request_timeout_seconds,
        )
    if name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.llm_model or "qwen3:8b",
            timeout=settings.ai_request_timeout_seconds,
        )
    if name == "mock":
        return MockProvider(model=settings.llm_model or "mock-1")
    return NoneProvider()
