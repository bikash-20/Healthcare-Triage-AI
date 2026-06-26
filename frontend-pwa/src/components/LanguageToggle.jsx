import React from 'react'
import { useLanguage } from '../LanguageContext'
import { t } from '../i18n'

/**
 * Compact Bangla ⇄ English switcher. The visible label is rendered in *the
 * opposite* script so users can see what they'll get when they tap it.
 */
export default function LanguageToggle({ className = '' }) {
  const { lang, toggle } = useLanguage()
  const next = lang === 'en' ? 'bn' : 'en'
  const label = next === 'en' ? t('lang.toggle_to_en', lang) : t('lang.toggle_to_bn', lang)

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch language to ${label}`}
      className={`btn-glass px-4 py-2 text-xs sm:text-sm font-semibold flex items-center gap-2 ${className}`}
    >
      <span aria-hidden="true" className="text-base">
        🌐
      </span>
      <span className="tracking-wide">{label}</span>
    </button>
  )
}