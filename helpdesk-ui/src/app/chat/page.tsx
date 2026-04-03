"use client"

import { useState, useEffect } from "react"
import { HistoryTurn, SessionSummary } from "@/types"
import { ChatSidebar } from "@/components/chat-sidebar"
import { ChatArea } from "@/components/chat-area"
import { ChatInput } from "@/components/chat-input"
import { BASE } from "@/lib/api"

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<HistoryTurn[]>([])
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [demoMode, setDemoMode] = useState(false)
  const [initialLoad, setInitialLoad] = useState(true)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps
    fetchSessions()
  }, [])

  const fetchSessions = async (useDemo = demoMode) => {
    try {
      const headers: Record<string, string> = {}
      if (useDemo) headers['x-demo-mode'] = 'true'
      const res = await fetch(`${BASE}/chat/sessions`, { headers })
      const data = await res.json()
      if (data.sessions) {
        setSessions(data.sessions)
      }
    } catch (err) {
      console.error("Failed to fetch sessions", err)
    } finally {
      if (initialLoad) setInitialLoad(false)
    }
  }

  const handleSelectSession = async (id: string) => {
    setSessionId(id)
    setLoading(true)
    try {
      const headers: Record<string, string> = {}
      if (demoMode) headers['x-demo-mode'] = 'true'
      const res = await fetch(`${BASE}/chat/${id}/history`, { headers })
      const data = await res.json()
      if (data.turns) {
        setMessages(data.turns)
      }
    } catch (err) {
      console.error("Failed to fetch history", err)
    } finally {
      setLoading(false)
    }
  }

  const handleNewChat = () => {
    setSessionId(null)
    setMessages([])
  }

  const handleDeleteSession = async (id: string) => {
    try {
      const headers: Record<string, string> = {}
      if (demoMode) headers['x-demo-mode'] = 'true'
      await fetch(`${BASE}/chat/${id}`, { method: 'DELETE', headers })
      if (id === sessionId) {
        handleNewChat()
      }
      fetchSessions(demoMode)
    } catch (err) {
      console.error("Failed to delete session", err)
    }
  }

  const handleSend = async (text: string, category: string, useDemo: boolean) => {
    let currentSessionId = sessionId;

    if (useDemo !== demoMode) {
      setDemoMode(useDemo)
      if (currentSessionId) {
        currentSessionId = null;
        setSessionId(null);
        setMessages([]);
      }
    }

    const optimisticMsg: HistoryTurn = {
      id: Math.random().toString(),
      session_id: currentSessionId || "",
      role: "user",
      content: text,
      confidence: null,
      service_category: category,
      sources: [],
      created_at: new Date().toISOString()
    }
    const optimisticAssistantId = `assistant-stream-${Date.now()}`
    const optimisticAssistant: HistoryTurn = {
      id: optimisticAssistantId,
      session_id: currentSessionId || "",
      role: "assistant",
      content: "",
      confidence: null,
      service_category: category,
      sources: [],
      created_at: new Date().toISOString()
    }
    setMessages(prev => [...prev, optimisticMsg, optimisticAssistant])
    setLoading(true)

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" }
      if (useDemo) headers['x-demo-mode'] = 'true'
      
      const payload = {
        session_id: currentSessionId,
        question: text,
        service_category: category === "general" ? null : category,
        top_k: 20
      }

      const res = await fetch(`${BASE}/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      })
      if (!res.ok || !res.body) {
        throw new Error("Chat stream failed")
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      let finalPayload: { history?: HistoryTurn[]; session_id?: string } | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split("\n\n")
        buffer = events.pop() || ""
        for (const event of events) {
          if (!event.startsWith("data: ")) continue
          const parsed = JSON.parse(event.slice(6)) as {
            type: string
            text?: string
            payload?: { history?: HistoryTurn[]; session_id?: string }
          }
          if (parsed.type === "delta" && parsed.text) {
            setMessages(prev => prev.map(msg => (
              msg.id === optimisticAssistantId
                ? { ...msg, content: `${msg.content}${parsed.text}` }
                : msg
            )))
          } else if (parsed.type === "final" && parsed.payload) {
            finalPayload = parsed.payload
          }
        }
      }
      if (finalPayload?.history) {
        setMessages(finalPayload.history)
      }
      if (finalPayload?.session_id && finalPayload.session_id !== currentSessionId) {
        setSessionId(finalPayload.session_id)
      }
      fetchSessions(useDemo)
    } catch (err) {
      console.error("Failed to send message", err)
      setMessages(prev => prev.filter(msg => msg.id !== optimisticAssistantId))
    } finally {
      setLoading(false)
    }
  }

  if (initialLoad) {
    return (
      <div className="h-[calc(100vh-3.5rem)] flex items-center justify-center bg-slate-50">
        <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex w-full h-[calc(100vh-3.5rem)] overflow-hidden -mx-4 sm:-mx-6 lg:-mx-8">
      <div className="hidden md:block shrink-0">
        <ChatSidebar
          sessions={sessions}
          activeSessionId={sessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onDeleteSession={handleDeleteSession}
        />
      </div>
      <div className="flex-1 relative bg-slate-50/50">
        <ChatArea
          sessionId={sessionId}
          messages={messages}
          loading={loading}
          onClear={handleNewChat}
        />
        <ChatInput onSend={handleSend} disabled={loading} />
      </div>
    </div>
  )
}
