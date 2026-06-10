import React, { useState } from 'react'

const detectLanguageFromText = (text) => /[\u0980-\u09FF]/.test(text) ? 'bn' : 'en'
const formatVitals = (vitals) => {
  const lines = []
  if (vitals.bp) lines.push(`Blood Pressure: ${vitals.bp}`)
  if (vitals.hr) lines.push(`Heart Rate: ${vitals.hr} bpm`)
  if (vitals.temp) lines.push(`Temperature: ${vitals.temp} °F`)
  if (vitals.spo2) lines.push(`SpO2: ${vitals.spo2}%`)
  if (vitals.glucose) lines.push(`Blood Glucose: ${vitals.glucose} mg/dL`)
  return lines.join('\n') || 'No vitals available.'
}

const formatTriage = (triage) => {
  if (!triage) return 'No triage data available.'
  return [`Severity: ${triage.triage_severity || 'Unknown'}`, `Reasoning: ${triage.clinical_reasoning || 'N/A'}`].join('\n')
}

const DEFAULT_MODEL = 'cf-llama'

const defaultWelcome = {
  role: 'assistant',
  content: 'Hi, I am NEXORA, your medical AI expert. How may I help you today?\n\nহাই, আমি নেক্সোরা, আপনার মেডিকেল এআই এক্সপার্ট। আজ আপনাকে কীভাবে সাহায্য করতে পারি?'
}

export default function NexoraChatbot({ vitals, triage }) {
  const [messages, setMessages] = useState([defaultWelcome])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(true)

  const handleSend = async () => {
    if (!input.trim()) return
    const userInput = input.trim()
    setInput('')
    const userMessage = { role: 'user', content: userInput }
    setMessages(prev => [...prev, userMessage])
    setLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [userMessage],
          vitals,
          triage,
          model: DEFAULT_MODEL
        })
      })
      const text = await response.text()
      let payload = null
      try {
        payload = text ? JSON.parse(text) : null
      } catch (parseErr) {
        payload = null
      }

      if (!response.ok) {
        const errorMessage = payload?.error || text || 'NEXORA chat failed'
        throw new Error(errorMessage)
      }
      if (!payload || typeof payload !== 'object') {
        throw new Error(text || 'Received unexpected chatbot response')
      }

      const assistantMessage = {
        role: 'assistant',
        content: payload.assistant || 'I could not generate a response. Please try again.'
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  const language = detectLanguageFromText(messages[messages.length - 1]?.content || '')

  return (
    <div className="relative w-full sm:relative sm:bottom-auto sm:z-auto">
      <div className="glass-card border border-white/10 bg-slate-950/90 shadow-soft-glow shadow-lg p-4 rounded-3xl max-w-full sm:max-w-none">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold">NEXORA Chat</h2>
            <p className="text-xs text-white/50">Context-aware medical assistant for the current patient.</p>
          </div>
          <button type="button" onClick={() => setIsOpen(prev => !prev)} className="text-sm text-cyan-300 hover:text-white transition">
            {isOpen ? 'Hide' : 'Show'}
          </button>
        </div>

        {isOpen ? (
          <>
            <div className="glass-card p-4 rounded-3xl border border-white/10 bg-white/5 mb-4 text-sm text-white/70">
              <p className="font-semibold text-white/90 mb-2">Patient Context</p>
              <p>{formatVitals(vitals)}</p>
              <div className="mt-3 border-t border-white/10 pt-3 text-xs text-white/50">
                {formatTriage(triage)}
              </div>
            </div>

            <div className="max-h-[320px] overflow-y-auto space-y-3 mb-4 px-2">
              {messages.map((message, index) => (
                <div key={index} className={message.role === 'assistant' ? 'rounded-3xl bg-slate-900/90 p-4 text-sm text-white shadow-inner' : 'rounded-3xl bg-cyan-500/10 p-4 text-sm text-white/90'}>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-white/40 mb-2">{message.role === 'assistant' ? 'NEXORA' : 'You'}</div>
                  <div className="whitespace-pre-line break-words">{message.content}</div>
                </div>
              ))}
            </div>

            <div className="space-y-3">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={4}
                placeholder={language === 'bn' ? 'আপনার প্রশ্ন লিখুন...' : 'Ask NEXORA a clinical question...'}
                className="w-full resize-none rounded-3xl border border-white/10 bg-slate-950/80 p-4 text-sm text-white placeholder:text-white/40 focus:border-cyan-400 focus:outline-none"
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="btn-glass w-full px-5 py-3 text-sm font-medium disabled:opacity-60"
              >
                {loading ? (language === 'bn' ? 'প্রসেস হচ্ছে...' : 'Processing...') : (language === 'bn' ? 'প্রশ্ন করুন' : 'Ask NEXORA')}
              </button>
            </div>
          </>
        ) : (
          <div className="text-sm text-white/60">Tap show to open NEXORA chat. It will stay aware of patient vitals and triage context.</div>
        )}
      </div>
    </div>
  )
}
