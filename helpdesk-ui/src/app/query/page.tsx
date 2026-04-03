'use client'

import React, { useState } from 'react'
import * as Switch from '@radix-ui/react-switch'
import { Loader2, AlertCircle, Search, Sparkles } from 'lucide-react'
import { postQueryStream } from '@/lib/api'
import { QueryResponse } from '@/types'
import { ResponseCard } from '@/components/response-card'
import { DemoBanner } from '@/components/demo-banner'
import { Skeleton } from '@/components/skeleton'

export default function QueryPage() {
  const [question, setQuestion] = useState("")
  const [service, setService] = useState("GENERAL")
  const [demoMode, setDemoMode] = useState(false)
  
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<QueryResponse | null>(null)
  const [streamAnswer, setStreamAnswer] = useState("")
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!question.trim()) return
    setLoading(true)
    setError(null)
    setResponse(null)
    setStreamAnswer("")
    
    try {
      const res = await postQueryStream(
        question,
        (delta) => setStreamAnswer((prev) => prev + delta),
        service,
        demoMode
      )
      setResponse(res)
    } catch (error) {
      const err = error as Error
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <DemoBanner demoMode={demoMode} />
      
      {/* Page Header (SENTINEL-style) */}
      <div className="page-header mt-8">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-indigo-50 ring-1 ring-indigo-100">
              <Search className="w-5 h-5 text-indigo-500" />
            </div>
            <div>
              <h1 className="page-title">Knowledge Query</h1>
              <p className="page-subtitle">Ask questions about your IT documentation</p>
            </div>
          </div>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start animate-fade-in">
        {/* Left Panel - Query Form */}
        <div className="lg:col-span-5 card p-6 flex flex-col gap-5 lg:sticky lg:top-20">
          {error && (
            <div className="bg-rose-50 text-rose-700 border border-rose-200 p-3 rounded-lg text-sm flex items-start gap-2 animate-fade-in">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Your Question</label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  submit()
                }
              }}
              placeholder="e.g. How do I reset my VPN password?"
              className="input-field min-h-[120px] resize-y"
            />
          </div>
          
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Service Category</label>
            <select
              value={service}
              onChange={(e) => setService(e.target.value)}
              className="input-field cursor-pointer"
            >
              <option value="GENERAL">General</option>
              <option value="VPN">VPN</option>
              <option value="SSL">SSL</option>
              <option value="EMAIL">Email</option>
              <option value="NETWORK">Network</option>
              <option value="OTHER">Other</option>
            </select>
          </div>

          <div className="flex items-center justify-between pt-1">
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

          <button
            type="button"
            onClick={submit}
            disabled={!question.trim() || loading}
            className="btn-primary w-full h-11 mt-1"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Thinking...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                Ask Question
              </span>
            )}
          </button>
        </div>
        
        {/* Right Panel - Response */}
        <div className="lg:col-span-7 flex flex-col">
          {loading ? (
            streamAnswer ? (
              <div className="animate-slide-up">
                <ResponseCard
                  response={{
                    question,
                    answer: streamAnswer,
                    confidence: 0,
                    confidence_label: "low",
                    sources: [],
                    service_category: service,
                    refused: false,
                  }}
                />
              </div>
            ) : (
              <div className="card p-6 flex flex-col gap-5 animate-fade-in">
                <div className="flex items-center justify-between">
                  <Skeleton className="h-7 w-32" />
                  <Skeleton className="h-16 w-24 rounded-xl" />
                </div>
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-4 w-4/6" />
                <div className="space-y-3 mt-2">
                  <Skeleton className="h-12 w-full rounded-lg" />
                  <Skeleton className="h-12 w-full rounded-lg" />
                </div>
              </div>
            )
          ) : response ? (
            <div className="animate-slide-up">
              <ResponseCard response={response} />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center min-h-[400px] card border-dashed">
              <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
                <Sparkles className="w-7 h-7 text-slate-300" />
              </div>
              <p className="text-slate-400 font-medium text-sm">Your answer will appear here</p>
              <p className="text-slate-300 text-xs mt-1">Press Enter or click Ask Question</p>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
