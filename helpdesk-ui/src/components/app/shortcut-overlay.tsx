"use client"

import * as React from "react"
import { Keyboard } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"

interface ShortcutGroup {
  title: string
  items: { keys: string[]; label: string }[]
}

const GROUPS: ShortcutGroup[] = [
  {
    title: "Navigation",
    items: [
      { keys: ["⌘", "K"], label: "Open command palette" },
      { keys: ["G", "Q"], label: "Go to Query" },
      { keys: ["G", "C"], label: "Go to Chat" },
      { keys: ["G", "D"], label: "Go to Documents" },
      { keys: ["G", "S"], label: "Go to Settings" },
    ],
  },
  {
    title: "Composer",
    items: [
      { keys: ["Enter"], label: "Send message" },
      { keys: ["Shift", "Enter"], label: "New line" },
      { keys: ["/"], label: "Open slash menu" },
      { keys: ["⌘", "↑"], label: "Edit last message" },
    ],
  },
  {
    title: "Answer",
    items: [
      { keys: ["C"], label: "Copy answer" },
      { keys: ["R"], label: "Regenerate" },
      { keys: ["B"], label: "Bookmark" },
      { keys: ["S"], label: "Speak / read aloud" },
    ],
  },
  {
    title: "Help",
    items: [{ keys: ["?"], label: "Toggle this overlay" }],
  },
]

function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT"
}

export function ShortcutOverlay() {
  const [open, setOpen] = React.useState(false)

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "?" && !isEditableTarget(e.target)) {
        e.preventDefault()
        setOpen((v) => !v)
      } else if (e.key === "Escape") {
        setOpen(false)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Keyboard className="h-4 w-4 text-primary" /> Keyboard shortcuts
          </DialogTitle>
        </DialogHeader>
        <div className="grid gap-6 sm:grid-cols-2">
          {GROUPS.map((group) => (
            <section key={group.title}>
              <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-fg">
                {group.title}
              </h4>
              <ul className="space-y-1.5">
                {group.items.map((item) => (
                  <li
                    key={item.label}
                    className="flex items-center justify-between gap-3 rounded-md border border-transparent px-2 py-1.5 text-sm hover:border-border hover:bg-muted/40"
                  >
                    <span className="text-muted-fg">{item.label}</span>
                    <span className="flex items-center gap-1">
                      {item.keys.map((k, idx) => (
                        <React.Fragment key={`${item.label}-${idx}`}>
                          <kbd className="inline-flex h-6 min-w-[1.6rem] items-center justify-center rounded border border-border bg-card px-1.5 text-[11px] font-medium text-fg shadow-sm">
                            {k}
                          </kbd>
                          {idx < item.keys.length - 1 && (
                            <span className="text-[11px] text-muted-fg">+</span>
                          )}
                        </React.Fragment>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
