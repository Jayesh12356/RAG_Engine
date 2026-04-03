'use client'

import React, { useState, useRef } from 'react'
import { UploadCloud, FileText, CheckCircle2, AlertCircle, X } from 'lucide-react'
import * as Switch from '@radix-ui/react-switch'
import { postIngest } from '@/lib/api'
import { IngestResponse } from '@/types'

export function UploadForm({ onSuccess }: { onSuccess: (res: IngestResponse) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [serviceName, setServiceName] = useState("")
  const [demoMode, setDemoMode] = useState(false)
  const [background, setBackground] = useState(false)
  
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<IngestResponse | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
    const dropped = e.dataTransfer.files[0]
    validateAndSetFile(dropped)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (selected) validateAndSetFile(selected)
  }

  const validateAndSetFile = (f: File) => {
    setError(null)
    setResult(null)
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      setError("Only PDF files are supported.")
      return
    }
    setFile(f)
  }

  const submit = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    setResult(null)
    
    try {
      const res = await postIngest(file, serviceName || undefined, background, demoMode)
      setResult(res)
      onSuccess(res)
      setFile(null)
      setServiceName("")
    } catch (error) {
      const err = error as Error
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="card p-6 flex flex-col gap-5">
      {/* Alerts */}
      {error && (
        <div className="bg-rose-50/80 text-rose-700 border border-rose-200/60 p-3.5 rounded-xl flex items-start gap-3 animate-fade-in">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <p className="text-sm font-medium flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-600">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
      
      {result && (
        <div className="bg-emerald-50/80 text-emerald-800 border border-emerald-200/60 p-3.5 rounded-xl flex items-start gap-3 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-semibold mb-0.5">Upload Successful</p>
            {result.status === 'processing' ? (
              <p className="text-emerald-600">Processing in background (Task: {result.task_id})</p>
            ) : (
              <p className="text-emerald-600">Ingested {result.total_pages} pages into {result.total_chunks} chunks for <span className="font-semibold">{result.service_name}</span></p>
            )}
          </div>
        </div>
      )}

      {/* Drop Zone / File Preview */}
      {file ? (
        <div className="flex items-center gap-4 bg-indigo-50/50 border border-indigo-200/50 p-4 rounded-xl animate-fade-in">
          <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center shrink-0">
            <FileText className="w-5 h-5 text-indigo-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-900 truncate">{file.name}</p>
            <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
          <button 
            type="button" 
            onClick={() => setFile(null)}
            className="text-xs font-medium text-slate-500 hover:text-slate-900 bg-white border border-slate-200 px-3 py-1.5 rounded-lg transition-colors"
          >
            Clear
          </button>
        </div>
      ) : (
        <div 
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all duration-200 ${
            isDragOver 
              ? 'border-indigo-400 bg-indigo-50/50 scale-[1.01]' 
              : 'border-slate-200 hover:border-indigo-300 hover:bg-slate-50/50'
          }`}
        >
          <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center">
            <UploadCloud className={`w-6 h-6 transition-colors ${isDragOver ? 'text-indigo-500' : 'text-slate-400'}`} />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-700">Click or drag a PDF here</p>
            <p className="text-xs text-slate-400 mt-0.5">Only PDF files are supported</p>
          </div>
          <input 
            type="file" 
            accept="application/pdf" 
            className="hidden" 
            ref={fileInputRef}
            onChange={handleFileSelect}
          />
        </div>
      )}

      {/* Options Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Service Name Override</label>
          <input 
            type="text" 
            value={serviceName}
            onChange={(e) => setServiceName(e.target.value)}
            placeholder="e.g. VPN"
            className="input-field"
          />
        </div>
        
        <div className="flex flex-col gap-3 justify-end">
          <div className="flex items-center gap-2.5">
            <Switch.Root 
              checked={background} 
              onCheckedChange={setBackground}
              className="toggle-root"
            >
              <Switch.Thumb className="toggle-thumb" />
            </Switch.Root>
            <span className="text-xs font-medium text-slate-500">Run in background</span>
          </div>
          <div className="flex items-center gap-2.5">
            <Switch.Root 
              checked={demoMode} 
              onCheckedChange={setDemoMode}
              className="toggle-root"
            >
              <Switch.Thumb className="toggle-thumb" />
            </Switch.Root>
            <span className="text-xs font-medium text-slate-500">Demo Mode</span>
          </div>
        </div>
      </div>

      <button
        type="button"
        disabled={!file || uploading}
        onClick={submit}
        className="btn-primary w-full h-11"
      >
        {uploading ? (
          <span className="flex items-center gap-2">
            <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
            Uploading...
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <UploadCloud className="w-4 h-4" />
            Upload Document
          </span>
        )}
      </button>
    </div>
  )
}
