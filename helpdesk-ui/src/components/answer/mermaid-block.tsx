"use client"

import * as React from "react"
import { useTheme } from "next-themes"
import { cn } from "@/lib/utils"

let mermaidInitialized = false
let mermaidPromise: Promise<typeof import("mermaid").default> | null = null

function getMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then((m) => m.default)
  }
  return mermaidPromise
}

export interface MermaidBlockProps {
  code: string
  className?: string
}

export function MermaidBlock({ code, className }: MermaidBlockProps) {
  const { resolvedTheme } = useTheme()
  const ref = React.useRef<HTMLDivElement>(null)
  const [error, setError] = React.useState<string | null>(null)
  const idRef = React.useRef(`mmd-${Math.random().toString(36).slice(2, 10)}`)

  React.useEffect(() => {
    let cancelled = false
    setError(null)
    getMermaid()
      .then(async (mermaid) => {
        const isDark = resolvedTheme === "dark"
        const themeName: "default" | "dark" = isDark ? "dark" : "default"
        if (!mermaidInitialized) {
          mermaid.initialize({
            startOnLoad: false,
            theme: themeName,
            securityLevel: "loose",
            fontFamily:
              "Geist, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          })
          mermaidInitialized = true
        } else {
          mermaid.initialize({ startOnLoad: false, theme: themeName, securityLevel: "loose" })
        }
        try {
          await mermaid.parse(code)
        } catch (err) {
          if (cancelled) return
          setError(err instanceof Error ? err.message : "Mermaid parse error")
          return
        }
        try {
          const { svg } = await mermaid.render(idRef.current, code)
          if (cancelled) return
          if (ref.current) {
            ref.current.innerHTML = svg
            const svgEl = ref.current.querySelector("svg")
            if (svgEl) {
              svgEl.removeAttribute("width")
              svgEl.removeAttribute("height")
              svgEl.setAttribute("style", "max-width:100%;height:auto;")
            }
          }
        } catch (err) {
          if (cancelled) return
          setError(err instanceof Error ? err.message : "Mermaid render error")
        }
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : "Failed to load mermaid")
      })
    return () => {
      cancelled = true
    }
  }, [code, resolvedTheme])

  return (
    <figure
      className={cn(
        "my-4 overflow-hidden rounded-xl border border-border bg-card/60 p-4 shadow-card",
        className,
      )}
    >
      {error ? (
        <div className="rounded-md border border-danger/30 bg-danger/10 p-3 text-xs text-danger">
          <p className="font-medium">Diagram could not be rendered</p>
          <p className="mt-1 font-mono whitespace-pre-wrap">{error}</p>
        </div>
      ) : (
        <div
          ref={ref}
          className="mermaid flex w-full justify-center [&_svg]:max-w-full [&_svg]:h-auto"
        />
      )}
    </figure>
  )
}
