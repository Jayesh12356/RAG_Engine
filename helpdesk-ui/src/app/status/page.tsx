'use client'

import React, { useEffect, useState, useCallback } from 'react'
import { getHealth } from '@/lib/api'
import { HealthResponse } from '@/types'
import { Activity, Server, Database, Brain, ArrowDownUp, ShieldCheck, AlertTriangle, RefreshCw } from 'lucide-react'

export default function StatusPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  const checkHealth = useCallback(async () => {
    try {
      const res = await getHealth()
      setHealth(res)
      setError(null)
    } catch (error) {
      const err = error as Error
      setError(err.message)
      setHealth(null)
    } finally {
      setLastChecked(new Date())
    }
  }, [])

  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [checkHealth])

  const isOk = health?.status === "ok" && !error

  const providers = health ? [
    { label: 'LLM Provider', value: health.llm_provider, icon: Brain, color: 'indigo' as const },
    { label: 'Embedding', value: health.embedding_provider, icon: ArrowDownUp, color: 'sky' as const },
    { label: 'Vector DB', value: health.vector_db, icon: Server, color: 'emerald' as const },
    { label: 'Relational DB', value: health.relational_db, icon: Database, color: 'amber' as const },
  ] : []

  const colorMap = {
    indigo: { bg: 'bg-indigo-50', text: 'text-indigo-600', icon: 'text-indigo-400', ring: 'ring-indigo-100', pill: 'badge-indigo' },
    sky:    { bg: 'bg-sky-50',    text: 'text-sky-600',    icon: 'text-sky-400',    ring: 'ring-sky-100',    pill: 'badge-sky' },
    emerald:{ bg: 'bg-emerald-50',text: 'text-emerald-600',icon: 'text-emerald-400',ring: 'ring-emerald-100',pill: 'badge-emerald' },
    amber:  { bg: 'bg-amber-50',  text: 'text-amber-600',  icon: 'text-amber-400',  ring: 'ring-amber-100',  pill: 'badge-amber' },
  }

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto mt-8 w-full animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-emerald-50 ring-1 ring-emerald-100">
            <Activity className="w-5 h-5 text-emerald-500" />
          </div>
          <div>
            <h1 className="page-title">System Status</h1>
            <p className="page-subtitle">Real-time health monitoring for all active providers</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {lastChecked && (
            <span className="text-[11px] text-slate-400 font-medium hidden sm:inline">
              Last checked: {lastChecked.toLocaleTimeString()}
            </span>
          )}
          <button onClick={checkHealth} className="btn-secondary">
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <div className={`badge ${isOk ? 'badge-emerald' : 'badge-rose'} gap-1.5 py-1 px-3`}>
            {isOk ? <ShieldCheck className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
            {isOk ? "Operational" : "Degraded"}
          </div>
        </div>
      </div>

      {/* Provider Cards Grid (SENTINEL-style stat cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {health ? providers.map((p) => {
          const c = colorMap[p.color]
          const Icon = p.icon
          return (
            <div key={p.label} className="stat-card animate-slide-up">
              <div className="flex items-center justify-between">
                <span className="stat-label">{p.label}</span>
                <div className={`stat-icon ${c.bg} ring-1 ${c.ring}`}>
                  <Icon className={`w-[18px] h-[18px] ${c.icon}`} />
                </div>
              </div>
              <div className={`provider-pill ${c.pill} self-start mt-1`}>
                {p.value}
              </div>
            </div>
          )
        }) : (
          Array.from({length: 4}).map((_, i) => (
            <div key={i} className="stat-card">
              <div className="h-5 w-20 bg-slate-100 animate-pulse rounded" />
              <div className="h-8 w-24 bg-slate-100 animate-pulse rounded-full mt-2" />
            </div>
          ))
        )}
      </div>
      
      {/* Demo mode indicator */}
      {health && (
        <div className="card p-5 flex items-center justify-between animate-fade-in">
          <div className="flex items-center gap-3">
            <div className={`w-2.5 h-2.5 rounded-full ${health.demo_mode ? 'bg-amber-400' : 'bg-slate-300'}`} />
            <span className="text-sm font-medium text-slate-700">Demo Mode</span>
          </div>
          <span className={`badge ${health.demo_mode ? 'badge-amber' : 'bg-slate-100 text-slate-500'}`}>
            {health.demo_mode ? 'ON' : 'OFF'}
          </span>
        </div>
      )}

      {error && (
        <div className="bg-rose-50 border border-rose-200 text-rose-700 p-4 rounded-xl flex items-start gap-3 animate-fade-in">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-sm mb-0.5">Connection Error</p>
            <p className="text-sm opacity-80">{error}</p>
          </div>
        </div>
      )}
    </div>
  )
}
