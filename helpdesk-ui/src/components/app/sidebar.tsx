"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion } from "framer-motion"
import {
  ChevronLeft,
  FileSearch,
  FilesIcon,
  MessageSquareText,
  Activity,
  Settings as SettingsIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Wordmark } from "./wordmark"
import { UserMenu } from "./user-menu"
import { ThemeToggle } from "./theme-toggle"

const NAV: { href: string; label: string; icon: React.ComponentType<{ className?: string }>; tourKey?: string }[] = [
  { href: "/app/chat",      label: "Chat",      icon: MessageSquareText, tourKey: "nav" },
  { href: "/app/query",     label: "Query",     icon: FileSearch },
  { href: "/app/documents", label: "Documents", icon: FilesIcon },
  { href: "/app/status",    label: "Status",    icon: Activity },
  { href: "/app/settings",  label: "Settings",  icon: SettingsIcon },
]

export function Sidebar() {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = React.useState(false)

  return (
    <aside
      data-tour="sidebar"
      className={cn(
        "relative hidden md:flex shrink-0 flex-col border-r border-border bg-card/60 backdrop-blur-md transition-[width] duration-300 ease-out",
        collapsed ? "w-[64px]" : "w-[244px]",
      )}
    >
      <div className="flex h-14 items-center px-3">
        <Link href="/app/chat" className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted">
          <Wordmark variant={collapsed ? "compact" : "full"} />
        </Link>
      </div>

      <TooltipProvider delayDuration={200}>
        <nav className="px-2.5 mt-2 flex flex-col gap-1">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname?.startsWith(`${item.href}/`)
            const Icon = item.icon
            const tourAttr = item.tourKey ? { "data-tour": item.tourKey } : {}
            const inner = (
              <Link
                href={item.href}
                {...tourAttr}
                className={cn(
                  "group relative flex items-center gap-2.5 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                  active ? "text-fg" : "text-muted-fg hover:text-fg hover:bg-muted/60",
                )}
              >
                {active && (
                  <motion.span
                    layoutId="sidebar-active"
                    className="absolute inset-0 rounded-md bg-muted"
                    transition={{ type: "spring", stiffness: 320, damping: 30 }}
                  />
                )}
                <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center">
                  <Icon
                    className={cn(
                      "h-[18px] w-[18px] transition-colors",
                      active ? "text-primary" : "text-muted-fg group-hover:text-fg",
                    )}
                  />
                </span>
                {!collapsed && <span className="relative z-10">{item.label}</span>}
                {active && !collapsed && (
                  <span className="relative z-10 ml-auto h-1.5 w-1.5 rounded-full bg-primary" />
                )}
              </Link>
            )
            return collapsed ? (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>{inner}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            ) : (
              <React.Fragment key={item.href}>{inner}</React.Fragment>
            )
          })}
        </nav>
      </TooltipProvider>

      <div className="mt-auto flex flex-col gap-2 p-2">
        <div
          className={cn(
            "flex items-center justify-between rounded-md px-1.5 py-1.5",
            collapsed && "flex-col gap-1.5",
          )}
        >
          <ThemeToggle className="h-9 w-9" />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCollapsed((c) => !c)}
            className={cn("h-9 w-9 transition-transform", collapsed && "rotate-180")}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
        <div className="rounded-md border border-border bg-card/60 p-1.5">
          <UserMenu compact={collapsed} />
        </div>
      </div>
    </aside>
  )
}
