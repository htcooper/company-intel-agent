from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


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
        display_name="Anthropic",
        api_key_placeholder="sk-ant-...",
        env_var="ANTHROPIC_API_KEY",
        research_model="claude-sonnet-4-6",
        fast_model="claude-haiku-5-5",
    ),
    "openai": ProviderConfig(
        name="openai",
        display_name="OpenAI",
        api_key_placeholder="sk-...",
        env_var="OPENAI_API_KEY",
        research_model="gpt-4o",
        fast_model="gpt-4o-mini",
    ),
}


# ── Source URL cleanup ────────────────────────────────────────────────────────


def _clean_url(url: str | None) -> str | None:
    """Drop utm_* tracking parameters (e.g. OpenAI's ?utm_source=openai),
    keeping every other query parameter and the fragment."""
    if not url:
        return url
    parts = urlsplit(url)
    if "utm_" not in parts.query:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_")]
    return urlunsplit(parts._replace(query=urlencode(query)))


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


# Models that support the dynamic-filtering web search tool (web_search_20260209).
# Older models (e.g. Haiku 4.5) need the basic web_search_20250305 variant.
_DYNAMIC_SEARCH_MODEL_PREFIXES = (
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-opus-5",
    "claude-sonnet-4-6", "claude-sonnet-5", "claude-fable", "claude-mythos",
)


def _anthropic_search_tool(model: str, max_uses: int) -> dict:
    if model.startswith(_DYNAMIC_SEARCH_MODEL_PREFIXES):
        return {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": max_uses,
            "allowed_callers": ["direct"],
        }
    return {"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}


class AnthropicAdapter:
    def __init__(
        self, api_key: str, model: str, timeout: float = 90.0, max_retries: int = 2
    ) -> None:
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=anthropic.Timeout(timeout, connect=10.0),
            max_retries=max_retries,
        )
        self._model = model

    def call_with_search(
        self,
        system: str,
        user: str,
        max_tokens: int,
        max_search_uses: int,
    ) -> LLMResponse:
        tools = [_anthropic_search_tool(self._model, max_search_uses)]
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
                    url = _clean_url(getattr(c, "url", None))
                    if url and url not in seen:
                        seen.add(url)
                        sources.append({"url": url, "title": getattr(c, "title", url)})

        if not sources:
            for block in response.content:
                if getattr(block, "type", None) == "web_search_tool_result":
                    for result in getattr(block, "content", []) or []:
                        url = _clean_url(getattr(result, "url", None))
                        if url and url not in seen:
                            seen.add(url)
                            sources.append(
                                {"url": url, "title": getattr(result, "title", url)}
                            )

        return sources


# ── OpenAI adapter ────────────────────────────────────────────────────────────


class OpenAIAdapter:
    def __init__(
        self, api_key: str, model: str, timeout: float = 90.0, max_retries: int = 2
    ) -> None:
        import openai

        self._openai = openai
        self._client = openai.OpenAI(
            api_key=api_key, timeout=timeout, max_retries=max_retries
        )
        self._model = model

    def call_with_search(
        self,
        system: str,
        user: str,
        max_tokens: int,
        max_search_uses: int,
    ) -> LLMResponse:
        # web_search_preview is a Responses API tool, not Chat Completions.
        # Chat Completions only accepts function/custom tool types.
        try:
            response = self._client.responses.create(
                model=self._model,
                tools=[{"type": "web_search_preview"}],
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_output_tokens=max_tokens,
            )
        except self._openai.AuthenticationError as e:
            raise LLMAuthError(str(e)) from e
        except self._openai.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except self._openai.APITimeoutError as e:
            raise LLMTimeoutError(str(e)) from e
        return LLMResponse(
            text=self._extract_responses_text(response),
            sources=self._extract_responses_sources(response),
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
                    url = _clean_url(getattr(citation, "url", None))
                    title = getattr(citation, "title", url)
                    if url and url not in seen:
                        seen.add(url)
                        sources.append({"url": url, "title": title})
        return sources

    def _extract_responses_text(self, response) -> str:
        text = getattr(response, "output_text", None)
        if text:
            return text
        parts: list[str] = []
        for item in getattr(response, "output", None) or []:
            if getattr(item, "type", None) == "message":
                for content in getattr(item, "content", None) or []:
                    if getattr(content, "type", None) == "output_text":
                        parts.append(getattr(content, "text", "") or "")
        return "\n\n".join(p for p in parts if p)

    def _extract_responses_sources(self, response) -> list[dict]:
        sources: list[dict] = []
        seen: set[str] = set()
        for item in getattr(response, "output", None) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", None) or []:
                for ann in getattr(content, "annotations", None) or []:
                    if getattr(ann, "type", None) != "url_citation":
                        continue
                    url = _clean_url(getattr(ann, "url", None))
                    title = getattr(ann, "title", url)
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
    max_retries: int = 2,
) -> LLMAdapter:
    """Build a provider adapter. The SDKs retry 429s/5xx with backoff
    up to max_retries times before raising."""
    if provider == "anthropic":
        return AnthropicAdapter(api_key, model, timeout, max_retries)
    elif provider == "openai":
        return OpenAIAdapter(api_key, model, timeout, max_retries)
    raise ValueError(f"Unknown provider: {provider!r}")
