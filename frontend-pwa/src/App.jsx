import React, { useCallback, useState } from 'react'
import InstallBanner from './components/InstallBanner'
import VitalsForm from './components/VitalsForm'
import AudioIntake from './components/AudioIntake'
import GlassCard from './components/GlassCard'
import TriageCard from './components/TriageCard'
import AudioPlayer from './components/AudioPlayer'
import NexoraChatbot from './components/NexoraChatbot'
import DoseCalculator from './components/DoseCalculator'
import LanguageToggle from './components/LanguageToggle'
import { LanguageProvider, useLanguage } from './LanguageContext'
import { t, SUPPORTED_LANGUAGES } from './i18n'

function AppShell() {
  const [triage, setTriage] = useState(null)
  const [vitals, setVitals] = useState({})
  const [pdfLoading, setPdfLoading] = useState(false)
  const { lang } = useLanguage()

  const handleTriageUpdate = useCallback((next) => {
    setTriage(next)
  }, [])

  const handleVitalsChange = useCallback((next) => {
    setVitals(next)
  }, [])

  const generatePDF = useCallback(async () => {
    setPdfLoading(true)
    try {
      const { jsPDF } = await import('jspdf')
      const doc = new jsPDF()
      doc.setFontSize(14)
      doc.text(t('pdf.title', lang), 10, 20)
      doc.setFontSize(10)
      doc.text(JSON.stringify({ vitals, triage }, null, 2), 10, 40)
      const filename = lang === 'bn' ? 'সারসংক্ষেপ.pdf' : 'summary.pdf'
      doc.save(filename)
    } catch (err) {
      console.error('PDF generation failed:', err)
      alert(t('pdf.error', lang))
    } finally {
      setPdfLoading(false)
    }
  }, [lang, vitals, triage])

  const summaryText = triage
    ? `${t('triage.title', lang)}: ${triage.triage_severity || ''}. ${triage.clinical_reasoning || ''}`
    : t('tts.no_data', lang)

  return (
    <div className="min-h-screen w-full p-4 sm:p-6 md:p-8 text-white flex flex-col gap-6">
      <InstallBanner />
      <div className="max-w-7xl mx-auto w-full grid gap-6 xl:grid-cols-[1.4fr_0.9fr]">
        <div className="glass-card p-4 sm:p-6 md:p-8 rounded-2xl sm:rounded-3xl shadow-soft-glow shadow-lg">
          <div className="flex flex-col gap-4 sm:gap-5 lg:flex-row lg:items-end lg:justify-between mb-6">
            <div className="flex-1">
              <h1 className="text-h1 mb-2">{t('app.name', lang)}</h1>
              <p className="text-xs sm:text-sm text-white/70 max-w-2xl leading-relaxed">
                {t('app.tagline', lang)}
              </p>
            </div>
            <div className="flex flex-shrink-0 flex-wrap items-center gap-3 w-full lg:w-auto">
              <GlassCard
                title={t('glass.active_nodes_title', lang)}
                value={t('glass.active_nodes_value', lang)}
                description={t('glass.active_nodes_desc', lang)}
                icon="⚕️"
              />
              <LanguageToggle />
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[1.7fr_1fr] gap-4 sm:gap-6">
            <VitalsForm
              onChange={handleVitalsChange}
              onAnomaly={handleTriageUpdate}
            />
            <div className="space-y-4">
              <AudioIntake
                vitals={vitals}
                onTriageUpdate={handleTriageUpdate}
              />
              <TriageCard triage={triage} />
              <DoseCalculator />
              <AudioPlayer text={summaryText} />
            </div>
          </div>

          <div className="mt-6 sm:mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={generatePDF}
              disabled={pdfLoading}
              className="btn-glass w-full sm:w-auto px-6 py-3 font-medium disabled:opacity-60"
            >
              {pdfLoading ? t('pdf.preparing', lang) : t('pdf.download', lang)}
            </button>
            <p className="text-[11px] text-white/40">
              {SUPPORTED_LANGUAGES.map((l) => l.toUpperCase()).join(' · ')}
            </p>
          </div>
        </div>
        <div className="relative">
          <NexoraChatbot context={{ vitals, triage }} />
        </div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <LanguageProvider>
      <AppShell />
    </LanguageProvider>
  )
}