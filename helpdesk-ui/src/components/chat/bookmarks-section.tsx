"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { BookmarkX, Star, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { useBookmarks } from "@/hooks/use-bookmarks"
import { cn, formatRelativeTime, truncate } from "@/lib/utils"

export interface BookmarksSectionProps {
  onPick?: (question: string) => void
  className?: string
}

export function BookmarksSection({ onPick, className }: BookmarksSectionProps) {
  const { bookmarks, removeBookmark, clearBookmarks } = useBookmarks()
  const [open, setOpen] = React.useState(false)

  if (bookmarks.length === 0) return null

  return (
    <div className={cn("flex flex-col gap-1 border-t border-border/60 pt-2", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg hover:text-fg"
        aria-expanded={open}
      >
        <span className="inline-flex items-center gap-1.5">
          <Star className="h-3 w-3 text-primary" />
          Bookmarks
          <span className="ml-1 rounded-full bg-muted px-1.5 text-[10px] text-muted-fg">
            {bookmarks.length}
          </span>
        </span>
        <span className="text-[11px] text-muted-fg">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <TooltipProvider delayDuration={300}>
          <ul className="flex flex-col gap-1">
            {bookmarks.map((b) => (
              <motion.li
                key={b.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.18 }}
                className="group relative"
              >
                <button
                  type="button"
                  onClick={() => onPick?.(b.question)}
                  className="flex w-full flex-col items-start gap-0.5 rounded-md px-3 py-1.5 text-left text-muted-fg transition-colors hover:bg-muted/60 hover:text-fg"
                >
                  <span className="text-[12px] font-medium leading-tight text-fg">
                    {truncate(b.question, 60)}
                  </span>
                  <span className="text-[10px] text-muted-fg">
                    {formatRelativeTime(b.createdAt)}
                  </span>
                </button>
                <div className="absolute right-1.5 top-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          removeBookmark(b.id)
                        }}
                        className="h-5 w-5 text-muted-fg hover:text-danger"
                        aria-label="Remove bookmark"
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="right">Remove</TooltipContent>
                  </Tooltip>
                </div>
              </motion.li>
            ))}
          </ul>
          {bookmarks.length > 0 && (
            <button
              type="button"
              onClick={clearBookmarks}
              className="mx-3 mt-1 inline-flex items-center gap-1 self-start text-[10px] text-muted-fg/80 hover:text-danger"
            >
              <BookmarkX className="h-3 w-3" />
              Clear bookmarks
            </button>
          )}
        </TooltipProvider>
      )}
    </div>
  )
}
