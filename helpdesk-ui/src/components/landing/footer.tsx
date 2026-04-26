"use client"

import Link from "next/link"
import { Wordmark } from "@/components/app/wordmark"

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12 2C6.475 2 2 6.475 2 12c0 4.425 2.862 8.166 6.838 9.49.5.087.687-.213.687-.475 0-.237-.013-1.025-.013-1.862-2.512.463-3.162-.612-3.362-1.175-.113-.288-.6-1.175-1.025-1.413-.35-.187-.85-.65-.013-.662.788-.013 1.35.725 1.538 1.025.9 1.512 2.337 1.087 2.912.825.088-.65.35-1.087.638-1.337-2.225-.25-4.55-1.113-4.55-4.938 0-1.088.387-1.987 1.025-2.687-.1-.25-.45-1.275.1-2.65 0 0 .837-.263 2.75 1.025a9.28 9.28 0 0 1 2.5-.337c.85 0 1.7.112 2.5.337 1.912-1.3 2.75-1.025 2.75-1.025.55 1.375.2 2.4.1 2.65.637.7 1.025 1.587 1.025 2.687 0 3.838-2.337 4.688-4.562 4.938.362.312.675.912.675 1.85 0 1.337-.013 2.412-.013 2.75 0 .262.188.575.688.475C19.137 20.163 22 16.413 22 12c0-5.525-4.475-10-10-10Z" />
    </svg>
  )
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.503 11.24h-6.65l-5.214-6.815L4.99 21.75H1.679l7.73-8.835L1.254 2.25h6.812l4.713 6.231 5.465-6.231Zm-1.161 17.52h1.833L7.084 4.126H5.117l11.966 15.644Z" />
    </svg>
  )
}

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-card/30">
      <div className="mx-auto flex max-w-7xl flex-col items-start gap-8 px-6 py-10 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-3">
          <Wordmark />
          <p className="max-w-sm text-[13px] text-muted-fg">
            Grounded document Q&amp;A for teams that need accuracy, not eloquence.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-x-12 gap-y-2 text-[13px] text-muted-fg md:grid-cols-3">
          <Link href="/sign-up" className="hover:text-fg transition-colors">Get started</Link>
          <a href="#features" className="hover:text-fg transition-colors">Features</a>
          <a href="#providers" className="hover:text-fg transition-colors">Providers</a>
          <Link href="/app/chat" className="hover:text-fg transition-colors">Workspace</Link>
          <Link href="/app/status" className="hover:text-fg transition-colors">System status</Link>
          <Link href="/sign-in" className="hover:text-fg transition-colors">Sign in</Link>
        </div>
        <div className="flex items-center gap-3 text-muted-fg">
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-border p-2 transition-colors hover:text-fg"
            aria-label="GitHub"
          >
            <GithubIcon className="h-4 w-4" />
          </a>
          <a
            href="https://twitter.com"
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-border p-2 transition-colors hover:text-fg"
            aria-label="X"
          >
            <XIcon className="h-4 w-4" />
          </a>
        </div>
      </div>
      <div className="border-t border-border px-6 py-4 text-center text-xs text-muted-fg">
        © {new Date().getFullYear()} RAG Engine — All your docs, one source of truth.
      </div>
    </footer>
  )
}
