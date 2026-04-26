"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { GitBranch, MessageSquarePlus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { BookmarksSection } from "@/components/chat/bookmarks-section"
import { cn, formatRelativeTime, truncate } from "@/lib/utils"
import type { SessionSummary } from "@/types"

export interface SessionsRailProps {
  sessions: SessionSummary[]
  activeId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
  onDelete: (id: string) => void
  onPickBookmark?: (question: string) => void
  className?: string
  showShell?: boolean
}

interface SessionNode extends SessionSummary {
  children: SessionNode[]
}

function buildSessionTree(sessions: SessionSummary[]): SessionNode[] {
  const byId = new Map<string, SessionNode>()
  sessions.forEach((s) => byId.set(s.session_id, { ...s, children: [] }))

  const roots: SessionNode[] = []
  byId.forEach((node) => {
    const parentId = node.parent_session_id || null
    if (parentId && byId.has(parentId)) {
      byId.get(parentId)!.children.push(node)
    } else {
      roots.push(node)
    }
  })

  const sortByActivity = (a: SessionNode, b: SessionNode) =>
    (b.last_active || "").localeCompare(a.last_active || "")
  const sortRecursively = (nodes: SessionNode[]) => {
    nodes.sort(sortByActivity)
    nodes.forEach((n) => sortRecursively(n.children))
  }
  sortRecursively(roots)
  return roots
}

interface SessionRowProps {
  node: SessionNode
  depth: number
  activeId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

function SessionRow({ node, depth, activeId, onSelect, onDelete }: SessionRowProps) {
  const active = node.session_id === activeId
  return (
    <>
      <motion.li
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="relative"
        style={{ paddingLeft: depth ? depth * 12 : 0 }}
      >
        <button
          type="button"
          onClick={() => onSelect(node.session_id)}
          className={cn(
            "group relative flex w-full flex-col items-start gap-0.5 rounded-md px-3 py-2 text-left transition-colors",
            active ? "bg-muted text-fg" : "hover:bg-muted/60 text-muted-fg hover:text-fg",
          )}
        >
          {depth > 0 && (
            <span
              aria-hidden
              className="pointer-events-none absolute left-1 top-0 bottom-0 w-px bg-border/60"
            />
          )}
          {active && (
            <motion.span
              layoutId="session-active"
              className="absolute inset-y-1.5 left-0 w-0.5 rounded-r bg-primary"
              transition={{ type: "spring", stiffness: 320, damping: 30 }}
            />
          )}
          <span className="flex w-full items-center gap-1.5">
            {depth > 0 && (
              <GitBranch className="h-3 w-3 shrink-0 text-muted-fg/70" aria-label="Branched session" />
            )}
            <span className="min-w-0 flex-1 truncate text-[13px] font-medium leading-tight text-fg">
              {truncate(node.title || node.first_question, 64) || "Untitled"}
            </span>
          </span>
          <span className="text-xs text-muted-fg">
            {node.turn_count} turn{node.turn_count === 1 ? "" : "s"} • {formatRelativeTime(node.last_active)}
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
                  onDelete(node.session_id)
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
      {node.children.map((child) => (
        <SessionRow
          key={child.session_id}
          node={child}
          depth={depth + 1}
          activeId={activeId}
          onSelect={onSelect}
          onDelete={onDelete}
        />
      ))}
    </>
  )
}

export function SessionsRail({
  sessions,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  onPickBookmark,
  className,
  showShell = true,
}: SessionsRailProps) {
  const Wrapper: React.ElementType = showShell ? "aside" : "div"
  const tree = React.useMemo(() => buildSessionTree(sessions), [sessions])
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
        {tree.length === 0 ? (
          <p className="rounded-md border border-dashed border-border bg-card/40 p-4 text-center text-xs text-muted-fg">
            No sessions yet. Ask your first question to start one.
          </p>
        ) : (
          <TooltipProvider delayDuration={350}>
            <ul className="flex flex-col gap-1">
              {tree.map((root) => (
                <SessionRow
                  key={root.session_id}
                  node={root}
                  depth={0}
                  activeId={activeId}
                  onSelect={onSelect}
                  onDelete={onDelete}
                />
              ))}
            </ul>
          </TooltipProvider>
        )}
        <BookmarksSection onPick={onPickBookmark} className="mt-3" />
      </ScrollArea>
    </Wrapper>
  )
}
