"use client"

import * as React from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { cn } from "@/lib/utils"

type ChartType = "bar" | "line" | "pie" | "area"

interface ChartSpec {
  type: ChartType
  title?: string
  xKey?: string
  yKey?: string | string[]
  data: Array<Record<string, number | string>>
  // Pie-specific
  nameKey?: string
  valueKey?: string
}

const PALETTE = [
  "hsl(262 83% 58%)",
  "hsl(280 90% 65%)",
  "hsl(190 95% 50%)",
  "hsl(152 70% 45%)",
  "hsl(38 92% 55%)",
  "hsl(0 84% 60%)",
  "hsl(200 80% 50%)",
  "hsl(310 75% 60%)",
]

function safeParse(source: string): ChartSpec | null {
  try {
    const parsed = JSON.parse(source)
    if (!parsed || typeof parsed !== "object") return null
    if (!("type" in parsed) || !Array.isArray(parsed.data)) return null
    return parsed as ChartSpec
  } catch {
    return null
  }
}

function ChartFallback({ source }: { source: string }) {
  return (
    <pre className="my-3 overflow-x-auto rounded-lg border border-dashed border-border bg-muted/40 p-3 text-[12px] text-muted-fg">
      <code>{source}</code>
    </pre>
  )
}

function ChartFrame({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <figure className="my-4 overflow-hidden rounded-xl border border-border bg-card/60 p-4 shadow-card">
      {title ? (
        <figcaption className="mb-3 text-[12px] font-semibold uppercase tracking-[0.18em] text-muted-fg">
          {title}
        </figcaption>
      ) : null}
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          {children as React.ReactElement}
        </ResponsiveContainer>
      </div>
    </figure>
  )
}

function asArray(v: string | string[] | undefined, fallback: string[] = []): string[] {
  if (!v) return fallback
  return Array.isArray(v) ? v : [v]
}

const AXIS_PROPS = {
  tick: { fill: "hsl(var(--muted-fg))", fontSize: 11 },
  axisLine: { stroke: "hsl(var(--border))" },
  tickLine: { stroke: "hsl(var(--border))" },
} as const

const TOOLTIP_STYLE = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  color: "hsl(var(--fg))",
  fontSize: 12,
} as const

export function ChartBlock({ source, className }: { source: string; className?: string }) {
  const spec = React.useMemo(() => safeParse(source), [source])
  if (!spec) return <ChartFallback source={source} />

  const xKey = spec.xKey || "name"
  const yKeys = asArray(spec.yKey, ["value"])

  if (spec.type === "bar") {
    return (
      <div className={cn(className)}>
        <ChartFrame title={spec.title}>
          <BarChart data={spec.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis dataKey={xKey} {...AXIS_PROPS} />
            <YAxis {...AXIS_PROPS} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "hsl(var(--muted) / 0.45)" }} />
            {yKeys.length > 1 ? <Legend wrapperStyle={{ fontSize: 12 }} /> : null}
            {yKeys.map((k, i) => (
              <Bar key={k} dataKey={k} fill={PALETTE[i % PALETTE.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        </ChartFrame>
      </div>
    )
  }

  if (spec.type === "line") {
    return (
      <div className={cn(className)}>
        <ChartFrame title={spec.title}>
          <LineChart data={spec.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis dataKey={xKey} {...AXIS_PROPS} />
            <YAxis {...AXIS_PROPS} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            {yKeys.length > 1 ? <Legend wrapperStyle={{ fontSize: 12 }} /> : null}
            {yKeys.map((k, i) => (
              <Line
                key={k}
                type="monotone"
                dataKey={k}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        </ChartFrame>
      </div>
    )
  }

  if (spec.type === "area") {
    return (
      <div className={cn(className)}>
        <ChartFrame title={spec.title}>
          <AreaChart data={spec.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis dataKey={xKey} {...AXIS_PROPS} />
            <YAxis {...AXIS_PROPS} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            {yKeys.length > 1 ? <Legend wrapperStyle={{ fontSize: 12 }} /> : null}
            {yKeys.map((k, i) => (
              <Area
                key={k}
                type="monotone"
                dataKey={k}
                stroke={PALETTE[i % PALETTE.length]}
                fill={PALETTE[i % PALETTE.length]}
                fillOpacity={0.2}
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        </ChartFrame>
      </div>
    )
  }

  if (spec.type === "pie") {
    const nameKey = spec.nameKey || spec.xKey || "name"
    const valueKey = spec.valueKey || (typeof spec.yKey === "string" ? spec.yKey : "value")
    return (
      <div className={cn(className)}>
        <ChartFrame title={spec.title}>
          <PieChart>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Pie
              data={spec.data}
              dataKey={valueKey}
              nameKey={nameKey}
              outerRadius={100}
              innerRadius={40}
              paddingAngle={1}
            >
              {spec.data.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Pie>
          </PieChart>
        </ChartFrame>
      </div>
    )
  }

  return <ChartFallback source={source} />
}
