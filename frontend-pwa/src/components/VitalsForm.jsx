import React, { useState, useRef } from 'react'

const detectBengali = (text) => /[\u0980-\u09FF]/.test(text)

const autoFillMap = {
  bp: ['bp', 'blood pressure', 'pressure'],
  hr: ['hr', 'heart rate', 'pulse'],
  temp: ['temp', 'temperature', '°f', 'f'],
  spo2: ['spo2', 'spO2', 'oxygen', 'spo₂'],
  glucose: ['glucose', 'blood glucose', 'sugar']
}

const normalizeAutoFill = (data) => {
  const result = {}
  for (const key of Object.keys(autoFillMap)) {
    const possible = autoFillMap[key]
    for (const variant of possible) {
      if (Object.prototype.hasOwnProperty.call(data, variant)) {
        result[key] = data[variant]
        break
      }
    }
  }
  return result
}

export default function VitalsForm({ onChange, onAnomaly }) {
  const [values, setValues] = useState({ bp: '', hr: '', temp: '', spo2: '', glucose: '' })
  const [uploadStatus, setUploadStatus] = useState('Upload prescription or lab report image')
  const [ocrResult, setOcrResult] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [triageLoading, setTriageLoading] = useState(false) // ✅ NEW
  const fileInput = useRef(null)

  const updateField = (name, value) => {
    setValues(prev => {
      const next = { ...prev, [name]: value }
      onChange(next)
      return next
    })
  }

  const fillVitals = (auto) => {
    const normalized = normalizeAutoFill(auto)
    if (Object.keys(normalized).length === 0) return
    setValues(prev => {
      const next = { ...prev, ...normalized }
      onChange(next)
      return next
    })
  }

  // ✅ FIXED: Now calls /api/triage after /api/vitals to get proper TriageResponse
  const handleSubmit = async (e) => {
    e.preventDefault()
    const formPayload = { ...values }
    setTriageLoading(true)

    try {
      // Step 1: get vitals anomaly
      const vitalsRes = await fetch('/api/vitals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formPayload)
      })
      const vitalsJson = await vitalsRes.json()
      onChange(formPayload)

      // Step 2: generate full triage from vitals
      const triageRes = await fetch('/api/triage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          normalized_text: `Patient vitals: BP ${values.bp}, HR ${values.hr}, Temp ${values.temp}F, SpO2 ${values.spo2}%, Glucose ${values.glucose}mg/dL`,
          vitals_anomaly: vitalsJson,
          history: { medications: [], diagnoses: [], labs: [] }
        })
      })
      const triageData = await triageRes.json()
      onAnomaly(triageData) // ✅ Now has triage_severity, clinical_reasoning etc.
    } catch (err) {
      console.error('Vitals/triage call failed:', err)
    } finally {
      setTriageLoading(false)
    }
  }

  // ✅ FIXED: Now calls /api/triage so triage_severity is properly set
  const simulateCritical = async () => {
    const simulated = { bp: '170/110', hr: '135', temp: '104.0', spo2: '88', glucose: '230' }
    setValues(simulated)
    onChange(simulated)
    setTriageLoading(true)

    try {
      const triageRes = await fetch('/api/triage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          normalized_text: 'Critical patient: BP 170/110, HR 135, Temp 104F, SpO2 88%, Glucose 230mg/dL',
          vitals_anomaly: { anomaly: true, reason: 'Simulated critical case' },
          history: { medications: [], diagnoses: [], labs: [] }
        })
      })
      const triageData = await triageRes.json()
      onAnomaly(triageData) // ✅ triage_severity will now be Red
    } catch (err) {
      console.error('Simulate triage failed:', err)
    } finally {
      setTriageLoading(false)
    }
  }

  const uploadFile = async (file) => {
    if (!file) return
    setIsUploading(true)
    setUploadStatus('Uploading image...')
    setOcrResult(null)
    const data = new FormData()
    data.append('file', file)

    try {
      const res = await fetch('/api/ocr/upload', { method: 'POST', body: data })
      const payload = await res.json()
      if (!res.ok) throw new Error(payload.error || 'OCR upload failed')
      setOcrResult(payload)
      setUploadStatus('OCR scan complete. Auto-filled vitals when available.')
      if (payload.auto_fill) fillVitals(payload.auto_fill)
    } catch (err) {
      setUploadStatus(err.message || 'OCR upload failed')
    } finally {
      setIsUploading(false)
      setDragging(false)
    }
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (file) await uploadFile(file)
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) await uploadFile(file)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 w-full">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <label className="text-xs uppercase tracking-wide text-white/70 block mb-2">Patient Vital Signs</label>
          <p className="text-[11px] text-white/50">Enter vitals or use lab report upload to auto-populate values.</p>
        </div>
        <button
          type="button"
          onClick={simulateCritical}
          disabled={triageLoading}
          className="btn-glass px-4 py-2 text-xs sm:text-sm disabled:opacity-50"
        >
          {triageLoading ? 'Analyzing...' : 'Simulate Critical Case'}
        </button>
      </div>

      <div className="glass-card p-4 sm:p-5 rounded-3xl border border-white/10 bg-white/5 shadow-soft-glow">
        <div className="grid gap-3">
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">Blood Pressure (systolic/diastolic)</label>
            <input value={values.bp} onChange={(e) => updateField('bp', e.target.value)} name="bp" className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50" placeholder="120/80" />
          </div>
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">Heart Rate (bpm)</label>
            <input value={values.hr} onChange={(e) => updateField('hr', e.target.value)} name="hr" type="number" className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50" placeholder="72" />
          </div>
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">Temperature (°F)</label>
            <input value={values.temp} onChange={(e) => updateField('temp', e.target.value)} name="temp" type="number" step="0.1" className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50" placeholder="98.6" />
          </div>
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">SpO₂ (%)</label>
            <input value={values.spo2} onChange={(e) => updateField('spo2', e.target.value)} name="spo2" type="number" className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50" placeholder="98" />
          </div>
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">Blood Glucose (mg/dL)</label>
            <input value={values.glucose} onChange={(e) => updateField('glucose', e.target.value)} name="glucose" type="number" className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50" placeholder="110" />
          </div>
        </div>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInput.current?.click()}
        className={`glass-card border border-dashed ${dragging ? 'border-cyan-400 bg-cyan-500/10' : 'border-white/20 bg-white/5'} p-5 rounded-3xl text-center cursor-pointer transition-all duration-200`}
      >
        <input ref={fileInput} type="file" accept="image/*" hidden onChange={handleFileChange} />
        <p className="text-sm text-white/70">Drag & drop a prescription or lab report image here, or click to upload.</p>
        <p className="mt-3 text-xs text-white/50">Supports handwriting and printed reports.</p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wide text-white/60">OCR Scan Status</span>
          <span className="text-xs text-white/50">{isUploading ? 'Processing…' : 'Ready'}</span>
        </div>
        <div className="glass-card p-4 rounded-3xl border border-white/10 bg-black/20">
          <p className="text-sm text-white/70">{uploadStatus}</p>
          {ocrResult?.raw_text ? <p className="mt-3 text-[13px] leading-5 text-white/60">Detected text preview: {ocrResult.raw_text.slice(0, 180)}{ocrResult.raw_text.length > 180 ? '...' : ''}</p> : null}
          {ocrResult?.labs?.length ? (
            <div className="mt-3 grid gap-2 text-sm text-white/70">
              <div className="font-semibold text-white/90">Extracted Labs:</div>
              {ocrResult.labs.map((lab, index) => (
                <div key={index}>{lab.test_name}: {lab.value ?? 'N/A'} {lab.units ?? ''}</div>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <button
        type="submit"
        disabled={triageLoading}
        className="btn-glass w-full px-5 py-3 text-sm font-medium disabled:opacity-50"
      >
        {triageLoading ? '⏳ Analyzing vitals...' : 'Submit Vitals'}
      </button>
    </form>
  )
}