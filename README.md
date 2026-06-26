# Rural Health Triage

A bilingual clinical decision support system for community health workers in rural Bangladesh. The app captures patient symptoms through voice, extracts vitals from prescription photos, runs rule-based anomaly detection, and produces a four-tier triage recommendation with on-site first-aid guidance. Everything works offline once installed and the entire interface flips between English and Bangla at the user's choice.

Built for the Codex Community Hackathon 2026 in association with SUST CSE Carnival and Poridhi.

Live deployment: https://rural-health-triage-nine.vercel.app/

---

## The problem

Most triage software assumes a doctor, a desktop, and reliable connectivity. None of those apply for the community health workers this project is built for. They work in the field, see patients in Bangla, and need an answer in under a minute. This project is an attempt to put a usable triage tool on the cheapest Android phone they carry, with full voice intake, no English requirement, and zero need for a network connection once the app is installed.

---

## What it does

- Voice intake in Bangla or English through the browser microphone. Whisper transcribes, language is detected from Unicode ranges, and the normalized text feeds downstream.
- Vitals form with rule-based anomaly detection. SpO2 below 92, temperature above 103 F, or a Z-score beyond 2.5 on heart rate or glucose escalates the severity.
- OCR on prescription or lab-report images. Google Cloud Vision pulls raw text, regex extracts vitals, and an LLM call structures the rest into medications, diagnoses, and lab results.
- Triage scoring through an LLM that returns Green, Yellow, Red, or Black plus a clinical reasoning field, differential diagnoses, and referral urgency.
- Streaming text-to-speech in both languages. The backend tries Worker AI, then OpenAI TTS, then ElevenLabs with automatic key rotation.
- PDF summary downloadable in either language. Bengali filename when Bangla is active.
- Progressive Web App. Installable on Android, iOS, and desktop, and the service worker keeps the app shell functional without a network.

---

## Architecture

Three independent services, each with its own deployment story.

```
rural-health-triage/
|-- frontend-pwa/      Vite + React 18 PWA, deployed on Vercel
|-- backend-core/      FastAPI + Pydantic v2, deployed on Render
`-- edge-router/       Cloudflare Worker, deployed via wrangler
```

The frontend is a static SPA. All requests for AI-backed endpoints are forwarded by the FastAPI backend to a Cloudflare Worker that owns the LLM provider logic and the API keys. The worker can route to Workers AI, OpenRouter free models, OpenAI, or any combination of those. The backend never holds OpenAI or OpenRouter keys directly; it only knows the worker's URL and an optional shared secret.

The reason for that split is operational. Free model quotas change weekly, and a hackathon-grade demo benefits from being able to swap providers without redeploying the backend. The worker is small, fast to redeploy, and is the only place secrets are stored.

---

## Repository layout

```
rural-health-triage/
|-- backend-core/
|   |-- app/
|   |   |-- main.py              FastAPI app factory and endpoints
|   |   |-- schemas.py           Pydantic request and response models
|   |   |-- llm_client.py        Retrying client for the edge router
|   |   |-- ml_engine.py         Vitals anomaly thresholds and escalation
|   |   |-- translations.py      Bangla and English strings, language detection
|   |   |-- __init__.py          App factory export
|   |   `-- services/
|   |       |-- ocr_service.py   Google Cloud Vision wrapper
|   |       `-- voice_service.py Streaming TTS with provider fallback
|   |-- tests/test_main.py       Async integration tests
|   `-- requirements.txt
|-- edge-router/
|   |-- index.js                 Worker entry, CORS, model fallback chain
|   `-- wrangler.toml
|-- frontend-pwa/
|   |-- index.html
|   |-- public/
|   |   |-- app.icon             Home screen icon
|   |   `-- manifest.json        PWA manifest
|   |-- src/
|   |   |-- App.jsx              Top-level shell, wraps LanguageProvider
|   |   |-- LanguageContext.jsx  Language state, localStorage persistence
|   |   |-- i18n.js              Frontend translation dictionary
|   |   |-- main.jsx
|   |   `-- components/
|   |       |-- AudioIntake.jsx      MediaRecorder plus upload
|   |       |-- AudioPlayer.jsx      Streaming audio element
|   |       |-- DoseCalculator.jsx   Age and weight-based dosing
|   |       |-- GlassCard.jsx        Shared glassmorphic card
|   |       |-- InstallBanner.jsx    PWA install prompt
|   |       |-- LanguageToggle.jsx   EN and BN switch
|   |       |-- NexoraChatbot.jsx    Floating chat assistant
|   |       |-- TriageCard.jsx       Severity display
|   |       `-- VitalsForm.jsx       Form with OCR drop zone
|   |-- package.json
|   |-- tailwind.config.js
|   `-- vite.config.js
|-- vercel.json                   Rewrites /api to the backend
`-- README.md
```

