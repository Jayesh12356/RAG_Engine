"use client"

import * as React from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { motion } from "framer-motion"
import { Activity, BadgeDollarSign, Gauge, ShieldX } from "lucide-react"
import { getRecentMetrics, type MetricsRecentItem } from "@/lib/api"
import { cn } from "@/lib/utils"

const POLL_MS = 15_000
const WINDOW_MIN = 60

interface ChartCardProps {
  title: string
  hint?: string
  icon: React.ReactNode
  value?: string
  children: React.ReactNode
}

function ChartCard({ title, hint, icon, value, children }: ChartCardProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-border bg-card/60 p-4 shadow-card"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-md border border-border bg-bg text-primary">
            {icon}
          </span>
          <div>
            <h3 className="text-sm font-semibold text-fg">{title}</h3>
            {hint && <p className="text-[11px] text-muted-fg">{hint}</p>}
          </div>
        </div>
        {value && <span className="font-mono text-sm tabular-nums text-fg">{value}</span>}
      </header>
      <div className="mt-3 h-36">
        <ResponsiveContainer width="100%" height="100%">
          {children as React.ReactElement}
        </ResponsiveContainer>
      </div>
    </motion.section>
  )
}

function formatMinute(value: string): string {
  try {
    const d = new Date(value)
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
  } catch {
    return value
  }
}

interface PreparedPoint extends MetricsRecentItem {
  minute_label: string
  refusal_rate: number
}

function prepare(points: MetricsRecentItem[]): PreparedPoint[] {
  return points.map((p) => ({
    ...p,
    minute_label: formatMinute(p.minute),
    refusal_rate: p.total ? p.refusals / p.total : 0,
  }))
}

