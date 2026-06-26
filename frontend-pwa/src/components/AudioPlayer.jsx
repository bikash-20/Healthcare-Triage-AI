import React, { useEffect, useRef, useState } from 'react'
import { useLanguage } from '../LanguageContext'
import { t } from '../i18n'

export default function AudioPlayer({ text }) {
  const { lang } = useLanguage()
  const [audioUrl, setAudioUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const lastUrlRef = useRef(null)

  useEffect(() => {
    return () => {
      if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current)
    }
  }, [])

  useEffect(() => {
    if (!text || !text.trim()) {
      setAudioUrl(null)
      return
    }

    const controller = new AbortController()
    let cancelled = false

    const loadAudio = async () => {
      setLoading(true)
      setError(null)
      try {
        const params = new URLSearchParams({ q: text.slice(0, 600), lang })
        const res = await fetch(`/api/tts/stream?${params}`, { signal: controller.signal })
        if (!res.ok) {
          throw new Error(t('tts.audio_failed', lang))
        }
        const blob = await res.blob()
        if (cancelled) return
        if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current)
        const url = URL.createObjectURL(blob)
        lastUrlRef.current = url
        setAudioUrl(url)
      } catch (err) {
        if (cancelled) return
        if (err.name !== 'AbortError') {
          console.error('TTS error:', err)
          setError(err.message || t('tts.audio_failed', lang))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadAudio()
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [text, lang])

  if (!text || !text.trim()) {
    return (
      <div className="glass-card p-4 rounded-3xl border border-white/10 bg-white/5 text-xs text-white/60">
        {t('tts.no_data', lang)}
      </div>
    )
  }

  return (
    <div className="glass-card p-4 sm:p-5 rounded-3xl border border-white/10 bg-white/5 shadow-soft-glow space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-white/60">
          {t('tts.listen_summary', lang)}
        </span>
        {loading ? (
          <span className="text-xs text-white/60">{t('tts.loading', lang)}…</span>
        ) : null}
      </div>
      {error ? (
        <p className="text-xs text-rose-300/80">{error}</p>
      ) : audioUrl ? (
        <audio src={audioUrl} controls className="w-full" />
      ) : (
        <p className="text-xs text-white/60">{t('tts.loading', lang)}…</p>
      )}
    </div>
  )
}
