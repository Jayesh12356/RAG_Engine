import React from 'react'
import { Trash2, UploadCloud } from 'lucide-react'
import { DocumentListItem } from '@/types'
import { formatDate } from '@/lib/utils'

export function DocumentList({ 
  documents, 
  onDelete 
}: { 
  documents: DocumentListItem[],
  onDelete: (id: string) => void
}) {
  if (!documents || documents.length === 0) {
    return (
      <div className="card flex flex-col items-center justify-center p-16 text-center">
        <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
          <UploadCloud className="w-7 h-7 text-slate-300" />
        </div>
        <p className="text-sm font-semibold text-slate-500">No documents ingested yet</p>
        <p className="text-xs text-slate-400 mt-1">Upload a PDF above to get started</p>
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/60">
              <th className="px-5 py-3.5 text-[11px] font-semibold text-slate-400 uppercase tracking-widest">PDF Name</th>
              <th className="px-5 py-3.5 text-[11px] font-semibold text-slate-400 uppercase tracking-widest">Service</th>
              <th className="px-5 py-3.5 text-[11px] font-semibold text-slate-400 uppercase tracking-widest">Pages</th>
              <th className="px-5 py-3.5 text-[11px] font-semibold text-slate-400 uppercase tracking-widest">Chunks</th>
              <th className="px-5 py-3.5 text-[11px] font-semibold text-slate-400 uppercase tracking-widest">Ingested</th>
              <th className="px-5 py-3.5 text-[11px] font-semibold text-slate-400 uppercase tracking-widest text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.document_id} className="border-b border-slate-100/80 last:border-0 hover:bg-slate-50/50 transition-colors group">
                <td className="px-5 py-3.5 font-medium text-slate-900 text-[13px]">{doc.pdf_name}</td>
                <td className="px-5 py-3.5">
                  <span className="badge badge-indigo">{doc.service_name}</span>
                </td>
                <td className="px-5 py-3.5 text-slate-500 text-[13px]">{doc.total_pages}</td>
                <td className="px-5 py-3.5 text-slate-500 text-[13px]">{doc.total_chunks}</td>
                <td className="px-5 py-3.5 text-slate-500 text-[13px] whitespace-nowrap">{formatDate(doc.created_at)}</td>
                <td className="px-5 py-3.5 text-right">
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm(`Are you sure you want to delete ${doc.pdf_name}?`)) {
                        onDelete(doc.document_id)
                      }
                    }}
                    className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
