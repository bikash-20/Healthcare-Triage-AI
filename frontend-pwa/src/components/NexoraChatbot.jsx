import React, { useEffect, useRef, useState } from 'react'
import { useLanguage } from '../LanguageContext'
import { isBengali, t } from '../i18n'

export default function NexoraChatbot({ context = {} }) {
  const { lang, setLang } = useLanguage()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [open, setOpen] = useState(false)
  const listRef = useRef(null)

  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          role: 'assistant',
          content: t('chat.welcome', lang),
        },
      ])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages, open])

  const send = async (e) => {
    e?.preventDefault?.()
    const trimmed = input.trim()
    if (!trimmed || sending) return

    const detected = isBengali(trimmed) ? 'bn' : 'en'
    if (detected !== lang) setLang(detected)

    const userMsg = { role: 'user', content: trimmed }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setSending(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: nextMessages,
          context,
          lang: detected,
        }),
      })
      const payload = await res.json()
      if (!res.ok) {
        throw new Error(payload.detail || t('chat.error', lang))
      }
      setMessages([...nextMessages, { role: 'assistant', content: payload.reply || '' }])
    } catch (err) {
      console.error('Chat error:', err)
      setMessages([
        ...nextMessages,
        { role: 'assistant', content: err.message || t('chat.error', lang) },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="btn-glass fixed bottom-5 right-5 z-40 px-4 py-3 text-sm font-medium shadow-soft-glow"
        aria-expanded={open}
      >
        {open ? t('chat.close', lang) : t('chat.open', lang)}
      </button>

      {open ? (
        <div className="fixed bottom-20 right-5 z-40 w-[min(360px,calc(100vw-2.5rem))] glass-card border border-white/10 bg-slate-950/80 backdrop-blur-xl rounded-3xl shadow-soft-glow flex flex-col max-h-[70vh]">
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-sm font-semibold text-white/90">{t('chat.title', lang)}</p>
            <p className="text-[11px] text-white/50">{t('chat.subtitle', lang)}</p>
          </div>

          <div
            ref={listRef}
            className="flex-1 overflow-y-auto px-4 py-3 space-y-3"
          >
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-6 whitespace-pre-line ${
                    m.role === 'user'
                      ? 'bg-cyan-500/20 text-cyan-50 border border-cyan-400/30'
                      : 'bg-white/5 text-white/85 border border-white/10'
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {sending ? (
              <div className="text-xs text-white/50 italic">{t('chat.thinking', lang)}…</div>
            ) : null}
          </div>

          <form onSubmit={send} className="border-t border-white/10 p-3 flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t(`chat.placeholder_${lang}`, lang)}
              className="flex-1 bg-transparent border border-white/20 p-2 rounded-2xl text-sm text-white placeholder:text-white/40"
            />
            <button
              type="submit"
              disabled={sending || !input.trim()}
              className="btn-glass px-3 py-2 text-xs disabled:opacity-50"
            >
              {t('chat.send', lang)}
            </button>
          </form>
        </div>
      ) : null}
    </>
  )
}
