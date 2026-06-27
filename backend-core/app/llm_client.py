"""LLM client with adaptive provider routing.

Three tiers, picked automatically on every request:

1. **Premium** — caller supplied an API key in the request, OR a premium key
   is set in the environment. The backend dispatches straight to the upstream
   provider (OpenAI, Anthropic, Gemini, or Groq) bypassing the edge router.
   Only triggered when a real key is configured; safe to leave unset.

2. **Free edge chain** — primary path when no premium key exists. Calls the
   Cloudflare Worker which tries ``cf-[redacted]-3.3-70b-instruct-fp8-fast``,
   then gemma-3-12b, qwen2.5-coder-32b, then OpenRouter free models.

3. **Local stub** — last-resort, deterministic offline response so the API
   never returns 5xx in a demo. Used only if the worker is unreachable and
   no premium key is set.

The active tier is exposed via :func:`current_provider` and surfaced through
``GET /api/provider-status`` so operators can confirm routing at any time.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, List, Optional

import httpx

logger = logging.getLogger("llm_client")

def _env(name: str) -> str:
    """Read an env var fresh each call so runtime changes take effect."""
    return os.getenv(name, "").strip()


def _edge_router_url() -> str:
    return _env("EDGE_ROUTER_URL").rstrip("/")


def _openai_key() -> str: return _env("OPENAI_API_KEY")
def _anthropic_key() -> str: return _env("ANTHROPIC_API_KEY")
def _gemini_key() -> str: return _env("GEMINI_API_KEY")
def _groq_key() -> str: return _env("GROQ_API_KEY")

# Back-compat aliases — module-level constants for tests / external introspection.
OPENAI_KEY = _openai_key()
ANTHROPIC_KEY = _anthropic_key()
GEMINI_KEY = _gemini_key()
GROQ_KEY = _groq_key()

# Premium model overrides — sensible defaults per provider.
_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Premium request budget is shorter — these APIs are usually faster.
PREMIUM_TIMEOUT_SECONDS = float(os.getenv("PREMIUM_TIMEOUT_SECONDS", "45"))
EDGE_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

def _first_premium_provider() -> Optional[dict[str, str]]:
    """Return the highest-priority premium provider config, or None.

    Reads keys via os.getenv each call so a key set after import (Render
    env-var changes, test setup) is picked up immediately.
    """
    if _openai_key():
        return {"provider": "openai", "model": _OPENAI_MODEL, "key": _openai_key(),
                "base_url": "https://api.openai.com/v1"}
    if _anthropic_key():
        return {"provider": "anthropic", "model": _ANTHROPIC_MODEL, "key": _anthropic_key(),
                "base_url": "https://api.anthropic.com"}
    if _gemini_key():
        return {"provider": "gemini", "model": _GEMINI_MODEL, "key": _gemini_key(),
                "base_url": "https://generativelanguage.googleapis.com"}
    if _groq_key():
        return {"provider": "groq", "model": _GROQ_MODEL, "key": _groq_key(),
                "base_url": "https://api.groq.com/openai/v1"}
    return None


def current_provider() -> dict[str, Any]:
    """Describe which provider is active right now.

    Safe to call on every request; never raises.
    """
    premium = _first_premium_provider()
    if premium:
        return {
            "tier": "premium",
            "provider": premium["provider"],
            "model": premium["model"],
            "via": "direct",
            "edge_router_configured": bool(_edge_router_url()),
            "fallback_chain": ["edge_router_free", "local_stub"],
        }
    return {
        "tier": "free",
        "provider": "edge_router",
        "model": "cf-llama",
        "via": "cloudflare_worker",
        "edge_router_configured": bool(_edge_router_url()),
        "fallback_chain": ["openrouter_free", "local_stub"],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def call_llm(
    prompt: Optional[str] = None,
    messages: Optional[List[dict]] = None,
    temperature: float = 0.2,
    api_key: Optional[str] = None,
    max_tokens: int = 1000,
    response_mode: str = "json",
    model: Optional[str] = None,
    lang: Optional[str] = None,
    prefer_premium: bool = True,
) -> Any:
    """Call the best available LLM.

    Resolution order per request:
      1. Caller-supplied ``api_key`` (per-request override, e.g. browser).
      2. Server-configured premium key (OpenAI → Anthropic → Gemini → Groq).
      3. Cloudflare edge router free chain.
      4. Local offline stub (demo safety net).

    Args:
        prompt: Single-shot user prompt. Ignored when ``messages`` is set.
        messages: Pre-built chat messages list.
        temperature: Sampling temperature.
        api_key: Optional caller-supplied key (forwarded as ``x-api-key``).
        max_tokens: Hard cap on response tokens.
        response_mode: ``"json"`` parses the body; ``"raw"`` returns text.
        model: Model override. ``None`` uses the provider default.
        lang: Optional language hint forwarded to the worker.
        prefer_premium: When False, skip premium even if a key exists (used
            for cost-controlled bulk calls).
    """
    if not messages and not prompt:
        raise ValueError("Either prompt or messages must be provided")

    if messages is None:
        messages = [
            {"role": "system", "content": "You are a strict JSON-outputting assistant. Reply only with valid JSON unless told otherwise."},
            {"role": "user", "content": prompt or ""},
        ]

    # Strip empty assistant content early — some upstream APIs reject it.
    messages = [
        {**m, "content": m.get("content") or ""} if m.get("role") != "user" else m
        for m in messages
    ]

    # 1. Caller-supplied key — takes priority over server config.
    if api_key and prefer_premium:
        text = await _call_premium(api_key, model, messages, temperature, max_tokens)
        return _shape(text, response_mode)

    # 2. Server-configured premium key.
    if prefer_premium:
        premium = _first_premium_provider()
        if premium:
            try:
                text = await _call_premium(
                    premium["key"], model or premium["model"], messages,
                    temperature, max_tokens,
                )
                return _shape(text, response_mode)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Premium provider %s failed, falling back to edge router: %s",
                               premium["provider"], exc)

    # 3. Free edge router (current production path).
    try:
        return await call_edge_router(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_mode=response_mode,
            model=model or "cf-llama",
            lang=lang,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Edge router unavailable, falling back to local stub: %s", exc)

    # 4. Offline stub — keeps the demo alive even with no network.
    return _local_stub(messages, response_mode)


# ---------------------------------------------------------------------------
# Premium dispatch
# ---------------------------------------------------------------------------

async def _call_premium(
    api_key: str,
    model: Optional[str],
    messages: List[dict],
    temperature: float,
    max_tokens: int,
) -> str:
    """Dispatch to the correct upstream provider based on key shape."""
    key_lower = api_key.lower()
    if key_lower.startswith("sk-ant-"):
        return await _call_anthropic(api_key, model or _ANTHROPIC_MODEL, messages, temperature, max_tokens)
    if key_lower.startswith("sk-"):
        return await _call_openai_compat(api_key, model or _OPENAI_MODEL, messages, temperature, max_tokens,
                                          base="https://api.openai.com/v1")
    if key_lower.startswith("gsk_"):
        return await _call_openai_compat(api_key, model or _GROQ_MODEL, messages, temperature, max_tokens,
                                          base="https://api.groq.com/openai/v1")
    # Gemini keys are 39 chars starting with "AIza" — treat anything else as Gemini too.
    return await _call_gemini(api_key, model or _GEMINI_MODEL, messages, temperature, max_tokens)


async def _call_openai_compat(
    api_key: str, model: str, messages: List[dict],
    temperature: float, max_tokens: int, base: str,
) -> str:
    url = f"{base}/chat/completions"
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=PREMIUM_TIMEOUT_SECONDS) as client:
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code >= 400:
                    raise RuntimeError(f"{base} returned {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"{base} call failed after retries: {exc}") from exc
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("unreachable")  # pragma: no cover


async def _call_anthropic(
    api_key: str, model: str, messages: List[dict],
    temperature: float, max_tokens: int,
) -> str:
    """Anthropic Messages API — system message is hoisted to top-level."""
    system_parts = [m["content"] for m in messages if m.get("role") == "system" and m.get("content")]
    convo = [m for m in messages if m.get("role") in ("user", "assistant")]
    if not convo:
        convo = [{"role": "user", "content": "Hello"}]

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": convo,
    }
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=PREMIUM_TIMEOUT_SECONDS) as client:
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await client.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
                if resp.status_code >= 400:
                    raise RuntimeError(f"Anthropic returned {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                blocks = data.get("content") or []
                parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
                return "\n".join(parts).strip()
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"Anthropic call failed after retries: {exc}") from exc
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("unreachable")  # pragma: no cover


async def _call_gemini(
    api_key: str, model: str, messages: List[dict],
    temperature: float, max_tokens: int,
) -> str:
    """Google Gemini generateContent — converts chat messages to contents array."""
    contents = []
    system_instruction = None
    for m in messages:
        role = m.get("role")
        text = m.get("content") or ""
        if role == "system":
            system_instruction = text
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": text}]})

    if not contents:
        contents.append({"role": "user", "parts": [{"text": "Hello"}]})

    body = {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=PREMIUM_TIMEOUT_SECONDS) as client:
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code >= 400:
                    raise RuntimeError(f"Gemini returned {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts") or []
                texts = [p.get("text", "") for p in parts if p.get("text")]
                return "\n".join(texts).strip()
            except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"Gemini call failed after retries: {exc}") from exc
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------------------
# Free edge router (legacy path)
# ---------------------------------------------------------------------------

async def call_edge_router(
    messages: Optional[List[dict]] = None,
    prompt: Optional[str] = None,
    temperature: float = 0.2,
    api_key: Optional[str] = None,
    max_tokens: int = 1000,
    response_mode: str = "json",
    model: Optional[str] = None,
    lang: Optional[str] = None,
) -> Any:
    """Forward a chat-completion request to the edge router.

    Kept for backward compatibility — :func:`call_llm` uses this internally.
    """
    edge_router_url = _edge_router_url()
    if not edge_router_url:
        raise RuntimeError("EDGE_ROUTER_URL not configured")
    if not messages and not prompt:
        raise ValueError("Either prompt or messages must be provided")
    if messages is None:
        messages = [
            {"role": "system", "content": "You are a strict JSON-outputting assistant. Reply only with valid JSON unless told otherwise."},
            {"role": "user", "content": prompt or ""},
        ]

    payload: dict[str, Any] = {
        "model": model or "cf-llama",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if lang:
        payload["lang"] = lang

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=EDGE_TIMEOUT_SECONDS) as client:
                resp = await client.post(f"{edge_router_url}/", json=payload, headers=headers)
                text = resp.text
                if resp.status_code >= 400:
                    logger.error("Edge router error %s (attempt %d): %s", resp.status_code, attempt + 1, text[:300])
                    if 400 <= resp.status_code < 500:
                        raise RuntimeError(f"Edge router rejected request ({resp.status_code}): {text[:300]}")
                    last_exc = RuntimeError(f"Edge router error {resp.status_code}: {text[:300]}")
                    continue
                return _shape(text, response_mode)
        except httpx.TimeoutException as exc:
            last_exc = exc
            logger.warning("Edge router timeout (attempt %d)", attempt + 1)
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning("Edge router HTTP error (attempt %d): %s", attempt + 1, exc)

    raise RuntimeError(f"Edge router unreachable after {MAX_RETRIES + 1} attempts: {last_exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shape(text: str, mode: str) -> Any:
    """Return either parsed JSON or raw text per ``response_mode``."""
    if mode == "raw":
        return text
    return _extract_json(text)


def _extract_json(text: str) -> Any:
    """Best-effort JSON extraction from a model response."""
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Empty model response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence = _FENCE_RE.search(text)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                continue
    logger.error("Model response not JSON: %s", text[:200])
    raise RuntimeError("Model response is not valid JSON")


def _local_stub(messages: List[dict], mode: str) -> Any:
    """Deterministic offline response for demo continuity.

    Used only when every upstream provider is unreachable and no premium
    key is configured. Echoes the last user message back in a structured
    shape that satisfies the caller's JSON contract.
    """
    last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    if mode == "raw":
        return f"[offline] I cannot reach any LLM provider right now. You said: {last_user[:200]}"
    return {
        "status": "offline_stub",
        "echoed_input": last_user[:300],
        "note": "All upstream LLM providers are unreachable. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY on the backend to enable premium routing, or restore the edge router URL.",
    }


__all__ = ["call_llm", "call_edge_router", "current_provider"]
