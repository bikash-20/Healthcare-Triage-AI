"""OCR helpers built on top of Google Cloud Vision.

The module is safe to import even when no Google credentials are present —
``extract_text_from_image`` only fails when actually called. ``init_client`` is
lazy so unit tests can import the module without a service-account file.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("ocr_service")

_client = None


def init_client():
    """Lazy-init the Cloud Vision client. Returns the cached instance."""
    global _client
    if _client is None:
        try:
            from google.cloud import vision  # type: ignore

            _client = vision.ImageAnnotatorClient()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to init Google Cloud Vision client: %s", exc)
            raise
    return _client


def extract_text_from_image(path: str) -> str:
    from google.cloud import vision  # type: ignore

    client = init_client()
    with open(path, "rb") as fh:
        content = fh.read()
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    if getattr(response.error, "message", None):
        raise RuntimeError(response.error.message)
    return response.full_text_annotation.text or ""


# --- Regex patterns for common clinical fields ----------------------------
_VITAL_PATTERNS = {
    "bp": r"(?:bp|blood\s*pressure|রক্ত\s*চাপ)[:\s]*([0-9]{2,3}\s*[/\-]\s*[0-9]{2,3})",
    "spo2": r"(?:spo2|sp[o0]2|oxygen(?:\s*sat(?:uration)?)?|অক্সিজেন)[:\s]*([0-9]{2,3})\s*%?",
    "temp": r"(?:temp(?:erature)?|জ্বর|তাপমাত্রা)[:\s]*([0-9]{2,3}(?:\.[0-9])?)",
    "hr": r"(?:hr|heart\s*rate|pulse|হৃদস্পন্দন|নাড়ি)[:\s]*([0-9]{2,3})",
    "glucose": r"(?:glucose|blood\s*sugar|গ্লুকোজ|চিনি)[:\s]*([0-9]{2,4})",
}


def extract_vitals_from_text(raw_text: str) -> dict:
    """Pull BP / SpO₂ / temp / HR / glucose out of free-form text."""
    if not raw_text:
        return {}

    text = raw_text.lower()
    found: dict[str, str] = {}

    for key, pattern in _VITAL_PATTERNS.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = match.group(1).replace(" ", "").replace("-", "/")
            found[key] = value

    # Fallback: if no explicit BP label, look for a bare systolic/diastolic pair.
    if "bp" not in found:
        bare = re.search(r"([0-9]{2,3})\s*[/\-]\s*([0-9]{2,3})", text)
        if bare:
            found["bp"] = f"{bare.group(1)}/{bare.group(2)}"

    return found


def parse_medical_text(raw_text: str) -> dict:
    """Lightweight wrapper: always returns ``raw_text`` plus ``auto_fill``."""
    return {
        "raw_text": raw_text or "",
        "auto_fill": extract_vitals_from_text(raw_text or ""),
    }
