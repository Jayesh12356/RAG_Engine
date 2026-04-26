"use client"

import * as React from "react"
import { Command } from "cmdk"
import { useTheme } from "next-themes"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
  Activity,
  ArrowRight,
  ExternalLink,
  Files,
  History,
  Home,
  LogOut,
  MessageSquareText,
  Moon,
  Search,
  Sparkles,
  Sun,
  Upload,
} from "lucide-react"
import { useCommand } from "./command-palette"
import { signOut } from "@/lib/auth"
import { cn } from "@/lib/utils"
import { getDocuments } from "@/lib/api"
import type { DocumentListItem } from "@/types"
import { useBookmarks } from "@/hooks/use-bookmarks"
import { fuzzyScore } from "@/lib/fuzzy"

const RECENT_KEY = "rag_engine.recent_queries"

export function CommandPaletteDialog() {
  const { open, setOpen } = useCommand()
  const router = useRouter()
  const { setTheme, resolvedTheme } = useTheme()
  const [search, setSearch] = React.useState("")
  const [recent, setRecent] = React.useState<string[]>([])
  const [docs, setDocs] = React.useState<DocumentListItem[]>([])
  const { bookmarks } = useBookmarks()

  React.useEffect(() => {
    if (!open) return
    setSearch("")
    try {
      const raw = window.localStorage.getItem(RECENT_KEY)
      const list = raw ? (JSON.parse(raw) as string[]) : []
      setRecent(Array.isArray(list) ? list.slice(0, 8) : [])
    } catch {
      setRecent([])
    }
    let cancelled = false
    getDocuments()
      .then((r) => {
        if (!cancelled) setDocs(r.documents.slice(0, 30))
      })
      .catch(() => {
        if (!cancelled) setDocs([])
      })
    return () => {
      cancelled = true
    }
  }, [open])

  React.useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, setOpen])

  const go = (url: string) => {
    setOpen(false)
    router.push(url)
  }

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark")
    setOpen(false)
  }

  const onSignOut = () => {
    signOut()
    setOpen(false)
    router.push("/")
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="cmd-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[100] flex items-start justify-center bg-black/55 px-4 pt-[12vh] backdrop-blur-sm"
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Command palette"
        >
          <motion.div
            key="cmd-shell"
            initial={{ opacity: 0, y: -12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-xl overflow-hidden rounded-xl border border-border bg-card shadow-glow"
            onClick={(e) => e.stopPropagation()}
          >
            <Command
              shouldFilter
              loop
              label="Command palette"
              className="text-fg"
              filter={(value, q) => fuzzyScore(q, value)}
            >
              <div className="flex items-center gap-2 border-b border-border px-3">
                <Search className="h-4 w-4 text-muted-fg" />
                <Command.Input
                  value={search}
                  onValueChange={setSearch}
                  autoFocus
                  placeholder="Type a command or search…"
                  className="h-12 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-muted-fg"
                />
                <kbd className="hidden rounded border border-border bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-fg sm:inline-flex">
                  Esc
                </kbd>
              </div>
              <Command.List className="max-h-[60vh] overflow-y-auto p-1.5">
                <Command.Empty className="py-10 text-center text-sm text-muted-fg">
                  Nothing matches your query.
                </Command.Empty>

                <CommandSection heading="Navigate">
                  <CmdItem
                    icon={<MessageSquareText className="h-4 w-4" />}
                    label="Open Chat"
                    hint="/app/chat"
                    onSelect={() => go("/app/chat")}
                  />
                  <CmdItem
                    icon={<Sparkles className="h-4 w-4" />}
                    label="Ask one-shot Query"
                    hint="/app/query"
                    onSelect={() => go("/app/query")}
                  />
                  <CmdItem
                    icon={<Files className="h-4 w-4" />}
                    label="Manage Documents"
                    hint="/app/documents"
                    onSelect={() => go("/app/documents")}
                  />
                  <CmdItem
                    icon={<Activity className="h-4 w-4" />}
                    label="System Status"
                    hint="/app/status"
                    onSelect={() => go("/app/status")}
                  />
                  <CmdItem
                    icon={<Home className="h-4 w-4" />}
                    label="Marketing site"
                    hint="/"
                    onSelect={() => go("/")}
                  />
                </CommandSection>

                <CommandSection heading="Actions">
                  <CmdItem
                    icon={<Upload className="h-4 w-4" />}
                    label="Upload a document"
                    hint="Documents"
                    onSelect={() => go("/app/documents")}
                  />
                  <CmdItem
                    icon={
                      resolvedTheme === "dark" ? (
                        <Sun className="h-4 w-4" />
                      ) : (
                        <Moon className="h-4 w-4" />
                      )
                    }
                    label={resolvedTheme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
                    hint="Toggle"
                    onSelect={toggleTheme}
                  />
                  <CmdItem
                    icon={<ExternalLink className="h-4 w-4" />}
                    label="Backend health"
                    hint="/app/status"
                    onSelect={() => go("/app/status")}
                  />
                  <CmdItem
                    icon={<LogOut className="h-4 w-4" />}
                    label="Sign out"
                    hint="End session"
                    onSelect={onSignOut}
                  />
                </CommandSection>

                {recent.length > 0 && (
                  <CommandSection heading="Recent queries">
                    {recent.map((q, i) => (
                      <CmdItem
                        key={`${q}-${i}`}
                        icon={<History className="h-4 w-4" />}
                        label={q}
                        onSelect={() => {
                          setOpen(false)
                          router.push(`/app/query?q=${encodeURIComponent(q)}`)
                        }}
                      />
                    ))}
                  </CommandSection>
                )}

                {bookmarks.length > 0 && (
                  <CommandSection heading="Bookmarks">
                    {bookmarks.slice(0, 8).map((b) => (
                      <CmdItem
                        key={b.id}
                        icon={<Sparkles className="h-4 w-4" />}
                        label={b.question}
                        onSelect={() => {
                          setOpen(false)
                          router.push(`/app/query?q=${encodeURIComponent(b.question)}`)
                        }}
                      />
                    ))}
                  </CommandSection>
                )}

                {docs.length > 0 && (
                  <CommandSection heading="Documents">
                    {docs.map((d) => (
                      <CmdItem
                        key={d.document_id}
                        icon={<Files className="h-4 w-4" />}
                        label={d.pdf_name}
                        hint={d.service_name}
                        onSelect={() => {
                          setOpen(false)
                          router.push(
                            `/app/documents?doc=${encodeURIComponent(d.document_id)}`,
                          )
                        }}
                      />
                    ))}
                  </CommandSection>
                )}
              </Command.List>
              <div className="flex items-center justify-between border-t border-border bg-muted/40 px-3 py-2 text-[11px] text-muted-fg">
                <span className="inline-flex items-center gap-1">
                  <kbd className="rounded border border-border bg-card px-1 py-0.5">↑</kbd>
                  <kbd className="rounded border border-border bg-card px-1 py-0.5">↓</kbd>
                  to navigate
                </span>
                <span className="inline-flex items-center gap-1">
                  <kbd className="rounded border border-border bg-card px-1 py-0.5">↵</kbd>
                  to open
                </span>
              </div>
            </Command>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function CommandSection({
  heading,
  children,
}: {
  heading: string
  children: React.ReactNode
}) {
  return (
    <Command.Group
      heading={heading}
      className={cn(
        "px-1.5 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg",
        "[&_[cmdk-group-heading]]:px-1.5 [&_[cmdk-group-heading]]:pb-1.5",
      )}
    >
      {children}
    </Command.Group>
  )
}

function CmdItem({
  icon,
  label,
  hint,
  onSelect,
}: {
  icon: React.ReactNode
  label: string
  hint?: string
  onSelect: () => void
}) {
  return (
    <Command.Item
      value={label}
      onSelect={onSelect}
      className={cn(
        "group flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-2 text-sm normal-case tracking-normal text-fg outline-none transition-colors",
        "data-[selected=true]:bg-muted data-[selected=true]:text-fg",
      )}
    >
      <span className="grid h-7 w-7 place-items-center rounded-md border border-border bg-card text-muted-fg transition-colors group-data-[selected=true]:border-primary/40 group-data-[selected=true]:text-primary">
        {icon}
      </span>
      <span className="flex-1 truncate font-medium">{label}</span>
      {hint && (
        <span className="hidden text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg sm:inline">
          {hint}
        </span>
      )}
      <ArrowRight className="h-3.5 w-3.5 text-muted-fg opacity-0 transition-opacity group-data-[selected=true]:opacity-100" />
    </Command.Item>
  )
}
