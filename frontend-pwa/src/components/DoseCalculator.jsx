import React, { useState } from 'react'

export default function DoseCalculator() {
  const [medication, setMedication] = useState('')
  const [age, setAge] = useState('')
  const [weight, setWeight] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [audioLoading, setAudioLoading] = useState(false)
  const audioRef = React.useRef(null)

  const calculate = async () => {
    if (!medication || !age || !weight) return
    setLoading(true)
    setResult(null)

    try {
      const res = await fetch('/api/dose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ medication, age: Number(age), weight: Number(weight) })
      })
      const data = await res.json()
      setResult(data)
    } catch (err) {
      console.error('Dose calculation failed:', err)
    } finally {
      setLoading(false)
    }
  }

  const speakResult = async () => {
    if (!result) return
    setAudioLoading(true)
    try {
      const text = `${result.summary_en}. ${result.summary_bn}. ${result.warning_en || ''} ${result.warning_bn || ''}`
      const url = `/api/tts/stream?q=${encodeURIComponent(text)}`
      const response = await fetch(url)
      if (!response.ok) throw new Error('TTS failed')
      const arrayBuffer = await response.arrayBuffer()
      const blob = new Blob([arrayBuffer], { type: 'audio/mpeg' })
      const audioUrl = URL.createObjectURL(blob)
      if (audioRef.current) {
        audioRef.current.src = audioUrl
        audioRef.current.load()
        await audioRef.current.play()
      }
    } catch (err) {
      console.error('TTS failed:', err)
    } finally {
      setAudioLoading(false)
    }
  }

  return (
    <div className="glass-card p-4 sm:p-6 rounded-xl sm:rounded-2xl w-full space-y-4">
      <audio ref={audioRef} preload="none" />

      {/* Header */}
      <div>
        <label className="text-xs uppercase tracking-wide text-white/70 block mb-1">
          Dose Calculator
        </label>
        <p className="text-xs text-white/50">
          রোগীর বয়স ও ওজন অনুযায়ী নিরাপদ ওষুধের ডোজ গণনা
        </p>
      </div>

      {/* Medication input */}
      <div className="space-y-1">
        <label className="text-xs text-white/70">Medication name / ওষুধের নাম</label>
        <input
          value={medication}
          onChange={e => setMedication(e.target.value)}
          placeholder="e.g. Paracetamol / প্যারাসিটামল"
          className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/40 text-sm"
        />
      </div>

      {/* Age and Weight */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-xs text-white/70">Age (years) / বয়স</label>
          <input
            value={age}
            onChange={e => setAge(e.target.value)}
            type="number"
            placeholder="e.g. 5"
            className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/40 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-white/70">Weight (kg) / ওজন</label>
          <input
            value={weight}
            onChange={e => setWeight(e.target.value)}
            type="number"
            placeholder="e.g. 20"
            className="w-full bg-transparent border border-white/20 p-3 rounded-2xl text-white placeholder:text-white/40 text-sm"
          />
        </div>
      </div>

      {/* Calculate button */}
      <button
        onClick={calculate}
        disabled={loading || !medication || !age || !weight}
        className="btn-glass w-full px-4 py-3 text-sm font-medium disabled:opacity-50"
      >
        {loading ? '⏳ Calculating...' : '💊 Calculate Safe Dose'}
      </button>

      {/* Result */}
      {result && (
        <div className={`rounded-2xl p-4 space-y-3 border ${result.is_dangerous ? 'border-red-400/50 bg-red-500/10' : 'border-green-400/30 bg-green-500/10'}`}>

          {/* Warning banner */}
          {result.is_dangerous && (
            <div className="flex items-start gap-2 bg-red-600/30 border border-red-400/40 rounded-xl p-3">
              <span className="text-lg">⚠️</span>
              <div>
                <p className="text-sm font-bold text-red-300">{result.warning_en}</p>
                <p className="text-sm text-red-300/80 mt-1">{result.warning_bn}</p>
              </div>
            </div>
          )}

          {/* English result */}
          <div>
            <p className="text-xs uppercase tracking-wide text-white/50 mb-1">English</p>
            <p className="text-sm text-white/90 leading-relaxed">{result.summary_en}</p>
          </div>

          {/* Bengali result */}
          <div className="pt-2 border-t border-white/10">
            <p className="text-xs uppercase tracking-wide text-white/50 mb-1">বাংলা</p>
            <p className="text-sm text-white/90 leading-relaxed">{result.summary_bn}</p>
          </div>

          {/* Dose details */}
          {result.dose_per_kg && (
            <div className="pt-2 border-t border-white/10 grid grid-cols-2 gap-2 text-xs text-white/60">
              <div>Dose/kg: <span className="text-white/90 font-medium">{result.dose_per_kg}</span></div>
              <div>Total dose: <span className="text-white/90 font-medium">{result.total_dose}</span></div>
              <div>Frequency: <span className="text-white/90 font-medium">{result.frequency}</span></div>
              <div>Route: <span className="text-white/90 font-medium">{result.route}</span></div>
            </div>
          )}

          {/* Listen button */}
          <button
            onClick={speakResult}
            disabled={audioLoading}
            className="w-full px-4 py-2 bg-indigo-500/80 hover:bg-indigo-400 text-white rounded-xl text-sm font-medium transition disabled:opacity-50"
          >
            {audioLoading ? '⏳ Loading...' : '🔊 Listen / শুনুন'}
          </button>
        </div>
      )}
    </div>
  )
}