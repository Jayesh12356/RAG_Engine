"use client"

import * as React from "react"
import { Paperclip, SendHorizonal, Sparkles, Wand2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"

const SLASH_COMMANDS = [
  { name: "/clear",   description: "Start a fresh chat" },
  { name: "/upload",  description: "Pick a document to ingest" },
] as const

export type SlashAction = "clear" | "upload"

export interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onAttach: () => void
  onSlash: (action: SlashAction) => void
  demoMode: boolean
  onDemoToggle: (next: boolean) => void
  category: string
  onCategoryChange: (next: string) => void
  disabled?: boolean
  placeholder?: string
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
    setShowSlash(value.trim().startsWith("/") && value.trim().length <= 8)
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
    if (trimmed === "/clear") {
      onSlash("clear")
      return
    }
    if (trimmed === "/upload") {
      onSlash("upload")
      return
    }
    onSubmit()
  }

  return (
    <div data-tour="composer" className="relative p-3">
      <div
        className={cn(
          "relative rounded-2xl border border-border bg-card/85 shadow-card backdrop-blur-md transition-shadow",
          "focus-within:border-primary/50 focus-within:shadow-glow",
        )}
      >
        {showSlash && (
          <div className="absolute bottom-full left-2 right-2 mb-2 overflow-hidden rounded-md border border-border bg-card shadow-card">
            <ul className="text-sm">
              {SLASH_COMMANDS.filter((c) => c.name.startsWith(value.trim())).map((c) => (
                <li
                  key={c.name}
                  className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2 hover:bg-muted"
                  onMouseDown={(e) => {
                    e.preventDefault()
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
