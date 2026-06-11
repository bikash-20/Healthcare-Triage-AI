import React from 'react'
import { motion } from 'framer-motion'

const config = {
  green: {
    border: 'border-green-400/50',
    glow: 'shadow-[0_0_20px_rgba(16,185,129,0.15)]',
    badge: 'bg-green-500 text-white',
    dot: 'bg-green-400'
  },
  yellow: {
    border: 'border-yellow-400/50',
    glow: 'shadow-[0_0_20px_rgba(245,158,11,0.15)]',
    badge: 'bg-yellow-500 text-white',
    dot: 'bg-yellow-400'
  },
  red: {
    border: 'border-red-500/60',
    glow: 'shadow-[0_0_20px_rgba(239,68,68,0.25)]',
    badge: 'bg-red-600 text-white',
    dot: 'bg-red-400'
  },
  black: {
    border: 'border-slate-400/35',
    glow: 'shadow-[0_0_20px_rgba(148,163,184,0.12)]',
    badge: 'bg-slate-800 text-slate-200',
    dot: 'bg-slate-400'
  }
}

export default function TriageCard({ triage }) {
  const level = triage?.triage_severity?.toLowerCase() || 'green'
  const c = config[level] || config.green

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`glass-card p-5 rounded-3xl ${c.border} ${c.glow} transition duration-300`}
    >
      {/* Header */}
      <h4 className="text-xs uppercase tracking-wide text-white/60 mb-3">
        Triage Status
      </h4>

      {/* Bold colored status badge */}
      <div className="flex items-center gap-3 mb-3">
        <span className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-bold uppercase tracking-widest ${c.badge}`}>
          <span className={`w-2 h-2 rounded-full ${c.dot} animate-pulse`}></span>
          {triage?.triage_severity?.toUpperCase() ?? 'GREEN'}
        </span>
      </div>

      {/* Clinical reasoning */}
      <div className="text-sm leading-6 text-white/70">
        {triage?.clinical_reasoning || 'No critical anomalies detected.'}
      </div>

      {/* Differential diagnoses */}
      {triage?.differential_diagnoses?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-white/10">
          <p className="text-xs uppercase tracking-wide text-white/50 mb-2">Differential</p>
          <div className="flex flex-wrap gap-2">
            {triage.differential_diagnoses.map((d, i) => (
              <span key={i} className="text-xs px-2 py-1 rounded-lg bg-white/10 text-white/70">{d}</span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  )
}