export function MetricsGraphs({ className }: { className?: string }) {
  const [points, setPoints] = React.useState<PreparedPoint[]>([])
  const [loading, setLoading] = React.useState(true)

  const refresh = React.useCallback(async () => {
    try {
      const data = await getRecentMetrics(WINDOW_MIN)
      setPoints(prepare(data.points))
    } catch {
      /* swallow — empty chart is acceptable */
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    refresh()
    const id = window.setInterval(refresh, POLL_MS)
    return () => window.clearInterval(id)
  }, [refresh])

  const totals = React.useMemo(() => {
    if (!points.length) return null
    const total = points.reduce((acc, p) => acc + p.total, 0)
    const refusals = points.reduce((acc, p) => acc + p.refusals, 0)
    const cost = points.reduce((acc, p) => acc + p.cost_usd, 0)
    const meanConfidence =
      points.reduce((acc, p) => acc + p.mean_confidence * p.total, 0) /
      Math.max(1, total)
    const latencies = points.map((p) => p.p95_ms).filter((v) => v > 0)
    const peakP95 = latencies.length ? Math.max(...latencies) : 0
    return {
      total,
      refusals,
      cost,
      meanConfidence,
      peakP95,
    }
  }, [points])

  const empty = !loading && (!points.length || totals?.total === 0)

  return (
    <section className={cn("space-y-4", className)}>
      <header className="flex items-end justify-between">
        <div>
          <h2 className="text-base font-semibold tracking-tight text-fg">
            Pipeline performance
          </h2>
          <p className="text-xs text-muted-fg">
            Last {WINDOW_MIN} minutes — refreshing every {POLL_MS / 1000}s.
          </p>
        </div>
        {totals && (
          <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-fg sm:grid-cols-4">
            <span>
              <span className="block uppercase tracking-[0.18em]">Volume</span>
              <span className="text-fg">{totals.total}</span>
            </span>
            <span>
              <span className="block uppercase tracking-[0.18em]">Refusals</span>
              <span className="text-fg">{totals.refusals}</span>
            </span>
            <span>
              <span className="block uppercase tracking-[0.18em]">Avg confidence</span>
              <span className="text-fg">{totals.meanConfidence.toFixed(2)}</span>
            </span>
            <span>
              <span className="block uppercase tracking-[0.18em]">Spend</span>
              <span className="text-fg">${totals.cost.toFixed(4)}</span>
            </span>
          </div>
        )}
      </header>

      {empty ? (
        <p className="rounded-md border border-dashed border-border bg-card/60 p-6 text-center text-sm text-muted-fg">
          No traffic yet. Issue a query or chat message to populate the graphs.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard
            title="Latency p50 / p95"
            hint="Per-minute percentiles, ms"
            icon={<Activity className="h-3.5 w-3.5" />}
            value={
              points.length
                ? `${Math.round(points[points.length - 1]?.p95_ms || 0)} ms p95`
                : undefined
            }
          >
            <LineChart data={points} margin={{ top: 5, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="hsl(var(--border) / 0.2)" strokeDasharray="3 3" />
              <XAxis
                dataKey="minute_label"
                tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }}
                stroke="hsl(var(--border))"
                interval="preserveEnd"
                minTickGap={20}
              />
              <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }} stroke="hsl(var(--border))" />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Line
                dataKey="p50_ms"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="p50"
              />
              <Line
                dataKey="p95_ms"
                stroke="hsl(var(--accent))"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="p95"
              />
            </LineChart>
          </ChartCard>

          <ChartCard
            title="Volume per minute"
            hint="Successful answers"
            icon={<Activity className="h-3.5 w-3.5" />}
          >
            <BarChart data={points} margin={{ top: 5, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="hsl(var(--border) / 0.2)" strokeDasharray="3 3" />
              <XAxis
                dataKey="minute_label"
                tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }}
                stroke="hsl(var(--border))"
                interval="preserveEnd"
                minTickGap={20}
              />
              <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }} stroke="hsl(var(--border))" />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="total" fill="hsl(var(--primary))" />
            </BarChart>
          </ChartCard>

          <ChartCard
            title="Refusal rate"
            hint="Share of refused answers"
            icon={<ShieldX className="h-3.5 w-3.5" />}
          >
            <AreaChart data={points} margin={{ top: 5, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="hsl(var(--border) / 0.2)" strokeDasharray="3 3" />
              <XAxis
                dataKey="minute_label"
                tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }}
                stroke="hsl(var(--border))"
                interval="preserveEnd"
                minTickGap={20}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }}
                stroke="hsl(var(--border))"
                tickFormatter={(v) => `${Math.round(v * 100)}%`}
                domain={[0, 1]}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value) => `${(Number(value ?? 0) * 100).toFixed(1)}%`}
              />
              <Area
                dataKey="refusal_rate"
                stroke="hsl(var(--danger))"
                fill="hsl(var(--danger) / 0.18)"
                strokeWidth={2}
                isAnimationActive={false}
              />
            </AreaChart>
          </ChartCard>

          <ChartCard
            title="Mean confidence"
            hint="Weighted average per minute"
            icon={<Gauge className="h-3.5 w-3.5" />}
          >
            <AreaChart data={points} margin={{ top: 5, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="hsl(var(--border) / 0.2)" strokeDasharray="3 3" />
              <XAxis
                dataKey="minute_label"
                tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }}
                stroke="hsl(var(--border))"
                interval="preserveEnd"
                minTickGap={20}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }}
                stroke="hsl(var(--border))"
                domain={[0, 1]}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value) => Number(value ?? 0).toFixed(2)}
              />
              <Area
                dataKey="mean_confidence"
                stroke="hsl(var(--success))"
                fill="hsl(var(--success) / 0.18)"
                strokeWidth={2}
                isAnimationActive={false}
              />
            </AreaChart>
          </ChartCard>

          <ChartCard
            title="Spend per minute"
            hint="Estimated USD"
            icon={<BadgeDollarSign className="h-3.5 w-3.5" />}
          >
            <BarChart data={points} margin={{ top: 5, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="hsl(var(--border) / 0.2)" strokeDasharray="3 3" />
              <XAxis
                dataKey="minute_label"
                tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }}
                stroke="hsl(var(--border))"
                interval="preserveEnd"
                minTickGap={20}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "hsl(var(--muted-fg))" }}
                stroke="hsl(var(--border))"
                tickFormatter={(v) => `$${(v as number).toFixed(3)}`}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value) => `$${Number(value ?? 0).toFixed(4)}`}
              />
              <Bar dataKey="cost_usd" fill="hsl(var(--accent))" />
            </BarChart>
          </ChartCard>
        </div>
      )}
    </section>
  )
}
