'use client'

import * as Accordion from '@radix-ui/react-accordion'
import { ChevronDown, ExternalLink } from 'lucide-react'
import { SourceChunk } from '@/types'
import { cn } from '@/lib/utils'
import { BASE } from '@/lib/api'

export function SourceAccordion({ sources }: { sources: SourceChunk[] }) {
  if (!sources || sources.length === 0) return null

  const visibleSources = sources.slice(0, 5)
  const buildPdfHref = (source: SourceChunk) => {
    return `${BASE}${source.pdf_url}#page=${source.page_number}`
  }

  return (
    <Accordion.Root type="single" collapsible className="space-y-2">
      {visibleSources.map((source, index) => (
        <Accordion.Item
          key={source.chunk_id || index}
          value={`item-${index}`}
          className="card overflow-hidden group"
        >
          <Accordion.Header className="flex">
            <Accordion.Trigger className="flex flex-1 items-center justify-between px-4 py-3 hover:bg-slate-50/80 transition-colors [&[data-state=open]>div>svg]:rotate-180">
              <div className="flex flex-col items-start gap-0.5">
                <span className="font-medium text-slate-800 text-[13px]">{source.pdf_name} · Page {source.page_number}</span>
                {source.section_title && (
                  <span className="text-[11px] text-slate-400 font-medium">{source.section_title}</span>
                )}
              </div>
              <div className="flex items-center gap-2.5">
                <div className={cn(
                  "badge text-[11px]",
                  source.score >= 0.8 ? "badge-emerald" :
                  source.score >= 0.6 ? "badge-indigo" :
                  "badge-amber"
                )}>
                  {Math.round(source.score * 100)}%
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 transition-transform duration-200" />
              </div>
            </Accordion.Trigger>
          </Accordion.Header>
          <Accordion.Content className="px-4 pb-4 border-t border-slate-100 bg-slate-50/50 text-slate-600 text-sm data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down overflow-hidden">
            <div className="font-mono text-xs bg-white p-3 rounded-lg border border-slate-200/80 mt-3 overflow-x-auto whitespace-pre-wrap leading-relaxed text-slate-600">
              {source.text}
            </div>
            <div className="mt-3 flex justify-end">
              <a
                href={buildPdfHref(source)}
                target="_blank"
                rel="noreferrer"
                className="btn-secondary text-xs py-1.5 px-3 gap-1"
              >
                Open PDF <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </Accordion.Content>
        </Accordion.Item>
      ))}
    </Accordion.Root>
  )
}
