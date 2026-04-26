"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { Loader2, RotateCcw, Save, Settings as SettingsIcon } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { WebhooksPanel } from "@/components/settings/webhooks-panel"
import {
  getSettingsSchema,
  putPreferences,
  type SettingsSchemaField,
  type SettingsSchemaResponse,
} from "@/lib/api"
import { cn } from "@/lib/utils"

type FieldValue = string | number | boolean | null

function formatLabel(key: string): string {
  return key
    .toLowerCase()
    .split("_")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ")
}

function coerce(field: SettingsSchemaField, raw: string): FieldValue {
  if (field.type === "int") {
    const n = Number(raw)
    return Number.isFinite(n) ? Math.trunc(n) : 0
  }
  if (field.type === "float") {
    const n = Number(raw)
    return Number.isFinite(n) ? n : 0
  }
  return raw
}

function valueEquals(a: unknown, b: unknown): boolean {
  if (typeof a === "number" && typeof b === "number") return Math.abs(a - b) < 1e-9
  return a === b
}

export default function SettingsPage() {
  const [schema, setSchema] = React.useState<SettingsSchemaResponse | null>(null)
  const [overrides, setOverrides] = React.useState<Record<string, FieldValue>>({})
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const data = await getSettingsSchema()
      setSchema(data)
      setOverrides(
        Object.fromEntries(
          Object.entries(data.overrides ?? {}).filter(([, v]) => v !== null && v !== undefined),
        ) as Record<string, FieldValue>,
      )
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings")
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void load()
  }, [load])

  const handleChange = React.useCallback(
    (field: SettingsSchemaField, raw: FieldValue) => {
      setOverrides((prev) => {
        const next = { ...prev }
        if (raw === "" || raw === null || valueEquals(raw, field.default)) {
          delete next[field.key]
        } else {
          next[field.key] = raw
        }
        return next
      })
    },
    [],
  )

  const handleReset = React.useCallback(
    (field: SettingsSchemaField) => {
      setOverrides((prev) => {
        const next = { ...prev }
        delete next[field.key]
        return next
      })
    },
    [],
  )

  const handleSave = React.useCallback(async () => {
    setSaving(true)
    try {
      await putPreferences({ settings: overrides })
      toast.success("Settings saved")
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save settings")
    } finally {
      setSaving(false)
    }
  }, [overrides, load])

  const handleResetAll = React.useCallback(async () => {
    setSaving(true)
    try {
      await putPreferences({ settings: {} })
      toast.success("Reverted to defaults")
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not reset")
    } finally {
      setSaving(false)
    }
  }, [load])

  const grouped = React.useMemo(() => {
    if (!schema) return []
    const groups: { title: string; fields: SettingsSchemaField[] }[] = [
      { title: "Generation model", fields: [] },
      { title: "Retrieval", fields: [] },
      { title: "Quality", fields: [] },
      { title: "Caching & UX", fields: [] },
    ]
    for (const f of schema.fields) {
      if (f.key.includes("PROVIDER") || f.key.endsWith("MODEL")) {
        groups[0].fields.push(f)
      } else if (
        f.key.startsWith("MAX_") ||
        f.key.startsWith("RERANK") ||
        f.key.startsWith("MMR") ||
        f.key.startsWith("HYDE") ||
        f.key.startsWith("MULTI_QUERY")
      ) {
        groups[1].fields.push(f)
      } else if (
        f.key.includes("VERIFIER") ||
        f.key.includes("REWRITE") ||
        f.key.includes("COREFERENCE") ||
        f.key.includes("RERANKER")
      ) {
        groups[2].fields.push(f)
      } else {
        groups[3].fields.push(f)
      }
    }
    return groups.filter((g) => g.fields.length > 0)
  }, [schema])

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-3xl px-6 py-8 md:py-12">
        <header className="mb-6 flex items-center gap-3">
          <span className="rounded-md border border-border bg-card/60 p-2">
            <SettingsIcon className="h-5 w-5 text-muted-fg" />
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
            <p className="text-sm text-muted-fg">
              Tweak retrieval, generation, and UX. Changes are scoped to your cookie and apply to every
              new query.
            </p>
          </div>
        </header>

        {error && (
          <div className="mb-6 rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex h-40 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-fg" />
          </div>
        ) : schema ? (
          <div className="space-y-8">
            <WebhooksPanel />

            {grouped.map((group) => (
              <motion.section
                key={group.title}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="rounded-xl border border-border bg-card/60 p-5"
              >
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-fg">
                  {group.title}
                </h2>
                <div className="divide-y divide-border">
                  {group.fields.map((field) => {
                    const overrideVal = overrides[field.key]
                    const isOverridden = overrideVal !== undefined
                    const value =
                      overrideVal !== undefined ? overrideVal : (field.current as FieldValue)
                    return (
                      <div key={field.key} className="flex items-start justify-between gap-4 py-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <Label className="text-sm font-medium">{formatLabel(field.key)}</Label>
                            {isOverridden && (
                              <Badge variant="secondary" className="text-[10px]">
                                Custom
                              </Badge>
                            )}
                          </div>
                          {field.description && (
                            <p className="mt-1 text-xs text-muted-fg">{field.description}</p>
                          )}
                          <p className="mt-1 text-[11px] text-muted-fg/70">
                            Default: <span className="font-mono">{String(field.default)}</span>
                          </p>
                        </div>
                        <div className="flex w-44 shrink-0 items-center gap-2">
                          <FieldControl field={field} value={value} onChange={(v) => handleChange(field, v)} />
                          {isOverridden && (
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => handleReset(field)}
                              aria-label="Reset to default"
                              className="h-8 w-8"
                            >
                              <RotateCcw className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </motion.section>
            ))}

            <div className="sticky bottom-0 -mx-6 flex items-center justify-between border-t border-border bg-bg/80 px-6 py-3 backdrop-blur">
              <div className={cn("text-xs", Object.keys(overrides).length ? "text-fg" : "text-muted-fg")}>
                {Object.keys(overrides).length
                  ? `${Object.keys(overrides).length} override${Object.keys(overrides).length === 1 ? "" : "s"} pending save`
                  : "All defaults"}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleResetAll} disabled={saving}>
                  Reset all
                </Button>
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                  Save changes
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

interface FieldControlProps {
  field: SettingsSchemaField
  value: FieldValue
  onChange: (value: FieldValue) => void
}

function FieldControl({ field, value, onChange }: FieldControlProps) {
  if (field.type === "bool") {
    return (
      <Switch
        checked={Boolean(value)}
        onCheckedChange={(checked) => onChange(checked)}
        aria-label={field.key}
      />
    )
  }
  if (field.type === "enum" && field.enum) {
    return (
      <select
        value={String(value ?? "")}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-border bg-bg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
      >
        {field.enum.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    )
  }
  if (field.type === "int" || field.type === "float") {
    return (
      <Input
        type="number"
        step={field.type === "float" ? "0.01" : "1"}
        value={String(value ?? "")}
        onChange={(e) => onChange(coerce(field, e.target.value))}
        className="h-8 text-sm"
      />
    )
  }
  return (
    <Input
      value={String(value ?? "")}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 text-sm"
    />
  )
}
