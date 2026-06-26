import React, { useEffect, useState } from 'react'
import { useLanguage } from '../LanguageContext'
import { t } from '../i18n'

export default function InstallBanner() {
  const { lang } = useLanguage()
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [iosVisible, setIosVisible] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return

    const dismissedFlag = localStorage.getItem('rht.installDismissed') === '1'
    if (dismissedFlag) setDismissed(true)

    const handleBeforeInstallPrompt = (event) => {
      event.preventDefault()
      setDeferredPrompt(event)
    }

    const isIos =
      /iphone|ipad|ipod/i.test(window.navigator.userAgent) &&
      !window.MSStream
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches
    if (isIos && !isStandalone) setIosVisible(true)

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    }
  }, [])

  const handleInstall = async () => {
    if (!deferredPrompt) return
    deferredPrompt.prompt()
    await deferredPrompt.userChoice
    setDeferredPrompt(null)
    setDismissed(true)
    localStorage.setItem('rht.installDismissed', '1')
  }

  const handleDismiss = () => {
    setDismissed(true)
    localStorage.setItem('rht.installDismissed', '1')
  }

  if (dismissed || (!deferredPrompt && !iosVisible)) return null

  return (
    <div className="glass-card border border-white/10 bg-white/5 rounded-3xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shadow-soft-glow">
      <div>
        <p className="text-sm font-semibold text-white/90">{t('install.title', lang)}</p>
        {iosVisible ? (
          <p className="mt-1 text-xs text-white/60">{t('install.body_ios', lang)}</p>
        ) : (
          <p className="mt-1 text-xs text-white/60">{t('install.body_android', lang)}</p>
        )}
      </div>
      <div className="flex items-center gap-2">
        {deferredPrompt ? (
          <button
            type="button"
            onClick={handleInstall}
            className="btn-glass px-4 py-2 text-xs font-medium"
          >
            {t('install.install', lang)}
          </button>
        ) : null}
        <button
          type="button"
          onClick={handleDismiss}
          className="btn-glass px-4 py-2 text-xs"
        >
          {t('install.later', lang)}
        </button>
      </div>
    </div>
  )
}
