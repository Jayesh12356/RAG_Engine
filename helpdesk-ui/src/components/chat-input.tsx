import { SendHorizontal } from "lucide-react"
import { useState, KeyboardEvent } from "react"
import * as Switch from '@radix-ui/react-switch'

interface ChatInputProps {
  onSend: (text: string, category: string, useDemo: boolean) => void
  disabled: boolean
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("")
  const [category, setCategory] = useState("general")
  const [demoMode, setDemoMode] = useState(false)

  const handleSend = () => {
    if (!input.trim() || disabled) return
    onSend(input.trim(), category, demoMode)
    setInput("")
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 p-4 bg-white/90 backdrop-blur-lg border-t border-slate-100 flex flex-col gap-2">
      <div className="max-w-3xl mx-auto w-full flex flex-col gap-2">
        {/* Options row */}
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2.5">
            <Switch.Root
              checked={demoMode}
              onCheckedChange={setDemoMode}
              className="toggle-root !w-8 !h-[18px]"
            >
              <Switch.Thumb className="toggle-thumb !w-[14px] !h-[14px] data-[state=checked]:!translate-x-[14px]" />
            </Switch.Root>
            <span className="text-[11px] font-medium text-slate-400">Demo</span>
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="text-[11px] font-medium text-slate-400 bg-transparent border-none cursor-pointer focus:ring-0 p-0 pr-4"
          >
            <option value="general">General Helpdesk</option>
            <option value="access">Access &amp; Accounts</option>
            <option value="hardware">Hardware</option>
            <option value="software">Software</option>
            <option value="network">Network &amp; VPN</option>
          </select>
        </div>

        {/* Input row */}
        <div className="relative flex items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question..."
            className="w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 pr-12 text-sm text-slate-800 placeholder:text-slate-400
                       focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none
                       min-h-[48px] max-h-32 shadow-sm transition-all"
            rows={Math.min(5, input.split('\n').length || 1)}
            disabled={disabled}
          />
          <button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            className="absolute right-2 bottom-2 p-2 rounded-lg transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed mb-[2px]"
            style={{ background: input.trim() && !disabled ? 'var(--accent-gradient)' : '#e2e8f0' }}
          >
            <SendHorizontal className="w-4 h-4 text-white" />
          </button>
        </div>
      </div>
    </div>
  )
}
