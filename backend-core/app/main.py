"""FastAPI application for the rural-health-triage backend.

This module exposes the patient-facing endpoints (vitals, audio, OCR, triage,
dose, chat, TTS). It is intentionally framework-light: dependencies are wired
through `create_app()` so tests can override them with `monkeypatch`.

Bilingual design
----------------
Every endpoint accepts an optional ``lang`` field (``"en"`` or ``"bn"``). When
the caller omits it we infer from the most recent user message / OCR text.
LLM prompts are sent with the chosen language so responses come back in the
right script; downstream payload keys stay English to keep clients
interoperable, but human-readable strings can be localized via
``app.translations.t``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai import AsyncOpenAI

from . import formulary, llm_client
from .llm_client import current_provider as _current_provider
from .ml_engine import analyze_vitals
from .schemas import (
    AudioIntakeResponse,
    ChatRequest,
    DoseRequest,
    OCRParseRequest,
    OCRParseResult,
    TriageRequest,
    TriageResponse,
    VitalsRequest,
)
from .services.ocr_service import extract_text_from_image, parse_medical_text
from .services.voice_service import stream_tts
from .translations import detect_language, t

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
EDGE_ROUTER_URL = os.getenv("EDGE_ROUTER_URL", "")

logger = logging.getLogger("backend")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

_openai_client: AsyncOpenAI | None = None

# Log provider tier once at import time — visible in Render deploy logs.
_tier_info = _current_provider()
logger.info(
    "LLM provider tier=%s provider=%s model=%s via=%s",
    _tier_info.get("tier"),
    _tier_info.get("provider"),
    _tier_info.get("model"),
    _tier_info.get("via"),
)


def _get_openai() -> AsyncOpenAI | None:
    """Return a cached AsyncOpenAI client, or None when no key is configured."""
    global _openai_client
    if not OPENAI_KEY:
        return None
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=OPENAI_KEY)
    return _openai_client


async def _save_upload(file: UploadFile) -> tuple[Path, bytes]:
    """Persist an UploadFile to a unique temp path. Caller is responsible for cleanup."""
    suffix = Path(file.filename or "").suffix or ".bin"
    fd, path_str = tempfile.mkstemp(suffix=suffix)
    path = Path(path_str)
    content = await file.read()
    with os.fdopen(fd, "wb") as fh:
        fh.write(content)
    return path, content


def _format_summary_en(r: dict) -> str:
    """Human-readable one-paragraph dose summary in English."""
    parts = [
        f"{r['display_en']}: give {r['formatted_dose_en']} per dose, "
        f"{r['freq_per_day']} times per day (every {r['interval_hours']} hours) "
        f"via {r['route']}."
    ]
    if r.get("notes"):
        parts.append(r["notes"])
    if r["warnings"]:
        parts.append("Warnings: " + "; ".join(r["warnings"]))
    if r["is_dangerous"]:
        parts.append("⚠ DO NOT ADMINISTER without prescriber review.")
    return " ".join(parts)


def _format_summary_bn(r: dict) -> str:
    """Human-readable one-paragraph dose summary in Bengali."""
    parts = [
        f"{r['display_bn']}: প্রতি ডোজে {r['formatted_dose_en']} দিন, "
        f"দিনে {r['freq_per_day']} বার ({r['interval_hours']} ঘণ্টা অন্তর), "
        f"{r['route']}।"
    ]
    if r.get("notes"):
        parts.append(r["notes"])
    if r["warnings"]:
        parts.append("সতর্কতা: " + "; ".join(r["warnings"]))
    if r["is_dangerous"]:
        parts.append("⚠ প্রেসক্রাইবারের অনুমোদন ছাড়া দেবেন না।")
    return " ".join(parts)


def create_app() -> FastAPI:
    app = FastAPI(title="Rural Health Triage API", version="1.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # ---------------------------------------------------------------- health
    @app.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "rural-health-triage-backend",
            "edge_router_configured": bool(EDGE_ROUTER_URL),
            "openai_configured": bool(OPENAI_KEY),
            "supported_languages": ["en", "bn"],
            "provider": _current_provider(),
        }

    # ------------------------------------------------------ provider status
    @app.get("/api/provider-status")
    async def provider_status() -> dict:
        """Tell operators which LLM tier is active and how to upgrade.

        No secrets are returned — only the provider name and model.
        """
        info = _current_provider()
        upgrade_hint = (
            "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or "
            "GROQ_API_KEY in the backend environment to enable premium routing. "
            "OpenAI wins first, then Anthropic, Gemini, Groq."
        )
        return {
            **info,
            "upgrade_hint": upgrade_hint,
            "supported_premium_providers": ["openai", "anthropic", "gemini", "groq"],
        }

    # ----------------------------------------------------------------- audio
    @app.post("/api/audio/intake", response_model=AudioIntakeResponse)
    async def audio_intake(file: UploadFile = File(...)) -> AudioIntakeResponse | JSONResponse:
        path, _content = await _save_upload(file)

        try:
            client = _get_openai()
            text = ""
            if client is not None:
                with open(path, "rb") as fh:
                    transcript = await client.audio.transcriptions.create(
                        file=fh, model="whisper-1", response_format="json"
                    )
                text = getattr(transcript, "text", "") or ""
            else:
                logger.warning("OPENAI_API_KEY missing — returning empty transcript")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Audio transcription failed")
            return JSONResponse(
                {"error": "transcription_failed", "detail": str(exc)},
                status_code=500,
            )
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

        lang = detect_language(text, default="en")
        normalized = text

        # If user spoke Bengali, normalize via Google Translate for downstream LLM.
        if lang == "bn":
            try:
                from google.cloud import translate_v2 as translate

                translated = translate.Client().translate(text, target_language="en")
                normalized = translated["translatedText"]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google Translate unavailable: %s — using raw text", exc)

        return AudioIntakeResponse(
            raw_text=text,
            normalized=normalized,
            lang=lang,
            detected_language=lang,
        )

    # ------------------------------------------------------------------- ocr
    @app.post("/api/ocr/upload", response_model=None)
    async def ocr_upload(file: UploadFile = File(...)):
        path, _content = await _save_upload(file)
        try:
            try:
                raw = extract_text_from_image(str(path))
            except Exception as exc:  # noqa: BLE001
                logger.exception("OCR text extraction failed")
                return JSONResponse(
                    {"error": "ocr_failed", "detail": str(exc)},
                    status_code=500,
                )

            auto_fill = parse_medical_text(raw)["auto_fill"]
            detected = detect_language(raw, default="en")

            prompt = (
                "You are a clinical NLP assistant. Extract medications, dosages, "
                "diagnoses, and lab results from the following medical text. "
                f"Reply with JSON matching this schema:\n{OCRParseResult.model_json_schema()}\n\n"
                f"Text:\n{raw}"
            )
            try:
                parsed = await llm_client.call_llm(
                    prompt, temperature=0.0, max_tokens=800, lang=detected,
                )
                result = OCRParseResult(**parsed, raw_text=raw)
            except Exception as exc:  # noqa: BLE001
                logger.exception("OCR parse via LLM failed; returning regex-only result")
                # Graceful fallback: regex-only payload so the UI still works.
                return {
                    "medications": [],
                    "diagnoses": [],
                    "labs": [],
                    "raw_text": raw,
                    "auto_fill": auto_fill,
                    "lang": detected,
                    "warning": f"LLM parse unavailable: {exc}",
                }

            payload = result.model_dump()
            payload["auto_fill"] = auto_fill
            payload["lang"] = detected
            return payload
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    @app.post("/api/ocr/parse")
    async def ocr_parse(payload: OCRParseRequest) -> dict:
        prompt = (
            "Extract medications, dosages, diagnoses, and lab results. "
            f"Return JSON matching schema:\n{OCRParseResult.model_json_schema()}\n\n"
            f"Text:\n{payload.raw_text}"
        )
        parsed = await llm_client.call_llm(
            prompt, temperature=0.0, max_tokens=800, lang=payload.lang,
        )
        result = OCRParseResult(**parsed, raw_text=payload.raw_text)
        out = result.model_dump()
        out["lang"] = payload.lang
        return out

    # ----------------------------------------------------------------- triage
    @app.post("/api/triage")
    async def triage_endpoint(payload: TriageRequest) -> dict:
        lang = payload.lang or detect_language(payload.normalized_text)
        prompt = (
            "You are a clinical decision support assistant for rural community "
            "health workers in Bangladesh. Produce STRICT JSON matching this "
            f"schema: {TriageResponse.model_json_schema()}\n\n"
            f"Patient language: {lang}. Reply with clinical_reasoning in that language.\n\n"
            f"Normalized symptoms:\n{payload.normalized_text}\n\n"
            f"Vitals anomaly:\n{payload.vitals_anomaly}\n\n"
            f"Medication/history:\n{payload.history}\n\n"
            "If vitals indicate a red alert, triage_severity must be 'Red' or 'Black'. "
            "Return only JSON."
        )
        parsed = await llm_client.call_llm(
            prompt, temperature=0.0, max_tokens=800, lang=lang,
        )
        triage = TriageResponse(**parsed)
        out = triage.model_dump()
        out["lang"] = lang
        return out

    # ------------------------------------------------------------------- dose
    @app.post("/api/dose")
    async def dose_endpoint(payload: DoseRequest) -> dict:
        lang = payload.lang or detect_language(payload.medication)

        # 1) Try the hand-curated formulary first — deterministic, can't hallucinate.
        formulary_result = formulary.calculate_dose(
            payload.medication, payload.age, payload.weight, lang=lang,
        )
        if formulary_result is not None:
            logger.info(
                "dose formulary hit medication=%s key=%s age=%s weight=%s",
                payload.medication, formulary_result["matched_key"],
                payload.age, payload.weight,
            )
            return {
                "source": "formulary",
                "matched_drug_key": formulary_result["matched_key"],
                "display_name": formulary_result["display_name_used"],
                "category": formulary_result["category"],
                "dose_per_kg": (
                    f"{formulary_result['computed_via']}"
                ),
                "total_dose": formulary_result["formatted_dose_en"],
                "frequency": (
                    f"{formulary_result['freq_per_day']}x/day, every "
                    f"{formulary_result['interval_hours']}h"
                ),
                "route": formulary_result["route"],
                "is_dangerous": formulary_result["is_dangerous"],
                "warnings": formulary_result["warnings"],
                "summary_en": _format_summary_en(formulary_result),
                "summary_bn": _format_summary_bn(formulary_result),
                "lang": lang,
                "formulary_dose_mg": formulary_result["dose_mg_per_dose"],
                "formulary_max_daily_mg": formulary_result["max_daily_mg"],
                "formulary_age_rule_used": formulary_result["age_rule_used"],
                "notes": formulary_result["notes"],
            }

        # 2) Fallback to LLM for drugs not in the formulary.
        logger.info(
            "dose formulary miss medication=%s — falling back to LLM",
            payload.medication,
        )
        prompt = (
            "You are a clinical pharmacist AI for rural health workers in Bangladesh. "
            "Calculate the safe medication dose based on patient age and weight. "
            "Return ONLY valid JSON with these exact fields:\n"
            "{\n"
            '  "summary_en": "Full dose instructions in English",\n'
            '  "summary_bn": "Full dose instructions in Bengali using real Bengali '
            "Unicode characters like রোগী NOT escape sequences\",\n"
            '  "dose_per_kg": "e.g. 15mg/kg",\n'
            '  "total_dose": "e.g. 300mg",\n'
            '  "frequency": "e.g. Every 6 hours",\n'
            '  "route": "e.g. Oral",\n'
            '  "is_dangerous": true or false,\n'
            '  "warning_en": "Warning in English if dangerous, else null",\n'
            '  "warning_bn": "Warning in Bengali using real Unicode characters if '
            "dangerous, else null\"\n}\n\n"
            f"Medication: {payload.medication}\n"
            f"Patient age: {payload.age} years\n"
            f"Patient weight: {payload.weight} kg\n"
            f"Reply language: {lang}\n\n"
            "CRITICAL: Bengali text must use real Unicode Bengali characters "
            "(অ আ ক খ etc), never escape sequences. Return only JSON."
        )
        parsed = await llm_client.call_llm(
            prompt, temperature=0.0, max_tokens=600, lang=lang,
        )
        if isinstance(parsed, dict):
            parsed.setdefault("lang", lang)
            parsed.setdefault("source", "llm")
        return parsed

    # ----------------------------------------------------------- /api/formulary
    @app.get("/api/formulary")
    async def formulary_endpoint() -> dict:
        """Inspect the hand-curated drug formulary (no secrets, no LLM calls)."""
        drugs = formulary.list_drugs()
        return {
            "count": formulary.drug_count(),
            "categories": formulary.list_categories(),
            "drugs": drugs,
        }

    @app.get("/api/formulary/{drug_key}")
    async def formulary_drug_endpoint(drug_key: str) -> dict:
        """Inspect one drug entry."""
        entry = formulary.lookup(drug_key)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Drug '{drug_key}' not in formulary")
        return {
            "key": entry.key,
            "display_en": entry.display_en,
            "display_bn": entry.display_bn,
            "category": entry.category,
            "aliases": list(entry.aliases),
            "adult_rule": entry.adult_rule.__dict__,
            "pediatric_rule": (
                entry.pediatric_rule.__dict__ if entry.pediatric_rule else None
            ),
            "notes_en": entry.notes_en,
            "notes_bn": entry.notes_bn,
        }

    # ----------------------------------------------------------------- vitals
    @app.post("/api/vitals")
    async def vitals_endpoint(payload: VitalsRequest) -> dict:
        return analyze_vitals(payload.model_dump())

    # ------------------------------------------------------------------- chat
    @app.post("/api/chat")
    async def chat_endpoint(payload: ChatRequest) -> dict:
        if not payload.messages:
            raise HTTPException(status_code=400, detail="messages list is required")

        vitals_context = payload.vitals or {}
        triage_context = payload.triage or {}
        last_user = next(
            (m.content for m in reversed(payload.messages) if m.role == "user"),
            "",
        )
        lang = payload.lang or detect_language(last_user)

        def render_context() -> str:
            return "\n".join(
                [
                    "Patient vitals data:",
                    f"Blood Pressure: {vitals_context.get('bp', 'unknown')}",
                    f"Heart Rate: {vitals_context.get('hr', 'unknown')}",
                    f"Temperature: {vitals_context.get('temp', 'unknown')}",
                    f"SpO2: {vitals_context.get('spo2', 'unknown')}",
                    f"Blood Glucose: {vitals_context.get('glucose', 'unknown')}",
                    "",
                    f"Current triage severity: {triage_context.get('triage_severity', 'unknown')}",
                    f"Clinical reasoning: {triage_context.get('clinical_reasoning', 'unknown')}",
                    "",
                    "Answer as NEXORA, a medical AI expert. Provide patient-specific "
                    "medical advice, speak in the user's language, and do not invent findings.",
                ]
            )

        system_prompt = (
            "You are NEXORA, a highly qualified medical consultant for rural "
            "healthcare workers. Silently use the patient vitals and triage context "
            "to answer the user question with clinical caution. If the user asks in "
            "Bengali, reply in Bengali. If the user asks in English, reply in English. "
            f"User language hint: {lang}. Always stay concise, factual, and supportive.\n\n"
            f"{render_context()}"
        )

        model = payload.model or "cf-llama"
        messages = [{"role": "system", "content": system_prompt}] + [
            m.model_dump() for m in payload.messages
        ]
        text = await llm_client.call_llm(
            messages=messages,
            response_mode="raw",
            temperature=0.6,
            max_tokens=900,
            api_key=payload.api_key,
            model=model,
            lang=lang,
        )
        return {
            "assistant": text,
            "language": detect_language(text),
            "model": model,
        }

    # -------------------------------------------------------------------- tts
    @app.get("/api/tts/stream")
    async def tts_stream(q: str = "Summary not provided", lang: str = "en"):
        text = (q or "").strip()
        if not text:
            raise HTTPException(
                status_code=400,
                detail=t("error.required_fields", detect_language(q, default=lang)),
            )

        async def streamer():
            try:
                async for chunk in stream_tts(text, lang=lang):
                    yield chunk
            except Exception as exc:  # noqa: BLE001
                logger.exception("TTS stream failed")
                # Yield a JSON error trailer so the client knows.
                yield f'{{"error":"tts_failed","detail":"{exc}"}}'.encode("utf-8")

        return StreamingResponse(streamer(), media_type="audio/mpeg")

    return app


__all__ = ["create_app"]