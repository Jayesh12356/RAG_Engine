"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Activity,
  FileSearch,
  FilesIcon,
  MessageSquareText,
  Menu,
} from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Wordmark } from "./wordmark"
import { ThemeToggle } from "./theme-toggle"
import { UserMenu } from "./user-menu"
import { cn } from "@/lib/utils"

const NAV = [
  { href: "/app/chat",      label: "Chat",      icon: MessageSquareText },
  { href: "/app/query",     label: "Query",     icon: FileSearch },
  { href: "/app/documents", label: "Documents", icon: FilesIcon },
  { href: "/app/status",    label: "Status",    icon: Activity },
] as const

export function MobileNav() {
  const pathname = usePathname()
  const [open, setOpen] = React.useState(false)

  React.useEffect(() => {
    setOpen(false)
  }, [pathname])

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open menu"
          className="md:hidden"
        >
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="flex w-[280px] flex-col gap-0 p-0 sm:max-w-[280px]">
        <SheetHeader className="border-b border-border p-4">
          <Link href="/app/chat" className="flex items-center gap-2" onClick={() => setOpen(false)}>
            <Wordmark variant="full" />
          </Link>
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">
            Switch between workspace pages and toggle the theme.
          </SheetDescription>
        </SheetHeader>
        <nav className="flex flex-col gap-1 p-2">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname?.startsWith(`${item.href}/`)
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                  active ? "bg-muted text-fg" : "text-muted-fg hover:bg-muted/60 hover:text-fg",
                )}
              >
                <Icon
                  className={cn(
                    "h-[18px] w-[18px]",
                    active ? "text-primary" : "text-muted-fg",
                  )}
                />
                {item.label}
                {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />}
              </Link>
            )
          })}
        </nav>
        <div className="mt-auto flex flex-col gap-3 border-t border-border p-3">
          <div className="flex items-center justify-between rounded-md bg-muted/40 px-2 py-1.5">
            <span className="text-xs font-medium text-muted-fg">Theme</span>
            <ThemeToggle className="h-9 w-9" />
          </div>
          <div className="rounded-md border border-border p-1.5">
            <UserMenu compact={false} />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
