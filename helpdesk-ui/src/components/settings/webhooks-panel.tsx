"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { Plus, Send, Trash2, Webhook } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  createWebhook,
  deleteWebhook,
  getWebhooks,
  testWebhook,
  updateWebhook,
  type WebhookListResponse,
  type WebhookSubscriptionItem,
} from "@/lib/api"

const DEFAULT_EVENT = "query.completed"

export function WebhooksPanel() {
  const [data, setData] = React.useState<WebhookListResponse | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [creating, setCreating] = React.useState(false)
  const [event, setEvent] = React.useState(DEFAULT_EVENT)
  const [url, setUrl] = React.useState("")
  const [secret, setSecret] = React.useState("")

  const refresh = React.useCallback(async () => {
    setLoading(true)
    try {
      setData(await getWebhooks())
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not load webhooks")
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void refresh()
  }, [refresh])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) {
      toast.error("URL is required")
      return
    }
    if (!/^https?:\/\//i.test(url.trim())) {
      toast.error("URL must start with http:// or https://")
      return
    }
    setCreating(true)
    try {
      await createWebhook({
        event,
        url: url.trim(),
        secret: secret.trim() || null,
        enabled: true,
      })
      toast.success("Webhook added")
      setUrl("")
      setSecret("")
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add webhook")
    } finally {
      setCreating(false)
    }
  }

  const handleToggle = async (sub: WebhookSubscriptionItem, next: boolean) => {
    try {
      await updateWebhook(sub.id, { enabled: next })
      toast.success(next ? "Webhook enabled" : "Webhook paused")
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update webhook")
    }
  }

  const handleDelete = async (sub: WebhookSubscriptionItem) => {
    try {
      await deleteWebhook(sub.id)
      toast.success("Webhook removed")
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete webhook")
    }
  }

  const handleTest = async (sub: WebhookSubscriptionItem) => {
    const id = toast.loading("Sending test event…")
    try {
      const res = await testWebhook(sub.id)
      toast.success(`Delivered to ${res.delivered} URL${res.delivered === 1 ? "" : "s"}`, { id })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Test failed", { id })
    }
  }

  const events = data?.events ?? ["ingestion.complete", "query.completed", "query.refused"]
  const subscriptions = data?.subscriptions ?? []

  return (
    <motion.section
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="rounded-xl border border-border bg-card/60 p-5"
    >
      <header className="mb-4 flex items-center gap-3">
        <span className="rounded-md border border-border bg-card/60 p-2">
          <Webhook className="h-4 w-4 text-muted-fg" />
        </span>
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-fg">
            Webhooks
          </h2>
          <p className="text-xs text-muted-fg/80">
            Receive a JSON POST when an ingest finishes or a query completes / refuses.
          </p>
        </div>
      </header>

      <form onSubmit={handleCreate} className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-[160px_1fr_140px_auto]">
        <div>
          <Label className="text-xs text-muted-fg">Event</Label>
          <select
            value={event}
            onChange={(e) => setEvent(e.target.value)}
            className="mt-1 h-8 w-full rounded-md border border-border bg-bg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          >
            {events.map((evt) => (
              <option key={evt} value={evt}>
                {evt}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label className="text-xs text-muted-fg">URL</Label>
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/hooks/helpdesk"
            className="mt-1 h-8 text-sm"
          />
        </div>
        <div>
          <Label className="text-xs text-muted-fg">Secret (optional)</Label>
          <Input
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder="signing secret"
            className="mt-1 h-8 text-sm"
          />
        </div>
        <div className="flex items-end">
          <Button type="submit" disabled={creating} className="h-8 px-3">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add
          </Button>
        </div>
      </form>

      <div className="divide-y divide-border rounded-md border border-border">
        {loading ? (
          <div className="px-4 py-6 text-center text-sm text-muted-fg">Loading…</div>
        ) : subscriptions.length === 0 ? (
          <div className="px-4 py-6 text-center text-sm text-muted-fg">
            No webhooks configured yet.
          </div>
        ) : (
          subscriptions.map((sub) => (
            <div key={sub.id} className="flex flex-wrap items-center gap-3 px-3 py-2">
              <Badge variant="secondary" className="text-[10px]">
                {sub.event}
              </Badge>
              <span className="min-w-0 flex-1 truncate text-sm text-fg">{sub.url}</span>
              {sub.secret && (
                <Badge variant="outline" className="text-[10px]">
                  signed
                </Badge>
              )}
              <Switch
                checked={sub.enabled}
                onCheckedChange={(checked) => handleToggle(sub, checked)}
                aria-label="enabled"
              />
              <Button
                size="icon"
                variant="ghost"
                onClick={() => handleTest(sub)}
                aria-label="Send test event"
                className="h-8 w-8"
              >
                <Send className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => handleDelete(sub)}
                aria-label="Delete webhook"
                className="h-8 w-8"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))
        )}
      </div>
    </motion.section>
  )
}
