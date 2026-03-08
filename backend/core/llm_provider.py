"""
QAForge -- Pluggable LLM Provider Abstraction
===============================================
Switch providers via the LLM_PROVIDER environment variable:
  LLM_PROVIDER=anthropic   (default) -- uses claude-3-5-haiku / claude-3-5-sonnet
  LLM_PROVIDER=openai               -- uses gpt-4o-mini / gpt-4o
  LLM_PROVIDER=groq                 -- uses Groq cloud inference (blazing fast)
  LLM_PROVIDER=ollama               -- local Ollama server (llama3, mistral, etc.)
  LLM_PROVIDER=mock                 -- deterministic mock for testing (no API key needed)

Provider-specific config via environment variables:
  Anthropic:  ANTHROPIC_API_KEY
  OpenAI:     OPENAI_API_KEY, OPENAI_BASE_URL (optional, for Azure / proxies)
  Groq:       GROQ_API_KEY
  Ollama:     OLLAMA_BASE_URL (default http://localhost:11434)

Model selection (optional overrides):
  LLM_FAST_MODEL   -- used for per-agent tasks (default per-provider)
  LLM_SMART_MODEL  -- used for complex reasoning (default per-provider)
"""

from __future__ import annotations

import os
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# -- LLM Response with token tracking -----------------------------------------

