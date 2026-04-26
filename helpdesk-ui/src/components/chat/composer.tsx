"use client"

import * as React from "react"
import { Mic, MicOff, Paperclip, SendHorizonal, Sparkles, Wand2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"
import { useSpeechRecognition } from "@/hooks/use-speech-recognition"

type SlashCommandKind = "action" | "directive"

interface SlashCommandSpec {
  name: string
  description: string
  kind: SlashCommandKind
  /** Server-side instruction prepended to the question (only for kind === "directive"). */
  directive?: string
  /** Placeholder shown when the user types the bare command (only for directives). */
  placeholder?: string
  /** Action id forwarded to onSlash (only for kind === "action"). */
  action?: SlashAction
}

const SLASH_COMMANDS: readonly SlashCommandSpec[] = [
  { name: "/clear",      description: "Start a fresh chat",                              kind: "action",    action: "clear" },
  { name: "/upload",     description: "Pick a document to ingest",                       kind: "action",    action: "upload" },
  { name: "/regenerate", description: "Regenerate the previous answer",                  kind: "action",    action: "regenerate" },
  { name: "/bookmark",   description: "Bookmark this question for later",                kind: "action",    action: "bookmark" },
  {
    name: "/summarize",
    description: "Summarize a topic from your corpus",
    kind: "directive",
    directive: "Summarize the following topic using only the documents in the knowledge base. Provide a concise overview followed by 3-5 key bullet points and cite sources.",
    placeholder: "/summarize <topic or document name>",
  },
  {
    name: "/compare",
    description: "Compare two items side by side",
    kind: "directive",
    directive: "Compare the following items based strictly on the documents in the knowledge base. Present a structured comparison table when helpful and cite sources.",
    placeholder: "/compare <thing A> vs <thing B>",
  },
  {
    name: "/extract",
    description: "Extract specific data from sources",
    kind: "directive",
    directive: "Extract the requested information from the documents in the knowledge base. Return a clean structured list or table with citations.",
    placeholder: "/extract <fields or facts to pull out>",
  },
  {
    name: "/translate",
    description: "Translate the answer to another language",
    kind: "directive",
    directive: "Translate the answer to the requested language while preserving meaning, citations, and formatting. Default to English when no language is specified.",
    placeholder: "/translate <language>: <question>",
  },
  {
    name: "/eli5",
    description: "Explain like I'm five",
    kind: "directive",
    directive: "Explain the following in plain, friendly language suitable for a beginner (ELI5). Avoid jargon, use short sentences, and still cite the sources from the knowledge base.",
    placeholder: "/eli5 <question>",
  },
] as const

export type SlashAction = "clear" | "upload" | "regenerate" | "bookmark"

export interface ComposerSubmitPayload {
  text: string
  directive?: string
  command?: string
}

export interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: (payload?: ComposerSubmitPayload) => void
  onAttach: () => void
  onSlash: (action: SlashAction) => void
  demoMode: boolean
  onDemoToggle: (next: boolean) => void
  category: string
  onCategoryChange: (next: string) => void
  disabled?: boolean
  placeholder?: string
}

function parseSlashInput(raw: string): { command: SlashCommandSpec | null; rest: string } {
  const trimmed = raw.trim()
  if (!trimmed.startsWith("/")) return { command: null, rest: trimmed }
  const firstSpace = trimmed.indexOf(" ")
  const head = firstSpace === -1 ? trimmed : trimmed.slice(0, firstSpace)
  const tail = firstSpace === -1 ? "" : trimmed.slice(firstSpace + 1).trim()
  const match = SLASH_COMMANDS.find((c) => c.name === head.toLowerCase())
  return { command: match ?? null, rest: tail }
}

const CATEGORIES = ["GENERAL", "VPN", "SSL", "EMAIL", "NETWORK", "OTHER"] as const

