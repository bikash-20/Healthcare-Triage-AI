"""End-to-end tests for the rural-health-triage backend.

These exercise the FastAPI app via httpx.AsyncClient + ASGI transport, so no
network is required. LLM calls are stubbed via monkeypatch on
``backend_app.llm_client.call_llm``.
"""
import importlib
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_app():
    """Import the app package fresh (reset module cache between tests)."""
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]
    return importlib.import_module("app")


@pytest.mark.asyncio
async def test_vitals_endpoint():
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"bp": "120/80", "hr": 72, "temp": 98.6, "spo2": 98, "glucose": 110}
        r = await ac.post("/api/vitals", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "level" in data
        assert data["level"] == "green"
        assert data["alerts"] == []


@pytest.mark.asyncio
async def test_vitals_red_alerts():
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"bp": "200/130", "hr": 150, "temp": 105.0, "spo2": 85, "glucose": 350}
        r = await ac.post("/api/vitals", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["level"] == "red"
        assert len(data["alerts"]) >= 3


@pytest.mark.asyncio
async def test_health():
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "bn" in body["supported_languages"]


@pytest.mark.asyncio
async def test_ocr_parse(monkeypatch):
    async def fake_call(prompt, temperature=0.2, api_key=None, max_tokens=1000, **_kw):
        return {
            "medications": [{"name": "Paracetamol", "dosage": "500mg", "frequency": "1+0+1", "route": "oral"}],
            "diagnoses": ["Fever"],
            "labs": [{"test_name": "WBC", "value": 7.5, "units": "10^3/uL"}],
        }

    backend_app = _load_app()
    monkeypatch.setattr(backend_app.llm_client, "call_llm", fake_call)
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/ocr/parse", json={"raw_text": "Paracetamol 500mg 1+0+1\nWBC:7.5"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "medications" in data
        assert data["medications"][0]["name"] == "Paracetamol"


@pytest.mark.asyncio
async def test_triage_endpoint(monkeypatch):
    async def fake_call(prompt, temperature=0.0, api_key=None, max_tokens=800, **_kw):
        return {
            "triage_severity": "Green",
            "clinical_reasoning": "Symptoms mild",
            "differential_diagnoses": ["Viral fever"],
            "immediate_recommendations": ["Rest", "Oral fluids"],
            "referral_urgency": "Low",
        }

    backend_app = _load_app()
    monkeypatch.setattr(backend_app.llm_client, "call_llm", fake_call)
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "normalized_text": "Patient with cough and mild fever",
            "vitals_anomaly": {"level": "green", "alerts": []},
            "history": {"medications": []},
            "lang": "en",
        }
        r = await ac.post("/api/triage", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["triage_severity"] == "Green"
        assert data["lang"] == "en"


@pytest.mark.asyncio
async def test_triage_validation_error():
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Missing required `vitals_anomaly`
        r = await ac.post("/api/triage", json={"normalized_text": "x"})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_dose_validation_error():
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Negative weight is invalid
        r = await ac.post("/api/dose", json={"medication": "X", "age": 5, "weight": -1})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_chat_validation_error():
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Empty messages
        r = await ac.post("/api/chat", json={"messages": []})
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_tts_empty_query():
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/tts/stream?q=")
        assert r.status_code == 400
