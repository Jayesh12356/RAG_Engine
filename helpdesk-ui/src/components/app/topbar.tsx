"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Search, Sparkles, ChevronRight } from "lucide-react"
import { Kbd } from "@/components/ui/kbd"
import { Button } from "@/components/ui/button"
import { useCommand } from "@/components/app/command-palette"
import { MobileNav } from "@/components/app/mobile-nav"
import { cn } from "@/lib/utils"

const SEGMENT_LABEL: Record<string, string> = {
  app: "Workspace",
  chat: "Chat",
  query: "Query",
  documents: "Documents",
  status: "Status",
}

export function Topbar({ children }: { children?: React.ReactNode }) {
  const pathname = usePathname() ?? ""
  const router = useRouter()
  const segments = pathname.split("/").filter(Boolean)
  const cmd = useCommand()

  const [searchValue, setSearchValue] = React.useState("")

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchValue.trim()) return
    router.push(`/app/query?q=${encodeURIComponent(searchValue.trim())}`)
  }

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg/80 px-4 backdrop-blur-xl">
      <MobileNav />
      <nav aria-label="Breadcrumb" className="hidden md:flex items-center gap-1.5 text-[13px] text-muted-fg">
        {segments.map((seg, i) => {
          const href = "/" + segments.slice(0, i + 1).join("/")
          const label = SEGMENT_LABEL[seg] ?? seg
          const active = i === segments.length - 1
          return (
            <React.Fragment key={href}>
              {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-muted-fg/60" />}
              <Link
                href={href}
                className={cn(
                  "rounded px-1.5 py-0.5 transition-colors",
                  active ? "text-fg" : "hover:text-fg",
                )}
              >
                {label}
              </Link>
            </React.Fragment>
          )
        })}
      </nav>

      <div className="flex-1" />

      <form onSubmit={handleSearchSubmit} className="relative hidden lg:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-fg" />
        <input
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          placeholder="Search documents…"
          className={cn(
            "h-10 w-[280px] rounded-md border border-border bg-card pl-9 pr-3 text-sm outline-none transition-all",
            "placeholder:text-muted-fg",
            "focus:border-ring focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-bg",
          )}
        />
      </form>

      <Button
        variant="secondary"
        size="sm"
        onClick={() => cmd.setOpen(true)}
        className="hidden sm:inline-flex gap-2 text-muted-fg"
      >
        <Sparkles className="h-3.5 w-3.5" />
        Quick action
        <span className="flex items-center gap-1">
          <Kbd>⌘</Kbd>
          <Kbd>K</Kbd>
        </span>
      </Button>

      <div className="flex items-center gap-2">{children}</div>
    </header>
  )
}
