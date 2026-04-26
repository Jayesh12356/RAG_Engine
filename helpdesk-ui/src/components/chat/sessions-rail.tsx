"use client"

import { motion } from "framer-motion"
import { MessageSquarePlus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { cn, formatRelativeTime, truncate } from "@/lib/utils"
import type { SessionSummary } from "@/types"

export interface SessionsRailProps {
  sessions: SessionSummary[]
  activeId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
  onDelete: (id: string) => void
  className?: string
  showShell?: boolean
}

export function SessionsRail({
  sessions,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  className,
  showShell = true,
}: SessionsRailProps) {
  const Wrapper: React.ElementType = showShell ? "aside" : "div"
  return (
    <Wrapper
      className={cn(
        showShell &&
          "hidden h-full w-[280px] shrink-0 flex-col border-r border-border bg-card/50 backdrop-blur-md md:flex",
        !showShell && "flex h-full w-full flex-col",
        className,
      )}
    >
      <div className="flex items-center justify-between p-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg">
          Sessions
        </span>
        <Button size="sm" variant="primary" onClick={onNewChat} className="px-2.5">
          <MessageSquarePlus className="h-3.5 w-3.5" />
          New
        </Button>
      </div>
      <ScrollArea className="flex-1 px-2 pb-2">
        {sessions.length === 0 ? (
          <p className="rounded-md border border-dashed border-border bg-card/40 p-4 text-center text-xs text-muted-fg">
            No sessions yet. Ask your first question to start one.
          </p>
        ) : (
          <TooltipProvider delayDuration={350}>
            <ul className="flex flex-col gap-1">
              {sessions.map((s) => {
                const active = s.session_id === activeId
                return (
                  <motion.li
                    key={s.session_id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25 }}
                    className="relative"
                  >
                    <button
                      type="button"
                      onClick={() => onSelect(s.session_id)}
                      className={cn(
                        "group flex w-full flex-col items-start gap-0.5 rounded-md px-3 py-2 text-left transition-colors",
                        active ? "bg-muted text-fg" : "hover:bg-muted/60 text-muted-fg hover:text-fg",
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId="session-active"
                          className="absolute inset-y-1.5 left-0 w-0.5 rounded-r bg-primary"
                          transition={{ type: "spring", stiffness: 320, damping: 30 }}
                        />
                      )}
                      <span className="text-[13px] font-medium leading-tight text-fg">
                        {truncate(s.first_question, 64) || "Untitled"}
                      </span>
                      <span className="text-xs text-muted-fg">
                        {s.turn_count} turn{s.turn_count === 1 ? "" : "s"} • {formatRelativeTime(s.last_active)}
                      </span>
                    </button>
                    <div className="pointer-events-none absolute right-1.5 top-1.5 opacity-0 transition-opacity group-hover:opacity-100 hover:opacity-100 focus-within:opacity-100">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              onDelete(s.session_id)
                            }}
                            className="pointer-events-auto h-6 w-6 text-muted-fg hover:text-danger"
                            aria-label="Delete session"
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="right">Delete session</TooltipContent>
                      </Tooltip>
                    </div>
                  </motion.li>
                )
              })}
            </ul>
          </TooltipProvider>
        )}
      </ScrollArea>
    </Wrapper>
  )
}
