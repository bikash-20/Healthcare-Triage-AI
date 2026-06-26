import React, { useRef, useState } from 'react'
import { useLanguage } from '../LanguageContext'
import { isBengali, t } from '../i18n'

const autoFillMap = {
  bp: ['bp', 'blood pressure', 'pressure', 'রক্তচাপ'],
  hr: ['hr', 'heart rate', 'pulse', 'হৃদস্পন্দন', 'নাড়ি'],
  temp: ['temp', 'temperature', '°f', 'f', 'জ্বর', 'তাপমাত্রা'],
  spo2: ['spo2', 'spo₂', 'oxygen', 'অক্সিজেন'],
  glucose: ['glucose', 'blood glucose', 'sugar', 'গ্লুকোজ', 'চিনি'],
}

const normalizeAutoFill = (data) => {
  const result = {}
  for (const key of Object.keys(autoFillMap)) {
    for (const variant of autoFillMap[key]) {
      if (Object.prototype.hasOwnProperty.call(data, variant)) {
        result[key] = data[variant]
        break
      }
    }
  }
  return result
}

export default function VitalsForm({ onChange, onAnomaly }) {
  const { lang } = useLanguage()
  const [values, setValues] = useState({ bp: '', hr: '', temp: '', spo2: '', glucose: '' })
  const [uploadStatus, setUploadStatus] = useState(t('vitals.ocr_uploading', lang))
  const [ocrResult, setOcrResult] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [triageLoading, setTriageLoading] = useState(false)
  const fileInput = useRef(null)

  const updateField = (name, value) => {
    setValues((prev) => {
      const next = { ...prev, [name]: value }
      if (onChange) onChange(next)
      return next
    })
  }

  const fillVitals = (auto) => {
    const normalized = normalizeAutoFill(auto || {})
    if (Object.keys(normalized).length === 0) return
    setValues((prev) => {
      const next = { ...prev, ...normalized }
      if (onChange) onChange(next)
      return next
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setTriageLoading(true)
    try {
      const vitalsRes = await fetch('/api/vitals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      })
      const vitalsJson = await vitalsRes.json()
      if (onChange) onChange(values)

      const alertSummary = vitalsJson.alerts?.length
        ? `${lang === 'bn' ? 'সতর্কতা' : 'ALERTS'}: ${vitalsJson.alerts.join(', ')}. ${lang === 'bn' ? 'মাত্রা' : 'Severity'}: ${vitalsJson.level}.`
        : lang === 'bn' ? 'কোনো গুরুতর সতর্কতা নেই।' : 'No critical alerts.'

      const description = `${lang === 'bn' ? 'রোগীর ভিটালস' : 'Patient vitals'}: BP ${values.bp}, HR ${values.hr}, Temp ${values.temp}F, SpO2 ${values.spo2}%, Glucose ${values.glucose}mg/dL. ${alertSummary}`

      const triageRes = await fetch('/api/triage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          normalized_text: description,
          vitals_anomaly: vitalsJson,
          history: { medications: [], diagnoses: [], labs: [] },
          lang,
        }),
      })
      const triageData = await triageRes.json()
      if (onAnomaly) onAnomaly(triageData)
    } catch (err) {
      console.error('Vitals/triage call failed:', err)
    } finally {
      setTriageLoading(false)
    }
  }

  const simulateCritical = async () => {
    const simulated = { bp: '170/110', hr: '135', temp: '104.0', spo2: '88', glucose: '230' }
    setValues(simulated)
    if (onChange) onChange(simulated)
    setTriageLoading(true)

    try {
      const triageRes = await fetch('/api/triage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          normalized_text:
            'CRITICAL PATIENT. ALERTS: Low SpO2 at 88%, High fever 104F, Abnormal HR 135, High BP 170/110, High glucose 230. Severity level: red.',
          vitals_anomaly: {
            level: 'red',
            alerts: ['Low SpO2', 'High fever', 'Abnormal heart rate', 'Glucose outlier'],
          },
          history: { medications: [], diagnoses: [], labs: [] },
          lang,
        }),
      })
      const triageData = await triageRes.json()
      if (onAnomaly) onAnomaly(triageData)
    } catch (err) {
      console.error('Simulate triage failed:', err)
    } finally {
      setTriageLoading(false)
    }
  }

  const uploadFile = async (file) => {
    if (!file) return
    setIsUploading(true)
    setUploadStatus(t('vitals.ocr_uploading', lang))
    setOcrResult(null)
    const data = new FormData()
    data.append('file', file)

    try {
      const res = await fetch('/api/ocr/upload', { method: 'POST', body: data })
      const payload = await res.json()
      if (!res.ok) throw new Error(payload.error || payload.detail || t('vitals.ocr_failed', lang))
      setOcrResult(payload)
      setUploadStatus(t('vitals.ocr_complete', lang))
      if (payload.auto_fill) fillVitals(payload.auto_fill)
    } catch (err) {
      setUploadStatus(err.message || t('vitals.ocr_failed', lang))
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
          <label className="text-xs uppercase tracking-wide text-white/70 block mb-2">
            {t('vitals.title', lang)}
          </label>
          <p className="text-[11px] text-white/50">{t('vitals.subtitle', lang)}</p>
        </div>
        <button
          type="button"
          onClick={simulateCritical}
          disabled={triageLoading}
          className="btn-glass px-4 py-2 text-xs sm:text-sm disabled:opacity-50"
        >
          {triageLoading
            ? t('vitals.analyzing_critical', lang)
            : t('vitals.simulate_critical', lang)}
        </button>
      </div>

      <div className="glass-card p-4 sm:p-5 rounded-3xl border border-white/10 bg-white/5 shadow-soft-glow">
        <div className="grid gap-3">
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">
              {t('vitals.bp', lang)}
            </label>
            <input
              value={values.bp}
              onChange={(e) => updateField('bp', e.target.value)}
              name="bp"
              className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50"
              placeholder="120/80"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">
              {t('vitals.hr', lang)}
            </label>
            <input
              value={values.hr}
              onChange={(e) => updateField('hr', e.target.value)}
              name="hr"
              type="number"
              className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50"
              placeholder="72"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">
              {t('vitals.temp', lang)}
            </label>
            <input
              value={values.temp}
              onChange={(e) => updateField('temp', e.target.value)}
              name="temp"
              type="number"
              step="0.1"
              className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50"
              placeholder="98.6"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">
              {t('vitals.spo2', lang)}
            </label>
            <input
              value={values.spo2}
              onChange={(e) => updateField('spo2', e.target.value)}
              name="spo2"
              type="number"
              className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50"
              placeholder="98"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs sm:text-sm font-medium text-white/80">
              {t('vitals.glucose', lang)}
            </label>
            <input
              value={values.glucose}
              onChange={(e) => updateField('glucose', e.target.value)}
              name="glucose"
              type="number"
              className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/50"
              placeholder="110"
            />
          </div>
        </div>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInput.current?.click()}
        className={`glass-card border border-dashed ${
          dragging ? 'border-cyan-400 bg-cyan-500/10' : 'border-white/20 bg-white/5'
        } p-5 rounded-3xl text-center cursor-pointer transition-all duration-200`}
        role="button"
        tabIndex={0}
      >
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          hidden
          onChange={handleFileChange}
        />
        <p className="text-sm text-white/70">{t('vitals.ocr_title', lang)}</p>
        <p className="mt-3 text-xs text-white/50">{t('vitals.ocr_hint', lang)}</p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wide text-white/60">
            {t('vitals.ocr_status_label', lang)}
          </span>
          <span className="text-xs text-white/50">
            {isUploading ? t('vitals.ocr_processing', lang) : t('vitals.ocr_ready', lang)}
          </span>
        </div>
        <div className="glass-card p-4 rounded-3xl border border-white/10 bg-black/20">
          <p className="text-sm text-white/70">{uploadStatus}</p>
          {ocrResult?.raw_text ? (
            <p className="mt-3 text-[13px] leading-5 text-white/60">
              <span className="text-white/80">{t('vitals.ocr_detected_label', lang)}:</span>{' '}
              {ocrResult.raw_text.slice(0, 180)}
              {ocrResult.raw_text.length > 180 ? '…' : ''}
            </p>
          ) : null}
          {ocrResult?.labs?.length ? (
            <div className="mt-3 grid gap-2 text-sm text-white/70">
              <div className="font-semibold text-white/90">
                {t('vitals.ocr_extracted_labs', lang)}:
              </div>
              {ocrResult.labs.map((lab, index) => (
                <div key={index}>
                  {lab.test_name}: {lab.value ?? 'N/A'} {lab.units ?? ''}
                </div>
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
        {triageLoading ? t('vitals.analyzing', lang) : t('vitals.submit', lang)}
      </button>
    </form>
  )
}