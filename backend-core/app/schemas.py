"""Pydantic request/response schemas for the rural-health-triage API."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------
class Medication(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None


class LabResult(BaseModel):
    test_name: str
    value: Optional[float] = None
    units: Optional[str] = None


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------
class OCRParseResult(BaseModel):
    medications: List[Medication] = []
    diagnoses: List[str] = []
    labs: List[LabResult] = []
    raw_text: Optional[str] = None


class OCRParseRequest(BaseModel):
    raw_text: str = Field(..., min_length=1)
    lang: Optional[Literal["en", "bn"]] = "en"


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------
TriageSeverity = Literal["Green", "Yellow", "Red", "Black"]


class TriageRequest(BaseModel):
    normalized_text: str = Field(..., min_length=1)
    vitals_anomaly: dict
    history: dict = Field(default_factory=dict)
    lang: Optional[Literal["en", "bn"]] = "en"

    @field_validator("vitals_anomaly")
    @classmethod
    def _has_level(cls, v: dict) -> dict:
        # Ensure downstream LLM prompt gets a level field even when UI sends none.
        v.setdefault("level", "green")
        v.setdefault("alerts", [])
        return v


class TriageResponse(BaseModel):
    triage_severity: str = Field(..., description="One of Green/Yellow/Red/Black")
    clinical_reasoning: str
    differential_diagnoses: List[str] = []
    immediate_recommendations: List[str] = []
    referral_urgency: str


# ---------------------------------------------------------------------------
# Dose calculator
# ---------------------------------------------------------------------------
class DoseRequest(BaseModel):
    medication: str = Field(..., min_length=1)
    age: float = Field(..., ge=0, le=120)
    weight: float = Field(..., gt=0, le=400)
    lang: Optional[Literal["en", "bn"]] = "en"


# ---------------------------------------------------------------------------
# Vitals
# ---------------------------------------------------------------------------
class VitalsRequest(BaseModel):
    bp: Optional[str] = None
    hr: Optional[float] = None
    temp: Optional[float] = None
    spo2: Optional[float] = None
    glucose: Optional[float] = None


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1)
    vitals: Optional[dict] = None
    triage: Optional[dict] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    lang: Optional[Literal["en", "bn"]] = "en"


# ---------------------------------------------------------------------------
# Audio intake response
# ---------------------------------------------------------------------------
class AudioIntakeResponse(BaseModel):
    raw_text: str
    normalized: str
    lang: str
    detected_language: str
