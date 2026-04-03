'use client'

import React, { useEffect, useState, useCallback } from 'react'
import { getDocuments, deleteDocument } from '@/lib/api'
import { DocumentListItem } from '@/types'
import { DocumentList } from '@/components/document-list'
import { UploadForm } from '@/components/upload-form'
import { Loader2, FileText } from 'lucide-react'

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchDocs = useCallback(async () => {
    try {
      const res = await getDocuments()
      setDocuments(res.documents)
      setError(null)
    } catch (error) {
      const err = error as Error
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDocs()
  }, [fetchDocs])

  const handleUploadSuccess = () => {
    fetchDocs()
  }

  const handleDelete = async (id: string) => {
    const previous = [...documents]
    setDocuments(prev => prev.filter(d => d.document_id !== id))
    
    try {
      await deleteDocument(id)
    } catch (error) {
      const err = error as Error
      alert(`Failed to delete document: ${err.message}`)
      setDocuments(previous)
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto mt-8 w-full animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-violet-50 ring-1 ring-violet-100">
            <FileText className="w-5 h-5 text-violet-500" />
          </div>
          <div>
            <h1 className="page-title">Documents</h1>
            <p className="page-subtitle">Upload, manage, and track ingested PDF knowledge bases</p>
          </div>
        </div>
        {documents.length > 0 && (
          <div className="badge badge-indigo py-1 px-3">
            {documents.length} {documents.length === 1 ? 'document' : 'documents'}
          </div>
        )}
      </div>

      <UploadForm onSuccess={handleUploadSuccess} />
      
      {error && (
        <div className="bg-rose-50 text-rose-700 border border-rose-200 p-4 rounded-xl text-sm flex items-start gap-2">
          <span className="font-medium">Error:</span> {error}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center p-16">
          <Loader2 className="w-7 h-7 animate-spin text-indigo-400" />
        </div>
      ) : (
        <DocumentList documents={documents} onDelete={handleDelete} />
      )}
    </div>
  )
}
