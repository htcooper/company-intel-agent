from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# ── Normalized response type ──────────────────────────────────────────────────


@dataclass
class LLMResponse:
    text: str
    sources: list[dict]  # [{"url": ..., "title": ...}, ...]


# ── Application-level exceptions ──────────────────────────────────────────────


class LLMAuthError(Exception):
    pass


class LLMRateLimitError(Exception):
    pass


class LLMTimeoutError(Exception):
    pass


# ── Provider config ───────────────────────────────────────────────────────────


@dataclass
class ProviderConfig:
    name: str
    display_name: str
    api_key_placeholder: str
    env_var: str
    research_model: str  # research passes + synthesis
    fast_model: str      # disambiguation + resolve (cheaper/faster)


PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "anthropic": ProviderConfig(
        name="anthropic",
        display_name="Anthropic Claude",
        api_key_placeholder="sk-ant-...",
        env_var="ANTHROPIC_API_KEY",
        research_model="claude-sonnet-4-6",
        fast_model="claude-haiku-4-5-20251001",
    ),
    "openai": ProviderConfig(
        name="openai",
        display_name="OpenAI GPT-4o",
        api_key_placeholder="sk-...",
        env_var="OPENAI_API_KEY",
        research_model="gpt-4o",
        fast_model="gpt-4o-mini",
    ),
}


# ── Adapter protocol ──────────────────────────────────────────────────────────


@runtime_checkable
class LLMAdapter(Protocol):
    def call_with_search(
        self,
        system: str,
        user: str,
        max_tokens: int,
        max_search_uses: int,
    ) -> LLMResponse: ...

    def call_text_only(
        self,
        system: str | None,
        user: str,
        max_tokens: int,
    ) -> LLMResponse: ...


# ── Anthropic adapter ─────────────────────────────────────────────────────────


class AnthropicAdapter:
    def __init__(self, api_key: str, model: str, timeout: float = 90.0) -> None:
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=anthropic.Timeout(timeout, connect=10.0),
        )
        self._model = model

    def call_with_search(
        self,
        system: str,
        user: str,
        max_tokens: int,
        max_search_uses: int,
    ) -> LLMResponse:
        tools = [
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": max_search_uses,
                "allowed_callers": ["direct"],
            }
        ]
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                tools=tools,
            )
        except self._anthropic.AuthenticationError as e:
            raise LLMAuthError(str(e)) from e
        except self._anthropic.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except self._anthropic.APITimeoutError as e:
            raise LLMTimeoutError(str(e)) from e
        return LLMResponse(
            text=self._extract_text(response),
            sources=self._extract_sources(response),
        )

    def call_text_only(
        self,
        system: str | None,
        user: str,
        max_tokens: int,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user}],
        }
        if system:
            kwargs["system"] = system
        try:
            response = self._client.messages.create(**kwargs)
        except self._anthropic.AuthenticationError as e:
            raise LLMAuthError(str(e)) from e
        except self._anthropic.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except self._anthropic.APITimeoutError as e:
            raise LLMTimeoutError(str(e)) from e
        return LLMResponse(text=self._extract_text(response), sources=[])

    def _extract_text(self, response) -> str:
        return "\n\n".join(
            block.text for block in response.content if block.type == "text"
        )

    def _extract_sources(self, response) -> list[dict]:
        sources: list[dict] = []
        seen: set[str] = set()

        for block in response.content:
            if block.type == "text":
                for c in getattr(block, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url and url not in seen:
                        seen.add(url)
                        sources.append({"url": url, "title": getattr(c, "title", url)})

        if not sources:
            for block in response.content:
                if getattr(block, "type", None) == "web_search_tool_result":
                    for result in getattr(block, "content", []) or []:
                        url = getattr(result, "url", None)
                        if url and url not in seen:
                            seen.add(url)
                            sources.append(
                                {"url": url, "title": getattr(result, "title", url)}
                            )

        return sources


# ── OpenAI adapter ────────────────────────────────────────────────────────────

_OPENAI_SEARCH_MODEL = "gpt-4o-search-preview"


class OpenAIAdapter:
    def __init__(self, api_key: str, model: str, timeout: float = 90.0) -> None:
        import openai

        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout)
        self._model = model

    def call_with_search(
        self,
        system: str,
        user: str,
        max_tokens: int,
        max_search_uses: int,
    ) -> LLMResponse:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            response = self._client.chat.completions.create(
                model=_OPENAI_SEARCH_MODEL,
                max_tokens=max_tokens,
                messages=messages,
                tools=[{"type": "web_search_preview"}],
            )
        except self._openai.AuthenticationError as e:
            raise LLMAuthError(str(e)) from e
        except self._openai.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except self._openai.APITimeoutError as e:
            raise LLMTimeoutError(str(e)) from e
        return LLMResponse(
            text=self._extract_text(response),
            sources=self._extract_sources(response),
        )

    def call_text_only(
        self,
        system: str | None,
        user: str,
        max_tokens: int,
    ) -> LLMResponse:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=messages,
            )
        except self._openai.AuthenticationError as e:
            raise LLMAuthError(str(e)) from e
        except self._openai.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except self._openai.APITimeoutError as e:
            raise LLMTimeoutError(str(e)) from e
        return LLMResponse(text=self._extract_text(response), sources=[])

    def _extract_text(self, response) -> str:
        return response.choices[0].message.content or ""

    def _extract_sources(self, response) -> list[dict]:
        sources: list[dict] = []
        seen: set[str] = set()
        annotations = getattr(response.choices[0].message, "annotations", None) or []
        for ann in annotations:
            if getattr(ann, "type", None) == "url_citation":
                citation = getattr(ann, "url_citation", None)
                if citation:
                    url = getattr(citation, "url", None)
                    title = getattr(citation, "title", url)
                    if url and url not in seen:
                        seen.add(url)
                        sources.append({"url": url, "title": title})
        return sources


# ── Factory ───────────────────────────────────────────────────────────────────


def make_adapter(
    provider: str,
    api_key: str,
    model: str,
    timeout: float = 90.0,
) -> LLMAdapter:
    if provider == "anthropic":
        return AnthropicAdapter(api_key, model, timeout)
    elif provider == "openai":
        return OpenAIAdapter(api_key, model, timeout)
    raise ValueError(f"Unknown provider: {provider!r}")
