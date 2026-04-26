"use client"

import * as React from "react"
import { Hash, Layers } from "lucide-react"

import { cn } from "@/lib/utils"

export interface SpacesSidebarProps {
  tags: string[]
  selected: string | null
  onSelect: (tag: string | null) => void
  onDropTag: (tag: string, documentId: string) => void
  className?: string
}

export function SpacesSidebar({
  tags,
  selected,
  onSelect,
  onDropTag,
  className,
}: SpacesSidebarProps) {
  return (
    <aside className={cn("flex w-56 shrink-0 flex-col gap-2", className)}>
      <header className="flex items-center gap-2 px-2 text-xs font-semibold uppercase tracking-wide text-muted-fg">
        <Layers className="h-3.5 w-3.5" />
        Spaces
      </header>

      <nav className="flex flex-col gap-1">
        <SpaceRow
          label="All documents"
          icon={<Layers className="h-3.5 w-3.5" />}
          active={selected === null}
          onClick={() => onSelect(null)}
        />
        {tags.length === 0 ? (
          <p className="mx-2 mt-2 rounded-md border border-dashed border-border p-3 text-[11px] text-muted-fg">
            Drop documents on a space (or use the card menu) to organise your corpus.
          </p>
        ) : (
          tags.map((tag) => (
            <SpaceRow
              key={tag}
              label={tag}
              icon={<Hash className="h-3.5 w-3.5" />}
              active={selected?.toLowerCase() === tag.toLowerCase()}
              onClick={() => onSelect(tag)}
              onDropDocument={(docId) => onDropTag(tag, docId)}
            />
          ))
        )}
      </nav>
    </aside>
  )
}

interface SpaceRowProps {
  label: string
  icon: React.ReactNode
  active: boolean
  onClick: () => void
  onDropDocument?: (documentId: string) => void
}

function SpaceRow({ label, icon, active, onClick, onDropDocument }: SpaceRowProps) {
  const [over, setOver] = React.useState(false)

  return (
    <button
      type="button"
      onClick={onClick}
      onDragOver={(e) => {
        if (!onDropDocument) return
        e.preventDefault()
        e.dataTransfer.dropEffect = "copy"
        if (!over) setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        if (!onDropDocument) return
        e.preventDefault()
        setOver(false)
        const id = e.dataTransfer.getData("application/x-document-id")
        if (id) onDropDocument(id)
      }}
      className={cn(
        "flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
        active ? "bg-muted text-fg" : "text-muted-fg hover:bg-muted/60 hover:text-fg",
        over && "border border-dashed border-primary/60 bg-primary/10 text-primary",
      )}
    >
      <span className="grid h-5 w-5 place-items-center text-muted-fg">{icon}</span>
      <span className="truncate">{label}</span>
    </button>
  )
}
