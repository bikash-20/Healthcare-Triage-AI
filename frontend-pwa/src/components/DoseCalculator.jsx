import React, { useState } from 'react'
import { useLanguage } from '../LanguageContext'
import { t } from '../i18n'

const DEFAULT_MEDICATIONS = [
  { key: 'paracetamol', label: 'Paracetamol', unit: 'mg' },
  { key: 'amoxicillin', label: 'Amoxicillin', unit: 'mg' },
  { key: 'ibuprofen', label: 'Ibuprofen', unit: 'mg' },
  { key: 'ors', label: 'ORS', unit: 'sachet' },
]

export default function DoseCalculator({ vitals = {} }) {
  const { lang } = useLanguage()
  const [age, setAge] = useState('')
  const [weight, setWeight] = useState('')
  const [medication, setMedication] = useState(DEFAULT_MEDICATIONS[0].key)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch('/api/dose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          age: Number(age),
          weight: Number(weight),
          medication,
          vitals,
          lang,
        }),
      })
      const payload = await res.json()
      if (!res.ok) {
        throw new Error(payload.detail?.[0]?.msg || payload.detail || t('dose.failed', lang))
      }
      setResult(payload)
    } catch (err) {
      console.error('Dose calc error:', err)
      setError(err.message || t('dose.failed', lang))
    } finally {
      setLoading(false)
    }
  }

  const selectedMed = DEFAULT_MEDICATIONS.find((m) => m.key === medication) || DEFAULT_MEDICATIONS[0]

  return (
    <div className="glass-card p-5 sm:p-6 rounded-3xl border border-white/10 bg-white/5 shadow-soft-glow space-y-4">
      <div>
        <h3 className="text-sm sm:text-base font-semibold text-white/90">
          {t('dose.title', lang)}
        </h3>
        <p className="mt-1 text-xs text-white/60">{t('dose.subtitle', lang)}</p>
      </div>

      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-white/70">{t('dose.age', lang)}</label>
            <input
              type="number"
              min="0"
              max="120"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white"
              placeholder="5"
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-white/70">{t('dose.weight', lang)}</label>
            <input
              type="number"
              min="0"
              max="300"
              step="0.1"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white"
              placeholder="18"
              required
            />
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-xs text-white/70">{t('dose.medication', lang)}</label>
          <select
            value={medication}
            onChange={(e) => setMedication(e.target.value)}
            className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white"
          >
            {DEFAULT_MEDICATIONS.map((m) => (
              <option key={m.key} value={m.key} className="bg-slate-900">
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="btn-glass w-full px-5 py-3 text-sm font-medium disabled:opacity-50"
        >
          {loading ? t('dose.calculating', lang) : t('dose.submit', lang)}
        </button>
      </form>

      {error ? <p className="text-xs text-rose-300/80">{error}</p> : null}

      {result ? (
        <div className="space-y-2 text-sm text-white/85">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wide text-white/60">
              {t('dose.result_label', lang)} ({selectedMed.label})
            </span>
            <span className="text-xs text-white/60">{selectedMed.unit}</span>
          </div>
          <p className="text-lg font-semibold">
            {result.dose != null ? `${result.dose} ${selectedMed.unit}` : t('dose.unavailable', lang)}
          </p>
          {result.frequency ? (
            <p className="text-xs text-white/70">
              <span className="text-white/50">{t('dose.frequency', lang)}:</span> {result.frequency}
            </p>
          ) : null}
          {result.duration ? (
            <p className="text-xs text-white/70">
              <span className="text-white/50">{t('dose.duration', lang)}:</span> {result.duration}
            </p>
          ) : null}
          {result.notes ? (
            <p className="text-xs text-white/70 whitespace-pre-line">
              <span className="text-white/50">{t('dose.notes', lang)}:</span> {result.notes}
            </p>
          ) : null}
          {result.warning ? (
            <p className="text-xs text-amber-300/90">
              <span className="text-amber-200">{t('dose.warning', lang)}:</span> {result.warning}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}