export function Composer({
  value,
  onChange,
  onSubmit,
  onAttach,
  onSlash,
  demoMode,
  onDemoToggle,
  category,
  onCategoryChange,
  disabled = false,
  placeholder = "Ask anything across your documents… use / for commands",
}: ComposerProps) {
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)
  const [showSlash, setShowSlash] = React.useState(false)

  React.useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = "auto"
    ta.style.height = `${Math.min(ta.scrollHeight, 220)}px`
  }, [value])

  React.useEffect(() => {
    const trimmed = value.trim()
    if (!trimmed.startsWith("/")) {
      setShowSlash(false)
      return
    }
    // Show suggestions only while typing the command head, before any space.
    setShowSlash(!trimmed.includes(" "))
  }, [value])

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      maybeSubmit()
    }
  }

  const maybeSubmit = () => {
    const trimmed = value.trim()
    if (!trimmed) return

    const parsed = parseSlashInput(trimmed)
    const cmd = parsed.command

    if (cmd?.kind === "action") {
      // Action commands: forward the action and stop.
      onSlash(cmd.action!)
      return
    }

    if (cmd?.kind === "directive") {
      // Directive commands: strip the leading command, prepend the directive.
      const userText = parsed.rest
      if (!userText) {
        // Bare directive without a topic — keep the user editing.
        onChange(cmd.placeholder ?? `${cmd.name} `)
        return
      }
      onSubmit({
        text: userText,
        directive: cmd.directive,
        command: cmd.name,
      })
      return
    }

    onSubmit({ text: trimmed })
  }

  const filteredCommands = React.useMemo(() => {
    const head = value.trim().toLowerCase()
    if (!head) return SLASH_COMMANDS.slice(0, 6)
    return SLASH_COMMANDS.filter((c) => c.name.startsWith(head))
  }, [value])

  const baseValueRef = React.useRef("")
  const speech = useSpeechRecognition({
    onPartial: (partial) => {
      const base = baseValueRef.current
      const next = base ? `${base.replace(/\s+$/, "")} ${partial}` : partial
      onChange(next)
    },
    onFinal: (final) => {
      const base = baseValueRef.current
      const next = base ? `${base.replace(/\s+$/, "")} ${final}` : final
      onChange(next.trim())
      baseValueRef.current = next.trim()
    },
    onError: (err) => {
      if (err && err !== "no-speech" && err !== "aborted") {
        toast.error(`Voice input failed: ${err}`)
      }
    },
  })

  const handleMicClick = () => {
    if (!speech.supported) {
      toast.message("Voice input is not supported in this browser")
      return
    }
    if (speech.listening) {
      speech.stop()
    } else {
      baseValueRef.current = value
      speech.start()
    }
  }

  return (
    <div
      data-tour="composer"
      className={cn(
        "relative p-3",
        "md:static md:p-3",
        "sticky bottom-0 z-30 -mx-3 px-3 pb-[max(env(safe-area-inset-bottom),0.75rem)] pt-2",
        "bg-gradient-to-t from-bg via-bg/95 to-transparent backdrop-blur-md md:bg-none md:backdrop-blur-0",
      )}
    >
      <div
        className={cn(
          "relative rounded-2xl border border-border bg-card/85 shadow-card backdrop-blur-md transition-shadow",
          "focus-within:border-primary/50 focus-within:shadow-glow",
        )}
      >
        {showSlash && filteredCommands.length > 0 && (
          <div className="absolute bottom-full left-2 right-2 mb-2 overflow-hidden rounded-md border border-border bg-card shadow-card">
            <ul className="max-h-64 overflow-y-auto text-sm">
              {filteredCommands.map((c) => (
                <li
                  key={c.name}
                  className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2 hover:bg-muted"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    if (c.kind === "action") {
                      onSlash(c.action!)
                      onChange("")
                      return
                    }
                    onChange(c.name + " ")
                    textareaRef.current?.focus()
                  }}
                >
                  <span className="font-mono text-xs text-primary">{c.name}</span>
                  <span className="text-xs text-muted-fg">{c.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <textarea
          ref={textareaRef}
          value={value}
          rows={1}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKey}
          disabled={disabled}
          placeholder={placeholder}
          className={cn(
            "block w-full resize-none bg-transparent px-4 pt-3 pb-1 text-[15px] leading-relaxed text-fg outline-none",
            "placeholder:text-muted-fg",
            "disabled:cursor-not-allowed disabled:opacity-60",
          )}
        />

        <div className="flex flex-wrap items-center gap-3 border-t border-border/60 px-3 pt-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onAttach}
            disabled={disabled}
            className="text-muted-fg"
          >
            <Paperclip className="h-3.5 w-3.5" />
            Attach
          </Button>

          {speech.supported && (
            <Button
              type="button"
              variant={speech.listening ? "primary" : "ghost"}
              size="sm"
              onClick={handleMicClick}
              disabled={disabled}
              className={cn(
                "text-muted-fg",
                speech.listening && "text-primary-fg",
              )}
              aria-label={speech.listening ? "Stop voice input" : "Start voice input"}
              aria-pressed={speech.listening}
            >
              {speech.listening ? (
                <>
                  <MicOff className="h-3.5 w-3.5" />
                  Listening…
                </>
              ) : (
                <>
                  <Mic className="h-3.5 w-3.5" />
                  Voice
                </>
              )}
            </Button>
          )}

          <div className="hidden sm:flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg">
              Category
            </span>
            <select
              value={category}
              onChange={(e) => onCategoryChange(e.target.value)}
              disabled={disabled}
              className="h-7 rounded-md border border-border bg-card px-2 text-[12px] text-fg outline-none transition-colors hover:border-ring focus-visible:ring-2 focus-visible:ring-ring"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c.charAt(0) + c.slice(1).toLowerCase()}
                </option>
              ))}
            </select>
          </div>

          <div className="hidden md:flex items-center gap-2">
            <Switch checked={demoMode} onCheckedChange={onDemoToggle} aria-label="Demo mode" />
            <span className="text-xs font-medium text-muted-fg">Demo</span>
          </div>

          <span className="ml-auto hidden items-center gap-1 text-xs text-muted-fg lg:inline-flex">
            <Sparkles className="h-3 w-3 text-primary" />
            <Kbd>↵</Kbd> to send • <Kbd>⇧</Kbd>+<Kbd>↵</Kbd> for newline
          </span>

          <Button
            type="button"
            onClick={maybeSubmit}
            disabled={disabled || !value.trim()}
            size="sm"
            className="h-8 px-3"
            aria-label="Send"
          >
            <SendHorizonal className="h-3.5 w-3.5" />
            Send
          </Button>
        </div>

        <div className="pointer-events-none absolute -top-2 right-4 hidden md:flex h-4 items-center gap-1 rounded-full bg-card px-2 text-[11px] font-medium text-muted-fg ring-1 ring-border">
          <Wand2 className="h-2.5 w-2.5 text-primary" /> Auto-grow
        </div>
      </div>
    </div>
  )
}
