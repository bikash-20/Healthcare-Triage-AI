import React from 'react'
import { useLanguage } from '../LanguageContext'
import { localizeTriage, t } from '../i18n'

const severityStyles = {
  green: 'border-emerald-400/40 bg-emerald-500/10 text-emerald-100',
  yellow: 'border-amber-400/40 bg-amber-500/10 text-amber-100',
  red: 'border-rose-400/40 bg-rose-500/10 text-rose-100',
  black: 'border-zinc-400/40 bg-zinc-500/20 text-zinc-100',
}

export default function TriageCard({ result }) {
  const { lang } = useLanguage()

  if (!result) {
    return (
      <div className="glass-card p-5 sm:p-6 rounded-3xl border border-white/10 bg-white/5 shadow-soft-glow">
        <h3 className="text-sm sm:text-base font-semibold text-white/90">
          {t('triage.title', lang)}
        </h3>
        <p className="mt-2 text-xs sm:text-sm text-white/60">
          {t('triage.empty', lang)}
        </p>
      </div>
    )
  }

  const severity = (result.severity || result.level || 'green').toLowerCase()
  const localized = localizeTriage(severity, lang)
  const styles = severityStyles[severity] || severityStyles.green
  const differential = result.differential || []
  const reasoning = result.reasoning || t('triage.reasoning_default', lang)

  return (
    <div className={`glass-card p-5 sm:p-6 rounded-3xl border ${styles} shadow-soft-glow space-y-4`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-white/60">
            {t('triage.title', lang)}
          </p>
          <h3 className="mt-1 text-xl sm:text-2xl font-bold text-white">
            {localized.label}
          </h3>
        </div>
        {result.urgency ? (
          <span className="text-xs uppercase tracking-wide text-white/70 px-3 py-1 rounded-full border border-white/20">
            {t('triage.urgency', lang)}: {result.urgency}
          </span>
        ) : null}
      </div>

      <p className="text-sm sm:text-base text-white/85 leading-6 whitespace-pre-line">
        {reasoning}
      </p>

      {Array.isArray(result.alerts) && result.alerts.length > 0 ? (
        <div className="space-y-2">
          <h4 className="text-xs uppercase tracking-wide text-white/60">
            {t('triage.alerts', lang)}
          </h4>
          <ul className="space-y-1 text-sm text-white/80">
            {result.alerts.map((alert, i) => (
              <li key={i} className="flex items-start gap-2">
                <span aria-hidden className="mt-1 h-1.5 w-1.5 rounded-full bg-current" />
                <span>{alert}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {differential.length > 0 ? (
        <div className="space-y-2">
          <h4 className="text-xs uppercase tracking-wide text-white/60">
            {t('triage.differential', lang)}
          </h4>
          <ul className="space-y-1 text-sm text-white/80">
            {differential.map((dx, i) => (
              <li key={i} className="flex items-center justify-between gap-3">
                <span>{dx.condition || dx}</span>
                {dx.probability != null ? (
                  <span className="text-xs text-white/60">
                    {Math.round(Number(dx.probability) * 100)}%
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {result.recommendations ? (
        <div className="space-y-2">
          <h4 className="text-xs uppercase tracking-wide text-white/60">
            {t('triage.recommendations', lang)}
          </h4>
          <p className="text-sm text-white/85 leading-6 whitespace-pre-line">
            {result.recommendations}
          </p>
        </div>
      ) : null}
    </div>
  )
}