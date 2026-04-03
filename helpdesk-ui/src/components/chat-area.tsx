import { HistoryTurn } from "@/types"
import { MessageSquare } from "lucide-react"
import { useEffect, useRef } from "react"
import { ConfidenceGauge } from "./confidence-gauge"
import { SourceAccordion } from "./source-accordion"

interface ChatAreaProps {
  sessionId: string | null
  messages: HistoryTurn[]
  loading: boolean
  onClear: () => void
}

export function ChatArea({ sessionId, messages, loading, onClear }: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] relative">
      {/* Top bar */}
      <div className="h-12 border-b border-slate-100 bg-white flex items-center justify-between px-5 shrink-0">
        <div className="text-[13px] font-medium text-slate-500 flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          {sessionId ? `Session ${sessionId.substring(0, 8)}` : "New Session"}
        </div>
        {messages.length > 0 && (
          <button
            onClick={onClear}
            className="text-[12px] font-medium text-slate-400 hover:text-indigo-600 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-6 bg-slate-50/50 pb-40">
        <div className="flex flex-col space-y-5 max-w-3xl mx-auto">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center text-center pt-24">
              <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
                <MessageSquare className="w-6 h-6 text-slate-300" />
              </div>
              <p className="text-sm font-medium text-slate-400">Start a conversation...</p>
              <p className="text-xs text-slate-300 mt-1">Ask anything about your IT documentation</p>
            </div>
          ) : (
            messages.map((msg, i) => {
              const isRefused = msg.content.toLowerCase().includes("cannot answer") || msg.content.toLowerCase().includes("does not contain")
              const isAssistant = msg.role === "assistant"

              return (
                <div
                  key={msg.id || i}
                  className={`flex ${!isAssistant ? "justify-end" : "justify-start"} animate-fade-in`}
                >
                  <div
                    className={`p-4 ${
                      !isAssistant
                        ? "bg-indigo-600 text-white rounded-2xl rounded-br-lg max-w-[70%] shadow-sm"
                        : isRefused
                        ? "bg-rose-50 text-rose-900 border border-rose-200/60 rounded-2xl rounded-bl-lg max-w-[80%]"
                        : "bg-white border border-slate-200/80 text-slate-700 rounded-2xl rounded-bl-lg max-w-[80%] shadow-sm"
                    }`}
                  >
                    <div className="whitespace-pre-wrap text-[14px] leading-relaxed">
                      {msg.content}
                    </div>
                    {isAssistant && msg.confidence !== null && msg.confidence !== undefined && (
                      <div className="mt-4 pt-3 border-t border-slate-100/60 flex flex-col gap-2">
                        <div className="w-[80px] h-[50px] origin-top-left transform scale-[0.75]">
                          <ConfidenceGauge confidence={msg.confidence} label={msg.confidence > 0.8 ? "high" : msg.confidence > 0.6 ? "moderate" : "low"} />
                        </div>
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="mt-1 w-full">
                            <SourceAccordion sources={msg.sources} />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            })
          )}
          
          {/* Typing indicator */}
          {loading && (
            <div className="flex justify-start animate-fade-in">
              <div className="bg-white border border-slate-200/80 p-4 rounded-2xl rounded-bl-lg shadow-sm dot-pulse flex gap-1.5 items-center h-12 w-20 justify-center">
                <span className="w-2 h-2 bg-slate-300 rounded-full" />
                <span className="w-2 h-2 bg-slate-300 rounded-full" />
                <span className="w-2 h-2 bg-slate-300 rounded-full" />
              </div>
            </div>
          )}
          <div ref={bottomRef} className="h-4" />
        </div>
      </div>
    </div>
  )
}
