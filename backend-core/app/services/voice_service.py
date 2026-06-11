import os
import httpx
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_KEYS = os.getenv('ELEVENLABS_KEYS', '').split(',') if os.getenv('ELEVENLABS_KEYS') else []
OPENAI_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_TTS_MODEL = os.getenv('OPENAI_TTS_MODEL', 'gpt-4o-mini-tts')
EDGE_ROUTER_URL = os.getenv('EDGE_ROUTER_URL', '')
USE_CF_WORKER_TTS = os.getenv('USE_CF_WORKER_TTS', '1').lower() in ('1', 'true', 'yes')


async def stream_worker_tts(text: str, model: str | None = None):
    if not EDGE_ROUTER_URL:
        raise RuntimeError('EDGE_ROUTER_URL not configured for worker TTS')
    url = EDGE_ROUTER_URL.rstrip('/') + '/tts'
    payload = {'text': text}
    if model:
        payload['model'] = model
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream('POST', url, headers={'Content-Type': 'application/json'}, json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise RuntimeError(f'Worker TTS failed {resp.status_code}: {body.decode(errors="replace")}')
            async for chunk in resp.aiter_bytes():
                yield chunk


async def stream_openai_tts(text: str, model: str = OPENAI_TTS_MODEL):
    if not OPENAI_KEY:
        raise RuntimeError('OPENAI_API_KEY not configured for OpenAI TTS')
    url = 'https://api.openai.com/v1/audio/speech'
    headers = {
        'Authorization': f'Bearer {OPENAI_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'audio/mpeg'
    }
    body = {
        'model': model,
        'voice': 'shimmer',  # better for Bengali and mixed scripts
        'input': text
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream('POST', url, headers=headers, json=body) as resp:
            if resp.status_code >= 400:
                body_text = await resp.aread()
                raise RuntimeError(f'OpenAI TTS failed {resp.status_code}: {body_text.decode(errors="replace")}')
            async for chunk in resp.aiter_bytes():
                yield chunk


async def stream_elevenlabs_tts(text: str, voice_id: str = '21m00Tcm4TlvDq8ikWAM'):
    last_exc = None
    for key in ELEVENLABS_KEYS:
        if not key:
            continue
        try:
            headers = {'xi-api-key': key, 'Accept': 'audio/mpeg'}
            url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream'
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream('POST', url, headers=headers, json={'text': text}) as resp:
                    if resp.status_code in (401, 403, 429, 402):
                        last_exc = Exception(f'Key rejected: {resp.status_code}')
                        continue
                    if resp.status_code >= 400:
                        last_exc = Exception(f'ElevenLabs error: {resp.status_code}')
                        continue
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                    return
        except Exception as e:
            last_exc = e
            continue
    raise last_exc or Exception('No ElevenLabs keys available')


# ✅ NEW: detects Bengali characters in text
def _is_bengali(text: str) -> bool:
    bengali_chars = sum(1 for c in text if '\u0980' <= c <= '\u09FF')
    return bengali_chars > 3


async def stream_tts(text: str, voice_id: str = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')):
    last_exc = None
    contains_bengali = _is_bengali(text)

    # English only → try CF Worker first, then ElevenLabs
    if not contains_bengali and USE_CF_WORKER_TTS and EDGE_ROUTER_URL:
        try:
            async for chunk in stream_worker_tts(text):
                yield chunk
            return
        except Exception as e:
            last_exc = e

    if not contains_bengali and ELEVENLABS_KEYS:
        try:
            async for chunk in stream_elevenlabs_tts(text, voice_id):
                yield chunk
            return
        except Exception as e:
            last_exc = e

    # Bengali or mixed → goes straight here
    # English also falls here if CF Worker and ElevenLabs both failed
    if OPENAI_KEY:
        try:
            async for chunk in stream_openai_tts(text):
                yield chunk
            return
        except Exception as e:
            last_exc = e

    raise last_exc or Exception('No TTS provider available')