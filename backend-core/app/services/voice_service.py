"""Text-to-speech streaming with provider fallback chain.

Order of preference:
    1. Cloudflare Workers AI (English only) when USE_CF_WORKER_TTS=1.
    2. ElevenLabs (English only) when ELEVENLABS_KEYS is configured.
    3. OpenAI TTS (Bengali + English + mixed).

The first provider that yields audio wins. Failures bubble up so the caller
can surface them; ``stream_tts`` is responsible for the final decision on
which provider to try based on text content and ``lang`` hint.
"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_KEYS = [
    k.strip()
    for k in os.getenv("ELEVENLABS_KEYS", "").split(",")
    if k.strip()
]
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
EDGE_ROUTER_URL = os.getenv("EDGE_ROUTER_URL", "").rstrip("/")
USE_CF_WORKER_TTS = os.getenv("USE_CF_WORKER_TTS", "1").lower() in ("1", "true", "yes")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"
)


def _is_bengali(text: str) -> bool:
    if not text:
        return False
    return sum(1 for c in text if "\u0980" <= c <= "\u09FF") > 3


async def stream_worker_tts(text: str, lang: str = "en"):
    if not EDGE_ROUTER_URL:
        raise RuntimeError("EDGE_ROUTER_URL not configured for worker TTS")
    url = f"{EDGE_ROUTER_URL}/tts"
    payload = {"text": text, "lang": lang}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST", url, headers={"Content-Type": "application/json"}, json=payload
        ) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise RuntimeError(
                    f"Worker TTS failed {resp.status_code}: "
                    f"{body.decode(errors='replace')}"
                )
            async for chunk in resp.aiter_bytes():
                yield chunk


async def stream_openai_tts(text: str, lang: str = "en"):
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured for OpenAI TTS")
    # Bengali gets a voice with strong multilingual coverage.
    voice = "shimmer" if lang == "bn" or _is_bengali(text) else OPENAI_TTS_VOICE
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {"model": OPENAI_TTS_MODEL, "voice": voice, "input": text}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, headers=headers, json=body) as resp:
            if resp.status_code >= 400:
                body_text = await resp.aread()
                raise RuntimeError(
                    f"OpenAI TTS failed {resp.status_code}: "
                    f"{body_text.decode(errors='replace')}"
                )
            async for chunk in resp.aiter_bytes():
                yield chunk


async def stream_elevenlabs_tts(text: str, voice_id: str = ELEVENLABS_VOICE_ID):
    last_exc: Exception | None = None
    for key in ELEVENLABS_KEYS:
        try:
            headers = {"xi-api-key": key, "Accept": "audio/mpeg"}
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", url, headers=headers, json={"text": text}
                ) as resp:
                    if resp.status_code in (401, 402, 403, 429):
                        last_exc = RuntimeError(f"Key rejected: {resp.status_code}")
                        continue
                    if resp.status_code >= 400:
                        last_exc = RuntimeError(
                            f"ElevenLabs error: {resp.status_code}"
                        )
                        continue
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                    return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            continue
    raise last_exc or RuntimeError("No ElevenLabs keys available")


async def stream_tts(text: str, voice_id: str = ELEVENLABS_VOICE_ID, lang: str = "en"):
    """Pick the best provider for ``text`` + ``lang``.

    Bengali / mixed-script text skips English-only providers and goes straight
    to OpenAI TTS which has proven multilingual coverage.
    """
    last_exc: Exception | None = None
    contains_bengali = lang == "bn" or _is_bengali(text)

    if not contains_bengali and USE_CF_WORKER_TTS and EDGE_ROUTER_URL:
        try:
            async for chunk in stream_worker_tts(text, lang="en"):
                yield chunk
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc

    if not contains_bengali and ELEVENLABS_KEYS:
        try:
            async for chunk in stream_elevenlabs_tts(text, voice_id):
                yield chunk
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc

    if OPENAI_KEY:
        try:
            async for chunk in stream_openai_tts(text, lang=lang):
                yield chunk
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc

    raise last_exc or RuntimeError("No TTS provider available")