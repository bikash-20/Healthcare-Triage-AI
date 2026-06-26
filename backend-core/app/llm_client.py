"""Robust client for the Cloudflare Edge Router proxy.

Features:
    * Async httpx with retries (exponential back-off) on transient failures.
    * Bounded JSON recovery (strip markdown fences, locate first JSON object).
    * Honest error reporting — never silently swallow upstream failures.
    * Optional language hint forwarded to the worker for bilingual prompts.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, List, Optional

import httpx

logger = logging.getLogger("llm_client")

EDGE_ROUTER_URL = os.getenv("EDGE_ROUTER_URL", "").rstrip("/")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

# Tight request budget: edge worker is supposed to be sub-second; cap retries.
_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


async def call_edge_router(
    prompt: Optional[str] = None,
    messages: Optional[List[dict]] = None,
    temperature: float = 0.2,
    api_key: Optional[str] = None,
    max_tokens: int = 1000,
    response_mode: str = "json",
    model: Optional[str] = None,
    lang: Optional[str] = None,
) -> Any:
    """Forward a chat-completion request to the edge router.

    Args:
        prompt: Single-shot user prompt (ignored when messages is provided).
        messages: Pre-built chat messages list.
        temperature: Sampling temperature.
        api_key: Optional caller-supplied key (forwarded as ``x-api-key``).
        max_tokens: Hard cap on response tokens.
        response_mode: ``"json"`` parses the body as JSON; ``"raw"`` returns text.
        model: Edge-model alias (``cf-llama``, ``cf-claude``, etc.) or full id.
        lang: Optional language hint (``"en"`` or ``"bn"``) passed to the worker.
    """
    if not EDGE_ROUTER_URL:
        raise RuntimeError("EDGE_ROUTER_URL not configured")

    if not messages and not prompt:
        raise ValueError("Either prompt or messages must be provided")

    if messages is None:
        messages = [
            {
                "role": "system",
                "content": "You are a strict JSON-outputting assistant. Reply only with valid JSON unless told otherwise.",
            },
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
    elif OPENAI_KEY:
        headers["x-api-key"] = OPENAI_KEY

    logger.debug(
        "Calling edge router %s model=%s messages=%d", EDGE_ROUTER_URL, payload["model"], len(messages)
    )

    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{EDGE_ROUTER_URL}/", json=payload, headers=headers
                )
                text = resp.text
                if resp.status_code >= 400:
                    logger.error(
                        "Edge router error %s (attempt %d): %s",
                        resp.status_code,
                        attempt + 1,
                        text[:300],
                    )
                    # Don't retry on 4xx — caller error
                    if 400 <= resp.status_code < 500:
                        raise RuntimeError(
                            f"Edge router rejected request ({resp.status_code}): {text[:300]}"
                        )
                    last_exc = RuntimeError(
                        f"Edge router error {resp.status_code}: {text[:300]}"
                    )
                    continue

                if response_mode == "raw":
                    return text
                return _extract_json(text)

        except httpx.TimeoutException as exc:
            last_exc = exc
            logger.warning("Edge router timeout (attempt %d)", attempt + 1)
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning("Edge router HTTP error (attempt %d): %s", attempt + 1, exc)

    raise RuntimeError(f"Edge router unreachable after {_MAX_RETRIES + 1} attempts: {last_exc}")


def _extract_json(text: str) -> Any:
    """Best-effort JSON extraction from a model response."""
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Empty model response")

    # Fast path: well-formed JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try fenced code blocks.
    fence = _FENCE_RE.search(text)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    # Try to locate the first balanced JSON object/array.
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