---

## API surface

All endpoints accept CORS and return JSON. The `lang` query parameter or body field is optional and defaults to English.

| Method | Path                 | Purpose                                                     |
|--------|----------------------|-------------------------------------------------------------|
| GET    | /api/health          | Health check                                                |
| POST   | /api/audio/intake    | Upload audio blob, returns transcript and detected language |
| POST   | /api/ocr/upload      | Upload image, returns raw text and auto-filled vitals       |
| POST   | /api/ocr/parse       | Structure raw text into medications, diagnoses, labs        |
| POST   | /api/triage          | Symptom text plus vitals, returns severity and reasoning    |
| POST   | /api/dose            | Age, weight, medication, returns recommended dose           |
| POST   | /api/vitals          | Vitals form, returns anomaly level and alerts               |
| POST   | /api/chat            | Chat messages plus optional patient context                 |
| GET    | /api/tts/stream      | Streaming audio for a given text and language               |

Validation errors return HTTP 422 with field-level detail from Pydantic.

---

## Running it locally

You need Node 18 or newer and Python 3.11 or newer. The frontend reads from `.env` for the API base URL, the backend reads from `.env` for the edge router URL, and the worker reads its secrets from `wrangler.toml` or the Cloudflare dashboard.

```bash
# Backend
cd backend-core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in EDGE_ROUTER_URL
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend-pwa
npm install
npm run dev
```

Open http://localhost:5173. The app will work fully against the local backend even without a deployed worker if the vitals and OCR endpoints are exercised alone; AI-backed endpoints (triage, chat, dose, OCR parse) need the worker URL.

Run the backend tests:

```bash
cd backend-core
pytest -q tests
```

Nine tests cover health, vitals validation, vitals anomaly thresholds, OCR parse, triage validation, dose validation, chat validation, and TTS empty-query handling.

---

## Deployment

The frontend is already deployed on Vercel through this repository. The vercel.json rewrites all `/api/*` requests to the Render backend service. To deploy the backend, follow these steps.

### Render for the FastAPI backend

1. Sign in to https://render.com with the GitHub account that owns this repository.
2. Click New, then Web Service, then pick the repository.
3. Set Root Directory to `backend-core`.
4. Build command: `pip install -r requirements.txt`.
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
6. Pick the free instance type for the demo. Pick a region close to your Cloudflare worker.
7. Under Environment, add:

   ```
   EDGE_ROUTER_URL = https://rural-health-triage-router.<your-subdomain>.workers.dev
   OPENAI_API_KEY = (optional, leave empty for free-tier routing)
   ELEVENLABS_API_KEY_1 = (optional)
   ELEVENLABS_API_KEY_2 = (optional)
   ELEVENLABS_API_KEY_3 = (optional)
   BACKEND_API_KEY = (optional shared secret, must match worker)
   ```

8. Click Create Web Service. After the first build, Render gives you a URL like `https://rural-health-triage-backend.onrender.com`.

### Cloudflare Worker for the edge router

