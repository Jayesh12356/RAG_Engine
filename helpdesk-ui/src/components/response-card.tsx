import { QueryResponse } from '@/types'
import { ConfidenceGauge } from './confidence-gauge'
import { SourceAccordion } from './source-accordion'
import { AlertTriangle } from 'lucide-react'

export function ResponseCard({ response }: { response: QueryResponse }) {
  const isRefused = response.refused

  return (
    <div className="card p-6 flex flex-col gap-5 relative overflow-hidden">
      {/* Subtle top accent line */}
      <div className="absolute top-0 left-0 right-0 h-[2px]" style={{ background: 'var(--accent-gradient)' }} />

      {/* Header row */}
      <div className="flex items-start justify-between gap-4 pt-1">
        <div className="flex-1">
          <div className="flex items-center gap-2.5 mb-1">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">Answer</h2>
            {response.service_category && (
              <span className="badge badge-indigo">{response.service_category}</span>
            )}
          </div>
        </div>
        <ConfidenceGauge confidence={response.confidence} label={response.confidence_label} />
      </div>

      {isRefused ? (
        <div className="flex flex-col gap-3">
          <div className="bg-rose-50/80 border border-rose-200/60 p-4 rounded-xl flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-rose-500 mt-0.5 shrink-0" />
            <p className="text-rose-700 text-sm font-medium">
              I don&apos;t have information on this topic in our documentation.
            </p>
          </div>
          <p className="text-slate-400 text-xs font-medium">No sources available</p>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="prose prose-sm prose-slate max-w-none text-slate-700 whitespace-pre-wrap leading-relaxed">
            {response.answer}
          </div>
          <div>
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Sources</h3>
            <SourceAccordion sources={response.sources} />
          </div>
        </div>
      )}
    </div>
  )
}
