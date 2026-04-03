import { SessionSummary } from "@/types"
import { Plus, Trash2, MessageSquare } from "lucide-react"
import { cn } from "@/lib/utils"

interface ChatSidebarProps {
  sessions: SessionSummary[]
  activeSessionId: string | null
  onSelectSession: (id: string) => void
  onNewChat: () => void
  onDeleteSession: (id: string) => void
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession
}: ChatSidebarProps) {
  return (
    <div className="w-[280px] bg-white border-r border-slate-200/80 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="p-4 border-b border-slate-100">
        <button
          onClick={onNewChat}
          className="btn-primary w-full h-9 text-[13px]"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {sessions.length === 0 ? (
          <div className="flex flex-col items-center text-center py-12 px-4">
            <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center mb-3">
              <MessageSquare className="w-5 h-5 text-slate-300" />
            </div>
            <p className="text-xs font-medium text-slate-400">No conversations yet</p>
            <p className="text-[11px] text-slate-300 mt-0.5">Start a new chat above</p>
          </div>
        ) : (
          sessions.map(session => (
            <div
              key={session.session_id}
              className={cn(
                "group flex items-center justify-between p-2.5 rounded-lg cursor-pointer transition-all duration-150",
                activeSessionId === session.session_id
                  ? "bg-indigo-50/80 ring-1 ring-indigo-200/50"
                  : "hover:bg-slate-50"
              )}
            >
              <div 
                className="flex-1 min-w-0" 
                onClick={() => onSelectSession(session.session_id)}
              >
                <div className={cn(
                  "text-[13px] font-medium truncate",
                  activeSessionId === session.session_id ? "text-indigo-700" : "text-slate-700"
                )}>
                  {session.first_question ? session.first_question.substring(0, 40) : "New Conversation"}
                  {session.first_question && session.first_question.length > 40 && "..."}
                </div>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-[10px] font-medium bg-slate-100 text-slate-400 rounded px-1.5 py-0.5">
                    {session.turn_count} {session.turn_count === 1 ? 'turn' : 'turns'}
                  </span>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(session.session_id);
                }}
                className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-lg transition-all"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