1. Install wrangler if needed: `npm install -g wrangler`.
2. Sign in: `wrangler login`.
3. From the `edge-router/` directory:

   ```bash
   wrangler secret put OPENAI_API_KEY         # only if you have one
   wrangler secret put OPENROUTER_API_KEY     # free models via OpenRouter
   wrangler secret put BACKEND_API_KEY        # must match the backend value
   wrangler deploy
   ```

4. Copy the deployed worker URL and paste it as `EDGE_ROUTER_URL` in the Render dashboard.

### Vercel for the frontend

The repository is already connected to Vercel. The frontend redeploys automatically when commits land on `main`. The `vercel.json` at the repo root rewrites `/api/*` to the Render backend URL, so no frontend code changes are required once Render is live.

### Optional: Google Cloud Vision

For OCR to work in production, set `GOOGLE_APPLICATION_CREDENTIALS` on Render to the contents of a service account JSON file (use the environment variable as a secret, not a file path). If this is not set, OCR upload falls back to a regex-only path that still works on simple printed text.

---

## Design notes

A few decisions worth mentioning because they are not obvious from the code.

The language toggle is a single source of truth held in a React context, persisted to localStorage under the key `rht.lang`, and mirrored to `<html lang>` and a `data-lang` attribute so screen readers, CSS `:lang()` selectors, and any future server-rendered piece all see the same value. Both the backend and the worker carry a parallel translation dictionary in `translations.py` and `i18n.js` respectively. The keys are kept identical by convention.

The vitals anomaly detector is intentionally conservative. It is a rule engine, not a model, and the thresholds are taken from standard emergency medicine references. The detector returns a level and a list of human-readable alerts, and the triage LLM is told to weight vitals anomalies heavily but not blindly override its clinical reasoning.

TTS provider fallback is implemented as a single function that tries Worker AI first, then OpenAI TTS, then ElevenLabs with key rotation on 401, 402, 403, and 429 responses. Bengali text routes to a female voice (shimmer on OpenAI) because that tends to read Bangla better than the default voices.

The edge router exists for two reasons. First, it lets the backend avoid holding per-user API keys. Second, it lets the routing logic evolve independently of the backend. Today it tries the user's key if provided, then a configured primary model, then free fallbacks. Tomorrow it can add caching, rate limiting, or abuse detection without touching the Python code.

---

## What is intentionally not built

A few things that look like they should be there but are deliberately left out.

- No user authentication. The hackathon demo assumes the device belongs to one CHW. Production would need at minimum device-based auth and patient record storage.
- No persistent patient history. Each session is independent. Records are kept in localStorage only for the duration of the visit.
- No real-time doctor connection. The referral urgency is a recommendation only; actual specialist handoff would need an integration that does not exist in the demo.
- No model fine-tuning. The clinical reasoning is whatever the upstream LLM returns, and is not medically validated. The system is decision support, not diagnosis.

---

## Performance

These numbers are from the demo deployment on Vercel's free tier and Render's free tier.

- Frontend first paint: under 1.5 seconds on a mid-range Android phone over 4G.
- Vitals anomaly endpoint: under 30 milliseconds.
- Triage endpoint: 1.5 to 4 seconds depending on the upstream LLM provider.
- TTS first byte: under 200 milliseconds with Worker AI; 800 milliseconds to 1.5 seconds with ElevenLabs.

---

## Testing

```bash
# Backend unit and integration tests
cd backend-core
pytest -q tests

# Frontend production build (catches type and import errors)
cd frontend-pwa
npm run build
```

The backend suite uses ASGITransport so it runs without a live server. LLM calls are monkeypatched at the module level so the tests do not require any API keys to pass.

---

## License

MIT for the code in this repository. Brand names, API keys, and any third-party service logos remain the property of their respective owners.

---

## Acknowledgements

Built during the Codex Community Hackathon 2026. Thanks to SUST CSE, Poridhi, and bKash for organising the event, and to the community health workers who tested early versions and gave blunt feedback on the Bangla UI strings.
