"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { ConfidencePill } from "@/components/chat/confidence-gauge"
import { TypingDots } from "@/components/chat/typing-dots"
import { AnswerToolbar } from "@/components/answer/answer-toolbar"
import { MarkdownAnswer } from "@/components/answer/markdown-answer"
import { SourceLink } from "@/components/answer/source-link"
import { messageVariants } from "@/lib/motion"
import { cn, formatRelativeTime, initialsFromName } from "@/lib/utils"
import type { Citation, HistoryTurn } from "@/types"
import { useSession } from "@/lib/auth"

export interface MessageBubbleProps {
  message: HistoryTurn
  streaming?: boolean
  onCopy?: (text: string) => void
  onRegenerate?: () => void
  onBranch?: (turnId: string) => void
  citations?: Citation[]
  /** Question text the assistant turn is responding to. */
  question?: string
}

export function MessageBubble({
  message,
  streaming = false,
  onCopy,
  onRegenerate,
  onBranch,
  citations,
  question,
}: MessageBubbleProps) {
  const { user } = useSession()
  const isUser = message.role === "user"

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
              <MarkdownAnswer
                content={message.content}
                streaming={streaming}
                citations={citations}
              />
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

        {!isUser && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {message.confidence !== null && message.confidence !== undefined && (
              <ConfidencePill value={message.confidence} />
            )}
            <AnswerToolbar
              content={message.content}
              question={question}
              sources={message.sources}
              citations={citations}
              bookmarkId={message.id}
              shareId={message.id}
              onBranch={onBranch ? () => onBranch(message.id) : undefined}
              onRegenerate={onRegenerate}
              onCopy={onCopy}
              streaming={streaming}
              className="ml-auto opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"
            />
          </div>
        )}
      </div>
    </motion.div>
  )
}