@dataclass
class LLMResponse:
    """Wraps an LLM completion result with token usage metadata."""

    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    provider: str = ""
    raw: Any = field(default=None, repr=False)

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed (input + output)."""
        return self.tokens_in + self.tokens_out


# -- Abstract base -------------------------------------------------------------

class LLMProvider(ABC):
    """
    Abstract LLM provider. All implementations must support:
      - complete()  -> LLMResponse  (blocking, with token counts)
      - stream()    -> iterator of string chunks (streaming, no token counts)
    """

    @abstractmethod
    def complete(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a single completion with token tracking."""
        ...

    @abstractmethod
    def stream(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream completion tokens. Token counts are not tracked in streaming mode."""
        ...

    def complete_text(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """Convenience: return just the text string (backward-compatible)."""
        return self.complete(system, messages, max_tokens, temperature, **kwargs).text

    def build_messages(self, role: str, content: str) -> Dict[str, str]:
        """Helper to construct a single message dict."""
        return {"role": role, "content": content}

    @property
    def provider_name(self) -> str:
        """Human-readable provider class name."""
        return self.__class__.__name__

    def ping(self, timeout_seconds: int = 15) -> bool:
        """Quick health check -- send a trivial prompt and verify we get a response."""
        try:
            result = self.complete(
                system="Respond with exactly: OK",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=4, temperature=0,
            )
            return bool(result.text and len(result.text.strip()) > 0)
        except Exception as exc:
            logger.warning("Provider ping failed (%s): %s", self.provider_name, exc)
            return False


# -- Anthropic (Claude) -------------------------------------------------------

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider (claude-haiku / claude-sonnet)."""

    DEFAULT_FAST_MODEL = "claude-haiku-4-5-20251001"
    DEFAULT_SMART_MODEL = "claude-sonnet-4-5-20250929"

    def __init__(self, use_defaults: bool = False) -> None:
        try:
            import anthropic as _anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic>=0.25.0"
            ) from exc
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        self._client = _anthropic.Anthropic(api_key=api_key)
        if use_defaults:
            self.fast_model = self.DEFAULT_FAST_MODEL
            self.smart_model = self.DEFAULT_SMART_MODEL
        else:
            self.fast_model = os.environ.get("LLM_FAST_MODEL", self.DEFAULT_FAST_MODEL)
            self.smart_model = os.environ.get("LLM_SMART_MODEL", self.DEFAULT_SMART_MODEL)
        logger.info("AnthropicProvider ready. fast=%s smart=%s", self.fast_model, self.smart_model)

    def _pick_model(self, kwargs: Dict) -> str:
        return kwargs.pop("model", self.fast_model)

    def complete(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> LLMResponse:
        model = self._pick_model(kwargs)
        resp = self._client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system, messages=messages,
        )
        tokens_in = getattr(resp.usage, "input_tokens", 0)
        tokens_out = getattr(resp.usage, "output_tokens", 0)
        return LLMResponse(
            text=resp.content[0].text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            provider="anthropic",
            raw=resp,
        )

    def stream(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> Iterator[str]:
        model = self._pick_model(kwargs)
        with self._client.messages.stream(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system, messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text


# -- OpenAI (GPT / Azure / compatible) ----------------------------------------

class OpenAIProvider(LLMProvider):
    """OpenAI provider (gpt-4o-mini / gpt-4o). Also works with Azure and compatible APIs."""

    DEFAULT_FAST_MODEL = "gpt-4o-mini"
    DEFAULT_SMART_MODEL = "gpt-4o"

    def __init__(self, use_defaults: bool = False) -> None:
        try:
            import openai as _openai
        except ImportError as exc:
            raise ImportError(
                "openai package not installed. Run: pip install openai>=1.10.0"
            ) from exc
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        ctor_kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            ctor_kwargs["base_url"] = base_url
        self._client = _openai.OpenAI(**ctor_kwargs)
        if use_defaults:
            self.fast_model = self.DEFAULT_FAST_MODEL
            self.smart_model = self.DEFAULT_SMART_MODEL
        else:
            self.fast_model = os.environ.get("LLM_FAST_MODEL", self.DEFAULT_FAST_MODEL)
            self.smart_model = os.environ.get("LLM_SMART_MODEL", self.DEFAULT_SMART_MODEL)
        logger.info("OpenAIProvider ready. fast=%s smart=%s", self.fast_model, self.smart_model)

    def _pick_model(self, kwargs: Dict) -> str:
        return kwargs.pop("model", self.fast_model)

    def _build_openai_messages(
        self, system: str, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        return [{"role": "system", "content": system}] + messages

    def complete(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> LLMResponse:
        model = self._pick_model(kwargs)
        resp = self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=self._build_openai_messages(system, messages),
        )
        usage = resp.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            provider="openai",
            raw=resp,
        )

    def stream(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> Iterator[str]:
        model = self._pick_model(kwargs)
        stream = self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=self._build_openai_messages(system, messages), stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# -- Groq (cloud inference -- blazing fast) ------------------------------------

class GroqProvider(LLMProvider):
    """Groq cloud inference provider (OpenAI-compatible API, ultra-low latency)."""

    DEFAULT_FAST_MODEL = "llama-3.1-8b-instant"
    DEFAULT_SMART_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, use_defaults: bool = False) -> None:
        try:
            import openai as _openai
        except ImportError as exc:
            raise ImportError(
                "openai package not installed. Run: pip install openai>=1.10.0"
            ) from exc
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set.")
        self._client = _openai.OpenAI(
            api_key=api_key, base_url="https://api.groq.com/openai/v1"
        )
        if use_defaults:
            self.fast_model = self.DEFAULT_FAST_MODEL
            self.smart_model = self.DEFAULT_SMART_MODEL
        else:
            self.fast_model = os.environ.get("LLM_FAST_MODEL", self.DEFAULT_FAST_MODEL)
            self.smart_model = os.environ.get("LLM_SMART_MODEL", self.DEFAULT_SMART_MODEL)
        logger.info("GroqProvider ready. fast=%s smart=%s", self.fast_model, self.smart_model)

    def _pick_model(self, kwargs: Dict) -> str:
        return kwargs.pop("model", self.fast_model)

    def _build_messages(
        self, system: str, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        return [{"role": "system", "content": system}] + messages

    def complete(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> LLMResponse:
        model = self._pick_model(kwargs)
        resp = self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=self._build_messages(system, messages),
        )
        usage = resp.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            provider="groq",
            raw=resp,
        )

    def stream(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> Iterator[str]:
        model = self._pick_model(kwargs)
        stream = self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=self._build_messages(system, messages), stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# -- Ollama (local) ------------------------------------------------------------

class OllamaProvider(LLMProvider):
    """Local Ollama server provider (llama3, qwen, mistral, etc.)."""

    DEFAULT_FAST_MODEL = "llama3.2"
    DEFAULT_SMART_MODEL = "qwen2.5"

    def __init__(self, use_defaults: bool = False) -> None:
        try:
            import requests as _requests  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "requests package not installed. Run: pip install requests"
            ) from exc
        import requests
        self._requests = requests
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        if use_defaults:
            self.fast_model = self.DEFAULT_FAST_MODEL
            self.smart_model = self.DEFAULT_SMART_MODEL
        else:
            self.fast_model = os.environ.get("LLM_FAST_MODEL", self.DEFAULT_FAST_MODEL)
            self.smart_model = os.environ.get("LLM_SMART_MODEL", self.DEFAULT_SMART_MODEL)
        try:
            resp = self._requests.get(f"{self.base_url}/api/tags", timeout=5)
            models = [m["name"] for m in resp.json().get("models", [])]
            logger.info("OllamaProvider ready. base_url=%s models=%s", self.base_url, models)
        except Exception:
            logger.warning("Could not connect to Ollama at %s.", self.base_url)

    def _pick_model(self, kwargs: Dict) -> str:
        return kwargs.pop("model", self.fast_model)

    def _build_chat_messages(
        self, system: str, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        return [{"role": "system", "content": system}] + messages

    def complete(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> LLMResponse:
        model = self._pick_model(kwargs)
        resp = self._requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model,
                "messages": self._build_chat_messages(system, messages),
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns token counts in eval_count / prompt_eval_count
        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)
        return LLMResponse(
            text=data.get("message", {}).get("content", ""),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            provider="ollama",
            raw=data,
        )

    def stream(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> Iterator[str]:
        model = self._pick_model(kwargs)
        with self._requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model,
                "messages": self._build_chat_messages(system, messages),
                "stream": True,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            stream=True,
            timeout=180,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break


# -- Mock (testing / CI) -------------------------------------------------------

class MockProvider(LLMProvider):
    """Deterministic mock provider for testing -- no API key needed."""

    def __init__(self) -> None:
        logger.warning("MockProvider active -- responses are pre-scripted, not real AI.")

    def complete(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> LLMResponse:
        last = messages[-1].get("content", "") if messages else ""
        if "test_case" in last.lower() or "test case" in system.lower() or "generate" in system.lower():
            text = json.dumps([
                {
                    "test_case_id": "TC-MOCK-001",
                    "title": "Mock Test Case -- Verify basic functionality",
                    "description": "Verify the system handles the primary scenario correctly.",
                    "preconditions": "System is running and accessible.",
                    "test_steps": [
                        {"step_number": 1, "action": "Open the application", "expected_result": "Application loads"},
                        {"step_number": 2, "action": "Perform the action", "expected_result": "Expected outcome"},
                    ],
                    "expected_result": "System behaves as specified.",
                    "priority": "High",
                    "category": "Functional",
                    "domain_tags": ["mock", "testing"],
                }
            ])
        elif "review" in system.lower():
            text = json.dumps({
                "coverage_score": 85,
                "gaps": [],
                "duplicates": [],
                "quality_issues": [],
                "suggestions": ["Add edge-case test for empty input"],
            })
        else:
            text = "Thank you for your message. How can I help you further?"

        # Simulate token counts based on content length
        estimated_in = sum(len(m.get("content", "")) // 4 for m in messages) + len(system) // 4
        estimated_out = len(text) // 4
        return LLMResponse(
            text=text,
            tokens_in=estimated_in,
            tokens_out=estimated_out,
            model="mock",
            provider="mock",
        )

    def stream(self, system, messages, max_tokens=1024, temperature=0.7, **kwargs) -> Iterator[str]:
        full = self.complete(system, messages, max_tokens, temperature, **kwargs).text
        words = full.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")


# -- Factory -------------------------------------------------------------------

_PROVIDERS: Dict[str, type] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "groq": GroqProvider,
    "ollama": OllamaProvider,
    "mock": MockProvider,
}

_instance: Optional[LLMProvider] = None


def get_llm_provider(force_reinit: bool = False) -> LLMProvider:
    """Return a singleton LLM provider instance based on LLM_PROVIDER env var."""
    global _instance
    if _instance is None or force_reinit:
        name = os.environ.get("LLM_PROVIDER", "anthropic").lower()
        cls = _PROVIDERS.get(name)
        if cls is None:
            raise ValueError(f"Unknown LLM_PROVIDER '{name}'. Valid: {', '.join(_PROVIDERS)}")
        logger.info("Initialising LLM provider: %s", name)
        _instance = cls()
    return _instance


def get_provider_by_name(name: str) -> LLMProvider:
    """Instantiate a specific provider by name (for per-agent provider switching)."""
    cls = _PROVIDERS.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown provider '{name}'. Valid: {', '.join(_PROVIDERS)}")
    return cls()


def list_providers() -> Dict[str, bool]:
    """Return all providers with availability status (True = can be instantiated)."""
    result: Dict[str, bool] = {}
    for name in _PROVIDERS:
        try:
            _PROVIDERS[name]()
            result[name] = True
        except Exception:
            result[name] = False
    return result
