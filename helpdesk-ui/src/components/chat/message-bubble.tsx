"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { Check, Copy, RefreshCcw } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { ConfidencePill } from "@/components/chat/confidence-gauge"
import { TypingDots } from "@/components/chat/typing-dots"
import { MarkdownAnswer } from "@/components/answer/markdown-answer"
import { SourceLink } from "@/components/answer/source-link"
import { messageVariants } from "@/lib/motion"
import { cn, formatRelativeTime, initialsFromName } from "@/lib/utils"
import type { HistoryTurn } from "@/types"
import { useSession } from "@/lib/auth"

export interface MessageBubbleProps {
  message: HistoryTurn
  streaming?: boolean
  onCopy?: (text: string) => void
  onRegenerate?: () => void
}

export function MessageBubble({
  message,
  streaming = false,
  onCopy,
  onRegenerate,
}: MessageBubbleProps) {
  const { user } = useSession()
  const isUser = message.role === "user"
  const [copied, setCopied] = React.useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      onCopy?.(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <motion.div
      variants={messageVariants}
      initial="hidden"
      animate="visible"
      className={cn(
        "group flex w-full items-start gap-3",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      <Avatar className={cn("h-8 w-8", isUser && "[background-image:none] bg-muted")}>
        <AvatarFallback
          className={cn(
            isUser
              ? "[background-image:none] bg-muted text-fg"
              : "[background-image:var(--grad-primary)] text-primary-fg",
          )}
        >
          {isUser ? initialsFromName(user?.name) : "R"}
        </AvatarFallback>
      </Avatar>

      <div className={cn("flex max-w-[85%] flex-col gap-1.5", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "flex items-baseline gap-2 text-xs",
            isUser ? "flex-row-reverse" : "flex-row",
          )}
        >
          <span className="font-semibold text-fg">{isUser ? user?.name ?? "You" : "RAG Engine"}</span>
          <span className="text-muted-fg">{formatRelativeTime(message.created_at)}</span>
        </div>

        <div
          className={cn(
            "relative break-words rounded-2xl px-4 py-3 text-[15px] leading-relaxed shadow-card",
            isUser
              ? "whitespace-pre-wrap rounded-br-sm text-primary-fg [background-image:var(--grad-primary)]"
              : "rounded-bl-sm border border-border bg-card text-card-fg",
          )}
        >
          {isUser ? (
            message.content
          ) : message.content ? (
            <>
              <MarkdownAnswer content={message.content} streaming={streaming} />
              {streaming && (
                <span
                  className="ml-0.5 inline-block h-4 w-[2px] translate-y-[2px] bg-primary animate-blink"
                  aria-hidden
                />
              )}
            </>
          ) : streaming ? (
            <TypingDots />
          ) : null}
        </div>

        {!isUser && message.sources?.length ? (
          <SourceLink sources={message.sources} className="mt-1" />
        ) : null}

        {!isUser && (message.confidence !== null || onCopy || onRegenerate) && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {message.confidence !== null && message.confidence !== undefined && (
              <ConfidencePill value={message.confidence} />
            )}

            <div className="ml-auto flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={handleCopy}
                className="h-7 w-7 text-muted-fg hover:text-fg"
                aria-label="Copy answer"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
              </Button>
              {onRegenerate && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={onRegenerate}
                  className="h-7 w-7 text-muted-fg hover:text-fg"
                  aria-label="Regenerate answer"
                  disabled={streaming}
                >
                  <RefreshCcw className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}
