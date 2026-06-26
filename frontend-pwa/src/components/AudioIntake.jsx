import React, { useEffect, useRef, useState } from 'react'
import { useLanguage } from '../LanguageContext'
import { t } from '../i18n'

export default function AudioIntake({ onTranscript, onIntake, onTriageUpdate, onError }) {
  const { lang } = useLanguage()
  const [isRecording, setIsRecording] = useState(false)
  const [status, setStatus] = useState(t('audio.idle', lang))
  const [audioBlobUrl, setAudioBlobUrl] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [duration, setDuration] = useState(0)

  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const streamRef = useRef(null)
  const timerRef = useRef(null)
  const startedAtRef = useRef(0)

  useEffect(() => {
    return () => {
      stopStream()
      if (timerRef.current) clearInterval(timerRef.current)
      if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!isRecording) {
      setStatus(t('audio.idle', lang))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

  const stopStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
  }

  const startTimer = () => {
    startedAtRef.current = Date.now()
    setDuration(0)
    timerRef.current = setInterval(() => {
      setDuration(Math.floor((Date.now() - startedAtRef.current) / 1000))
    }, 250)
  }

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  const handleStart = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const mimeType = MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : ''
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      mediaRecorderRef.current = recorder
      audioChunksRef.current = []

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      recorder.onstop = async () => {
        stopTimer()
        const blob = new Blob(audioChunksRef.current, {
          type: mimeType || 'audio/webm',
        })
        if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl)
        setAudioBlobUrl(URL.createObjectURL(blob))
        await sendBlob(blob)
        stopStream()
      }

      recorder.start()
      setIsRecording(true)
      setStatus(t('audio.recording', lang))
      startTimer()
    } catch (err) {
      console.error('Microphone access failed:', err)
      setStatus(t('audio.permission_denied', lang))
      if (onError) onError(err)
    }
  }

  const handleStop = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    setIsRecording(false)
    setStatus(t('audio.processing', lang))
  }

  const sendBlob = async (blob) => {
    setIsProcessing(true)
    setStatus(t('audio.processing', lang))
    try {
      const data = new FormData()
      data.append('audio', blob, 'intake.webm')
      const res = await fetch('/api/audio/intake', { method: 'POST', body: data })
      const payload = await res.json()
      if (!res.ok) {
        throw new Error(payload.error || payload.detail || t('audio.failed', lang))
      }
      setStatus(t('audio.complete', lang))
      if (onTranscript) onTranscript(payload.transcript || '', payload.detected_language || lang)
      if (onIntake) onIntake(payload)
      if (payload.triage && onTriageUpdate) onTriageUpdate(payload.triage)
    } catch (err) {
      console.error('Audio intake error:', err)
      setStatus(err.message || t('audio.failed', lang))
      if (onError) onError(err)
    } finally {
      setIsProcessing(false)
    }
  }

  const formatDuration = (s) => {
    const mins = String(Math.floor(s / 60)).padStart(2, '0')
    const secs = String(s % 60).padStart(2, '0')
    return `${mins}:${secs}`
  }

  return (
    <div className="glass-card p-5 sm:p-6 rounded-3xl border border-white/10 bg-white/5 shadow-soft-glow space-y-4">
      <div>
        <h3 className="text-sm sm:text-base font-semibold text-white/90">
          {t('audio.title', lang)}
        </h3>
        <p className="mt-1 text-xs text-white/60">{t('audio.subtitle', lang)}</p>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <button
          type="button"
          onClick={isRecording ? handleStop : handleStart}
          disabled={isProcessing}
          className={`btn-glass px-5 py-3 text-sm font-medium disabled:opacity-50 ${
            isRecording ? '!bg-red-500/30 !border-red-400/40' : ''
          }`}
        >
          {isProcessing
            ? t('audio.processing', lang)
            : isRecording
            ? t('audio.stop', lang)
            : t('audio.start', lang)}
        </button>
        <span className="text-xs text-white/70">
          {isRecording ? t('audio.duration', lang) : ''} {formatDuration(duration)}
        </span>
      </div>

      <p className="text-xs sm:text-sm text-white/70">{status}</p>

      {audioBlobUrl ? (
        <audio
          src={audioBlobUrl}
          controls
          className="w-full rounded-2xl"
        />
      ) : null}
    </div>
  )
}