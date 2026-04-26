"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { FileUp, MessagesSquare } from "lucide-react"
import { toast } from "sonner"
import { Composer, type SlashAction } from "@/components/chat/composer"
import { Conversation } from "@/components/chat/conversation"
import { SessionsRail } from "@/components/chat/sessions-rail"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import {
  deleteChatSession,
  getChatHistory,
  getChatSessions,
  postChatStream,
  postIngest,
} from "@/lib/api"
import type { HistoryTurn, SessionSummary } from "@/types"
import { uid } from "@/lib/utils"

export default function ChatPage() {
  const [sessions, setSessions] = React.useState<SessionSummary[]>([])
  const [sessionId, setSessionId] = React.useState<string | null>(null)
  const [messages, setMessages] = React.useState<HistoryTurn[]>([])
  const [loading, setLoading] = React.useState(false)
  const [streamingId, setStreamingId] = React.useState<string | null>(null)
  const [demoMode, setDemoMode] = React.useState(false)
  const [category, setCategory] = React.useState("GENERAL")
  const [composer, setComposer] = React.useState("")

  const [mobileSessionsOpen, setMobileSessionsOpen] = React.useState(false)

  const [dropping, setDropping] = React.useState(false)
  const [ingesting, setIngesting] = React.useState(false)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const refreshSessions = React.useCallback(
    async (mode = demoMode) => {
      try {
        const data = await getChatSessions(mode)
        setSessions(data.sessions ?? [])
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load sessions"
        toast.error(message)
      }
    },
    [demoMode],
  )

  React.useEffect(() => {
    refreshSessions()
  }, [refreshSessions])

  const handleSelectSession = async (id: string) => {
    setSessionId(id)
    setLoading(true)
    try {
      const data = await getChatHistory(id, demoMode)
      setMessages(data.turns ?? [])
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load history"
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  const handleNewChat = () => {
    setSessionId(null)
    setMessages([])
    setStreamingId(null)
  }

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteChatSession(id, demoMode)
      toast.success("Session deleted")
      if (id === sessionId) handleNewChat()
      refreshSessions()
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete session"
      toast.error(message)
    }
  }

  const submitQuestion = React.useCallback(
    async (text: string) => {
      if (!text.trim()) return
      setComposer("")

      const optimisticUser: HistoryTurn = {
        id: uid("turn"),
        session_id: sessionId ?? "",
        role: "user",
        content: text,
        confidence: null,
        service_category: category,
        sources: [],
        created_at: new Date().toISOString(),
      }
      const assistantId = uid("turn")
      const optimisticAssistant: HistoryTurn = {
        id: assistantId,
        session_id: sessionId ?? "",
        role: "assistant",
        content: "",
        confidence: null,
        service_category: category,
        sources: [],
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, optimisticUser, optimisticAssistant])
      setStreamingId(assistantId)
      setLoading(true)

      try {
        const result = await postChatStream(
          {
            session_id: sessionId,
            question: text,
            service_category: category === "GENERAL" ? null : category,
            top_k: 20,
          },
          (delta) =>
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + delta } : m)),
            ),
          demoMode,
        )

        if (result.history) {
          setMessages(result.history)
        }
        if (result.session_id && result.session_id !== sessionId) {
          setSessionId(result.session_id)
        }
        refreshSessions(demoMode)
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to send message"
        toast.error(message)
        setMessages((prev) => prev.filter((m) => m.id !== assistantId))
      } finally {
        setStreamingId(null)
        setLoading(false)
      }
    },
    [category, demoMode, refreshSessions, sessionId],
  )

  const handleSubmit = () => {
    submitQuestion(composer)
  }

  const handleRegenerate = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user")
    if (!lastUser) return
    setMessages((prev) => {
      const cut = prev.slice(0, prev.findLastIndex((m) => m.role === "user"))
      return cut
    })
    submitQuestion(lastUser.content)
  }

  const handleSlash = (action: SlashAction) => {
    setComposer("")
    if (action === "clear") handleNewChat()
    if (action === "upload") fileInputRef.current?.click()
  }

  const handleAttach = () => {
    fileInputRef.current?.click()
  }

  const ingestFile = async (file: File) => {
    if (file.size > 50 * 1024 * 1024) {
      toast.error("File is larger than 50 MB.")
      return
    }
    setIngesting(true)
    const toastId = toast.loading(`Ingesting ${file.name}…`)
    try {
      const res = await postIngest(file, undefined, undefined, demoMode)
      toast.success(`Ingested ${res.pdf_name}`, {
        id: toastId,
        description: `${res.total_pages} pages, ${res.total_chunks} chunks indexed`,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ingest failed"
      toast.error(message, { id: toastId })
    } finally {
      setIngesting(false)
    }
  }

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setDropping(false)
    const files = Array.from(e.dataTransfer.files ?? [])
    for (const f of files) {
      await ingestFile(f)
    }
  }

  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    for (const f of files) {
      await ingestFile(f)
    }
    e.target.value = ""
  }

  return (
    <div
      className="relative flex h-full w-full"
      onDragOver={(e) => {
        e.preventDefault()
        setDropping(true)
      }}
      onDragLeave={() => setDropping(false)}
      onDrop={onDrop}
    >
      <input
        ref={fileInputRef}
        data-tour="upload"
        type="file"
        multiple
        accept="application/pdf,.pdf,.docx,.pptx,.xlsx,.xls,.csv,.txt,.md,.markdown,.html,.htm,.json,.png,.jpg,.jpeg,.webp,.tiff,.tif,.bmp"
        className="hidden"
        onChange={onFileChange}
      />

      <SessionsRail
        sessions={sessions}
        activeId={sessionId}
        onSelect={handleSelectSession}
        onNewChat={handleNewChat}
        onDelete={handleDeleteSession}
      />

      <div className="relative flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-2 border-b border-border bg-card/40 px-3 py-2 md:hidden">
          <Sheet open={mobileSessionsOpen} onOpenChange={setMobileSessionsOpen}>
            <SheetTrigger asChild>
              <Button type="button" variant="secondary" size="sm">
                <MessagesSquare className="h-3.5 w-3.5" />
                Sessions
                {sessions.length > 0 && (
                  <span className="ml-1 rounded-full bg-primary/15 px-1.5 text-[11px] text-primary">
                    {sessions.length}
                  </span>
                )}
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[300px] p-0 sm:max-w-[300px]">
              <SheetHeader className="sr-only">
                <SheetTitle>Sessions</SheetTitle>
                <SheetDescription>Switch between past chat sessions or start a new one.</SheetDescription>
              </SheetHeader>
              <SessionsRail
                sessions={sessions}
                activeId={sessionId}
                onSelect={(id) => {
                  handleSelectSession(id)
                  setMobileSessionsOpen(false)
                }}
                onNewChat={() => {
                  handleNewChat()
                  setMobileSessionsOpen(false)
                }}
                onDelete={handleDeleteSession}
                showShell={false}
              />
            </SheetContent>
          </Sheet>
          <span className="truncate text-xs text-muted-fg">
            {sessionId
              ? sessions.find((s) => s.session_id === sessionId)?.first_question || "Untitled session"
              : "New chat"}
          </span>
        </div>
        <Conversation
          messages={messages}
          loading={loading}
          streamingId={streamingId}
          onSuggestion={(t) => submitQuestion(t)}
          onCopy={() => toast.success("Copied")}
          onRegenerate={handleRegenerate}
          className="flex-1 min-h-0"
        />
        <Composer
          value={composer}
          onChange={setComposer}
          onSubmit={handleSubmit}
          onAttach={handleAttach}
          onSlash={handleSlash}
          demoMode={demoMode}
          onDemoToggle={(v) => {
            setDemoMode(v)
            handleNewChat()
          }}
          category={category}
          onCategoryChange={setCategory}
          disabled={loading || ingesting}
        />
      </div>

      <AnimatePresence>
        {dropping && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-bg/80 backdrop-blur-sm"
          >
            <div className="rounded-2xl border-2 border-dashed border-primary/60 bg-card/80 p-10 text-center shadow-glow">
              <FileUp className="mx-auto mb-2 h-8 w-8 text-primary" />
              <p className="text-2xl font-semibold tracking-[-0.02em] text-fg">Drop to ingest</p>
              <p className="mt-1 text-xs text-muted-fg">
                PDF, Word, PowerPoint, Excel/CSV, text, Markdown, HTML, JSON or images.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
