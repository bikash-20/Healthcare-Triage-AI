import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import openai
from langdetect import detect
from .ml_engine import analyze_vitals
from .services.ocr_service import extract_text_from_image, parse_medical_text
from .services.voice_service import stream_tts
from . import llm_client
from .schemas import OCRParseResult, TriageResponse
import logging

logger = logging.getLogger('backend')
logging.basicConfig(level=logging.INFO)

load_dotenv()

OPENAI_KEY = os.getenv('OPENAI_API_KEY')
EDGE_ROUTER_URL = os.getenv('EDGE_ROUTER_URL')

def create_app():
  app = FastAPI()
  app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

  @app.post('/api/audio/intake')
  async def audio_intake(file: UploadFile = File(...)):
    # save temp
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
      content = await file.read()
      tmp.write(content)
      tmp_path = tmp.name

    # Send to OpenAI Whisper
    openai.api_key = OPENAI_KEY
    try:
      with open(tmp_path, 'rb') as f:
        resp = openai.Audio.transcriptions.create(file=f, model='whisper-1')
      text = resp.get('text') if isinstance(resp, dict) else getattr(resp,'text', '')
    except Exception as e:
      return JSONResponse({'error': str(e)}, status_code=500)

    # detect language
    lang = 'en'
    try:
      lang = detect(text)
    except:
      lang = 'en'

    # If Bengali, translate using Google Translate
    if lang and lang.startswith('bn'):
      from google.cloud import translate_v2 as translate
      client = translate.Client()
      translated = client.translate(text, target_language='en')
      normalized = translated['translatedText']
    else:
      normalized = text

    return {'raw_text': text, 'normalized': normalized, 'lang': lang}

  @app.post('/api/ocr/upload')
  async def ocr_upload(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
      content = await file.read()
      tmp.write(content)
      tmp_path = tmp.name
    try:
      raw = extract_text_from_image(tmp_path)
      auto_fill = parse_medical_text(raw)['auto_fill']
      prompt = f"Extract medications, dosages, diagnoses, and lab results from the following medical text. Return ONLY valid JSON matching this schema: {OCRParseResult.schema_json()}\n\nText:\n{raw}"
      try:
        parsed = await llm_client.call_edge_router(prompt)
        result = OCRParseResult(**parsed, raw_text=raw)
        payload = result.dict()
        payload['auto_fill'] = auto_fill
        return payload
      except Exception as e:
        logger.exception('OCR parsing failed')
        return JSONResponse({'error': 'Failed to parse OCR text', 'detail': str(e), 'raw_text': raw, 'auto_fill': auto_fill}, status_code=500)
    except Exception as e:
      return JSONResponse({'error': str(e)}, status_code=500)

  @app.post('/api/ocr/parse')
  async def ocr_parse(payload: Request):
    data = await payload.json()
    raw = data.get('raw_text')
    if not raw:
      return JSONResponse({'error': 'raw_text required'}, status_code=400)
    prompt = f"Extract medications, dosages, diagnoses, and lab results from the following medical text. Return ONLY valid JSON matching this schema: {OCRParseResult.schema_json()}\n\nText:\n{raw}"
    try:
      parsed = await llm_client.call_edge_router(prompt)
      result = OCRParseResult(**parsed, raw_text=raw)
      return result.dict()
    except Exception as e:
      logger.exception('OCR parse API failed')
      return JSONResponse({'error': 'Failed to parse OCR text', 'detail': str(e)}, status_code=500)

  @app.post('/api/triage')
  async def triage_endpoint(payload: Request):
    data = await payload.json()
    normalized = data.get('normalized_text')
    vitals_anomaly = data.get('vitals_anomaly')
    history = data.get('history')
    if not normalized or vitals_anomaly is None or history is None:
      return JSONResponse({'error': 'normalized_text, vitals_anomaly, and history required'}, status_code=400)

    # Build clinical prompt
    prompt = (
      "You are a clinical decision support assistant for rural community health workers in Bangladesh. "
      "Given the patient's symptomatic description, the structured medication/history, and vital anomaly findings, produce STRICT JSON matching this schema: "
      f"{TriageResponse.schema_json()}\n\n"
      "Inputs:\n"
      f"Normalized symptoms text:\n{normalized}\n\n"
      f"Vitals anomaly JSON:\n{vitals_anomaly}\n\n"
      f"Medication/history JSON:\n{history}\n\n"
      "Important: If vitals indicate a red alert, the triage_severity must be 'Red' or 'Black'. Return only JSON."
    )
    try:
      parsed = await llm_client.call_edge_router(prompt, temperature=0.0, max_tokens=800)
      triage = TriageResponse(**parsed)
      return triage.dict()
    except Exception as e:
      logger.exception('Triage LLM call failed')
      return JSONResponse({'error': 'Triage generation failed', 'detail': str(e)}, status_code=500)
  @app.post('/api/dose')
  async def dose_endpoint(payload: Request):
    data = await payload.json()
    medication = data.get('medication')
    age = data.get('age')
    weight = data.get('weight')

    if not medication or age is None or weight is None:
        return JSONResponse({'error': 'medication, age, and weight are required'}, status_code=400)

    prompt = (
        "You are a clinical pharmacist AI for rural health workers in Bangladesh. "
        "Calculate the safe medication dose based on patient age and weight. "
        "Return ONLY valid JSON with these exact fields:\n"
        "{\n"
        '  "summary_en": "Full dose instructions in English",\n'
        '  "summary_bn": "Full dose instructions in Bengali",\n'
        '  "dose_per_kg": "e.g. 15mg/kg",\n'
        '  "total_dose": "e.g. 300mg",\n'
        '  "frequency": "e.g. Every 6 hours",\n'
        '  "route": "e.g. Oral",\n'
        '  "is_dangerous": true or false,\n'
        '  "warning_en": "Warning in English if dangerous, else null",\n'
        '  "warning_bn": "Warning in Bengali if dangerous, else null"\n'
        "}\n\n"
        f"Medication: {medication}\n"
        f"Patient age: {age} years\n"
        f"Patient weight: {weight} kg\n\n"
        "Important: If the dose is unsafe for this age/weight, set is_dangerous to true and explain why in both languages. Return only JSON."
    )

    try:
        parsed = await llm_client.call_edge_router(prompt, temperature=0.0, max_tokens=600)
        return parsed
    except Exception as e:
        logger.exception('Dose calculation failed')
        return JSONResponse({'error': 'Dose calculation failed', 'detail': str(e)}, status_code=500)
  @app.post('/api/vitals')
  async def vitals_endpoint(payload: Request):
    data = await payload.json()
    result = analyze_vitals(data)
    return result

  @app.post('/api/chat')
  async def chat_endpoint(payload: Request):
    data = await payload.json()
    messages = data.get('messages')
    vitals_context = data.get('vitals') or {}
    triage_context = data.get('triage') or {}

    if not messages or not isinstance(messages, list):
      return JSONResponse({'error': 'messages list is required'}, status_code=400)

    def render_context():
      lines = [
        'Patient vitals data:',
        f"Blood Pressure: {vitals_context.get('bp', 'unknown')}",
        f"Heart Rate: {vitals_context.get('hr', 'unknown')}",
        f"Temperature: {vitals_context.get('temp', 'unknown')}",
        f"SpO2: {vitals_context.get('spo2', 'unknown')}",
        f"Blood Glucose: {vitals_context.get('glucose', 'unknown')}",
        '',
        f"Current triage severity: {triage_context.get('triage_severity', 'unknown')}",
        f"Clinical reasoning: {triage_context.get('clinical_reasoning', 'unknown')}",
        '',
        'Answer as NEXORA, a medical AI expert. Provide patient-specific medical advice, speak in the user language, and do not invent findings.'
      ]
      return '\n'.join(lines)

    system_prompt = (
      'You are NEXORA, a highly qualified medical consultant for rural healthcare workers. '
      'Silently use the patient vitals and triage context to answer the user question with clinical caution. '
      'If the user asks in Bengali, reply in Bengali. If the user asks in English, reply in English. '
      'Always stay concise, factual, and supportive.'
      f"\n\n{render_context()}"
    )
    model = data.get('model', 'cf-llama')
    try:
      text = await llm_client.call_edge_router(messages=[{'role':'system','content': system_prompt}, *messages], response_mode='raw', temperature=0.6, max_tokens=900, api_key=data.get('api_key'), model=model)
      language = 'bn' if any('উ' in c or 'ক' in c or 'া' in c for c in text) else 'en'
      return {'assistant': text, 'language': language, 'model': model}
    except Exception as e:
      logger.exception('Chat gateway failed')
      return JSONResponse({'error': 'NEXORA chat failed', 'detail': str(e)}, status_code=500)

  @app.get('/api/tts/stream')
  async def tts_stream(q: str = 'Summary not provided'):
    async def streamer():
      async for chunk in stream_tts(q):
        yield chunk
    return StreamingResponse(streamer(), media_type='audio/mpeg')

  return app