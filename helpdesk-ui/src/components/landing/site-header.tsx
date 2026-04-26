"use client"

import Link from "next/link"
import { motion, useScroll, useTransform } from "framer-motion"
import { Wordmark } from "@/components/app/wordmark"
import { ThemeToggle } from "@/components/app/theme-toggle"
import { Button } from "@/components/ui/button"
import { useSession } from "@/lib/auth"

export function SiteHeader() {
  const { user } = useSession()
  const { scrollY } = useScroll()
  const blur = useTransform(scrollY, [0, 80], [0, 14])
  const bgOpacity = useTransform(scrollY, [0, 80], [0, 0.85])

  return (
    <motion.header
      style={{
        backdropFilter: useTransform(blur, (b) => `blur(${b}px) saturate(140%)`),
        WebkitBackdropFilter: useTransform(blur, (b) => `blur(${b}px) saturate(140%)`),
        backgroundColor: useTransform(bgOpacity, (a) => `hsl(var(--bg) / ${a})`),
      }}
      className="sticky top-0 z-30 border-b border-transparent transition-colors"
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-6">
        <Link href="/" className="flex items-center gap-2">
          <Wordmark />
        </Link>
        <nav className="ml-8 hidden items-center gap-6 text-sm text-muted-fg md:flex">
          <a href="#features" className="hover:text-fg transition-colors">Features</a>
          <a href="#providers" className="hover:text-fg transition-colors">Providers</a>
          <a href="#testimonial" className="hover:text-fg transition-colors">Customers</a>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          {user ? (
            <Button asChild>
              <Link href="/app/chat">Open workspace</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
                <Link href="/sign-in">Sign in</Link>
              </Button>
              <Button asChild size="sm">
                <Link href="/sign-up">Get started</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </motion.header>
  )
}
