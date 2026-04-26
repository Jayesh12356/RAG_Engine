"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { MessageBubble } from "@/components/chat/message-bubble"
import { ChatEmptyState } from "@/components/chat/empty-state"
import type { Citation, HistoryTurn } from "@/types"
import { cn } from "@/lib/utils"

export interface ConversationProps {
  messages: HistoryTurn[]
  loading: boolean
  streamingId?: string | null
  onSuggestion: (text: string) => void
  onCopy: (text: string) => void
  onRegenerate: () => void
  onBranch?: (turnId: string) => void
  citationsByTurn?: Record<string, Citation[]>
  className?: string
}

export function Conversation({
  messages,
  loading,
  streamingId,
  onSuggestion,
  onCopy,
  onRegenerate,
  onBranch,
  citationsByTurn,
  className,
}: ConversationProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const bottomRef = React.useRef<HTMLDivElement>(null)
  const [stickToBottom, setStickToBottom] = React.useState(true)

  React.useEffect(() => {
    if (!stickToBottom) return
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [messages, stickToBottom])

  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    setStickToBottom(distance < 80)
  }

  if (messages.length === 0 && !loading) {
    return (
      <div className={cn("relative h-full overflow-y-auto", className)}>
        <ChatEmptyState onPick={onSuggestion} />
      </div>
    )
  }

  return (
    <div className={cn("relative h-full overflow-hidden", className)}>
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="h-full overflow-y-auto px-4 py-6 md:px-8"
      >
        <div className="mx-auto flex max-w-3xl flex-col gap-7">
          {messages.map((msg, idx) => {
            const question =
              msg.role === "assistant"
                ? messages
                    .slice(0, idx)
                    .reverse()
                    .find((m) => m.role === "user")?.content
                : undefined
            return (
              <MessageBubble
                key={msg.id}
                message={msg}
                streaming={msg.id === streamingId}
                onCopy={onCopy}
                onRegenerate={onRegenerate}
                onBranch={onBranch}
                citations={citationsByTurn?.[msg.id]}
                question={question}
              />
            )
          })}
          <div ref={bottomRef} />
        </div>
      </div>
      <AnimatePresence>
        {!stickToBottom && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            transition={{ duration: 0.2 }}
            className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2"
          >
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="pointer-events-auto h-8 rounded-full"
              onClick={() => {
                bottomRef.current?.scrollIntoView({ behavior: "smooth" })
                setStickToBottom(true)
              }}
            >
              <ArrowDown className="h-3.5 w-3.5" />
              Latest
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
