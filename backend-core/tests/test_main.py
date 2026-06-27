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


# ---------------------------------------------------------------------------
# Formulary module tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_formulary_list_endpoint_has_80_plus_drugs():
    """GET /api/formulary returns the full drug list — at least 80 WHO/BD entries."""
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/formulary")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 80, f"Expected >= 80 drugs, got {data['count']}"
        assert "drugs" in data and len(data["drugs"]) == data["count"]
        assert "categories" in data and len(data["categories"]) >= 10
        # Spot-check paracetamol present
        keys = {d["key"] for d in data["drugs"]}
        assert "paracetamol" in keys
        assert "amoxicillin" in keys


@pytest.mark.asyncio
async def test_formulary_inspect_endpoint():
    """GET /api/formulary/paracetamol returns full pediatric + adult rules."""
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/formulary/paracetamol")
        assert r.status_code == 200
        d = r.json()
        assert d["key"] == "paracetamol"
        assert "Pediatric" in d["display_en"] or "Acetaminophen" in d["display_en"]
        assert d["pediatric_rule"] is not None
        assert d["pediatric_rule"]["mg_per_kg_per_dose"] == 15
        assert d["adult_rule"]["fixed_mg_per_dose"] == 500


@pytest.mark.asyncio
async def test_formulary_inspect_404():
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/formulary/xyz_not_a_real_drug")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_dose_formulary_hit_paracetamol_pediatric():
    """5yo, 18kg → 270 mg paracetamol from pediatric rule (15 mg/kg)."""
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/dose", json={
            "medication": "Paracetamol",
            "age": 5,
            "weight": 18,
            "lang": "en",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "formulary"
        assert data["matched_drug_key"] == "paracetamol"
        assert data["formulary_dose_mg"] == 270.0
        assert data["formulary_age_rule_used"] == "pediatric"
        assert data["is_dangerous"] is False


@pytest.mark.asyncio
async def test_dose_formulary_alias_resolution():
    """Acetaminophen alias resolves to paracetamol."""
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/dose", json={
            "medication": "Acetaminophen",
            "age": 7,
            "weight": 22,
            "lang": "en",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "formulary"
        assert data["matched_drug_key"] == "paracetamol"


@pytest.mark.asyncio
async def test_dose_formulary_age_guardrail():
    """3yo given aspirin (min_age 12y) → is_dangerous=True."""
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/dose", json={
            "medication": "Aspirin",
            "age": 3,
            "weight": 14,
            "lang": "en",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "formulary"
        assert data["is_dangerous"] is True
        assert any("below the minimum age" in w for w in data["warnings"])


@pytest.mark.asyncio
async def test_dose_formulary_bangla_display():
    """lang=bn returns Bangla display_name + warnings."""
    backend_app = _load_app()
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/dose", json={
            "medication": "Paracetamol",
            "age": 5,
            "weight": 18,
            "lang": "bn",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "formulary"
        # display_name should contain Bangla characters
        assert any(ord(c) > 0x0980 for c in data["display_name"]), data["display_name"]
        # At least one warning in Bangla
        assert any(any(ord(c) > 0x0980 for c in w) for w in data["warnings"])


@pytest.mark.asyncio
async def test_dose_formulary_miss_falls_back_to_llm(monkeypatch):
    """Unknown drug triggers LLM fallback; result is stamped source='llm'."""
    backend_app = _load_app()
    async def _fake_llm(*args, **kwargs):
        return {
            "summary_en": "fake",
            "summary_bn": "ভুয়া",
            "dose_per_kg": "1mg/kg",
            "total_dose": "10mg",
            "frequency": "Once",
            "route": "Oral",
            "is_dangerous": False,
            "warning_en": None,
            "warning_bn": None,
        }
    monkeypatch.setattr(backend_app.llm_client, "call_llm", _fake_llm)
    transport = ASGITransport(app=backend_app.create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/dose", json={
            "medication": "Unobtainium-3000",
            "age": 30,
            "weight": 70,
            "lang": "en",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "llm"
        assert data["summary_en"] == "fake"


@pytest.mark.asyncio
async def test_formulary_lookup_helper():
    """Unit test the formulary module lookup() directly."""
    backend_app = _load_app()
    f = backend_app.formulary
    # Exact key
    assert f.lookup("paracetamol").key == "paracetamol"
    # Display name (case-insensitive)
    assert f.lookup("PARACETAMOL").key == "paracetamol"
    # Alias
    assert f.lookup("Tylenol").key == "paracetamol"
    # Substring
    assert f.lookup("ibu").key == "ibuprofen"
    # Bangla
    assert f.lookup("প্যারাসিটামল").key == "paracetamol"
    # Unknown
    assert f.lookup("xyz_not_real") is None
