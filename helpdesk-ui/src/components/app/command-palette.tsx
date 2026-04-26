"use client"

import * as React from "react"

interface CommandContextValue {
  open: boolean
  setOpen: (open: boolean) => void
  toggle: () => void
}

const CommandContext = React.createContext<CommandContextValue | null>(null)

export function CommandProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false)
  const toggle = React.useCallback(() => setOpen((v) => !v), [])

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        toggle()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [toggle])

  const value = React.useMemo(() => ({ open, setOpen, toggle }), [open, toggle])
  return <CommandContext.Provider value={value}>{children}</CommandContext.Provider>
}

export function useCommand(): CommandContextValue {
  const ctx = React.useContext(CommandContext)
  if (!ctx) {
    return {
      open: false,
      setOpen: () => undefined,
      toggle: () => undefined,
    }
  }
  return ctx
}
