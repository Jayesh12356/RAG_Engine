"use client"

import * as React from "react"
import { Check, Copy } from "lucide-react"
import { useTheme } from "next-themes"
import { cn } from "@/lib/utils"

const SUPPORTED_LANGS = [
  "javascript",
  "typescript",
  "tsx",
  "jsx",
  "json",
  "python",
  "bash",
  "shell",
  "sh",
  "sql",
  "yaml",
  "yml",
  "html",
  "css",
  "markdown",
  "md",
  "go",
  "rust",
  "java",
  "c",
  "cpp",
  "csharp",
  "ruby",
  "php",
  "kotlin",
  "swift",
  "diff",
  "ini",
  "toml",
  "xml",
  "dockerfile",
  "powershell",
  "text",
  "plaintext",
] as const

type ShikiHighlighter = {
  codeToHtml: (code: string, options: { lang: string; theme: string }) => string
}

let highlighterPromise: Promise<ShikiHighlighter> | null = null
function getHighlighter(): Promise<ShikiHighlighter> {
  if (!highlighterPromise) {
    highlighterPromise = import("shiki").then(async ({ createHighlighter }) =>
      createHighlighter({
        themes: ["github-light", "github-dark"],
        langs: SUPPORTED_LANGS as unknown as string[],
      }) as unknown as Promise<ShikiHighlighter>,
    )
  }
  return highlighterPromise
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

export interface CodeBlockProps {
  language: string
  code: string
  className?: string
}

export function CodeBlock({ language, code, className }: CodeBlockProps) {
  const { resolvedTheme } = useTheme()
  const lang = (language || "text").toLowerCase()
  const normalizedLang = (SUPPORTED_LANGS as readonly string[]).includes(lang) ? lang : "text"
  const [html, setHtml] = React.useState<string | null>(null)
  const [copied, setCopied] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    getHighlighter()
      .then((h) => {
        if (cancelled) return
        try {
          const out = h.codeToHtml(code, {
            lang: normalizedLang,
            theme: resolvedTheme === "dark" ? "github-dark" : "github-light",
          })
          setHtml(out)
        } catch {
          setHtml(`<pre><code>${escapeHtml(code)}</code></pre>`)
        }
      })
      .catch(() => {
        if (cancelled) return
        setHtml(`<pre><code>${escapeHtml(code)}</code></pre>`)
      })
    return () => {
      cancelled = true
    }
  }, [code, normalizedLang, resolvedTheme])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div
      className={cn(
        "group relative my-3 overflow-hidden rounded-lg border border-border bg-muted/40 text-[13px]",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border bg-card/60 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg">
        <span>{language || "text"}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-muted-fg transition-colors hover:bg-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Copy code"
        >
          {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
          <span className="hidden sm:inline normal-case tracking-normal">
            {copied ? "Copied" : "Copy"}
          </span>
        </button>
      </div>
      {html ? (
        <div
          className="shiki-wrap overflow-x-auto px-3 py-3 text-[13px] leading-[1.55]"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre className="overflow-x-auto px-3 py-3 text-[13px] leading-[1.55] text-fg">
          <code>{code}</code>
        </pre>
      )}
    </div>
  )
}
