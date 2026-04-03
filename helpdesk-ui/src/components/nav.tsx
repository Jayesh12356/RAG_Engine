'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { HelpCircle, Search, MessageSquare, FileText, Activity } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function Nav() {
  const pathname = usePathname()

  const navLinks = [
    { name: 'Query', href: '/query', icon: Search },
    { name: 'Chat', href: '/chat', icon: MessageSquare },
    { name: 'Documents', href: '/documents', icon: FileText },
    { name: 'Status', href: '/status', icon: Activity },
  ]

  return (
    <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-lg border-b border-slate-200/80 h-14">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
        {/* Logo */}
        <Link href="/query" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent-gradient)' }}>
            <HelpCircle className="w-[18px] h-[18px] text-white" />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-slate-900 text-[15px] tracking-tight">IT Helpdesk</span>
            <span className="text-[10px] font-medium text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded tracking-wide">RAG</span>
          </div>
        </Link>

        {/* Nav Links */}
        <div className="flex items-center gap-1 h-full">
          {navLinks.map((link) => {
            const isActive = pathname.startsWith(link.href)
            const Icon = link.icon
            return (
              <Link
                key={link.name}
                href={link.href}
                className={cn(
                  "h-full flex items-center gap-1.5 px-3.5 text-[13px] font-medium border-b-2 transition-all duration-200",
                  isActive
                    ? "border-indigo-500 text-indigo-600"
                    : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
                )}
              >
                <Icon className={cn("w-[15px] h-[15px]", isActive ? "text-indigo-500" : "text-slate-400")} />
                <span className="hidden sm:inline">{link.name}</span>
              </Link>
            )
          })}
        </div>

        {/* Right section - version badge */}
        <div className="hidden md:flex items-center gap-2">
          <span className="text-[11px] font-medium text-slate-400">v0.1.0</span>
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        </div>
      </div>
    </nav>
  )
}
