"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import { ArrowRight, Lock, Mail, ShieldCheck, Sparkles, User2 } from "lucide-react"
import { GlowOrb } from "@/components/motion/glow-orb"
import { RingPulse } from "@/components/motion/ring-pulse"
import { Wordmark } from "@/components/app/wordmark"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { signIn } from "@/lib/auth"
import { toast } from "sonner"

export type AuthMode = "sign-in" | "sign-up"

const COPY: Record<AuthMode, { title: string; subtitle: string; cta: string }> = {
  "sign-in": {
    title: "Welcome back",
    subtitle: "Sign in to your RAG Engine workspace and continue exploring your documents.",
    cta: "Continue",
  },
  "sign-up": {
    title: "Create your workspace",
    subtitle: "Spin up a private space to upload, search, and chat with your documents.",
    cta: "Get started",
  },
}

export function AuthShell({ mode }: { mode: AuthMode }) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const from = searchParams.get("from") || "/app/chat"

  const [name, setName] = React.useState("")
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [submitting, setSubmitting] = React.useState(false)

  const copy = COPY[mode]
  const isSignUp = mode === "sign-up"

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password.trim() || (isSignUp && !name.trim())) {
      toast.error("Please fill in all required fields.")
      return
    }
    setSubmitting(true)
    try {
      const fallbackName = email.split("@")[0]?.replace(/[._-]+/g, " ") || "User"
      signIn({
        name: isSignUp ? name : fallbackName.replace(/\b\w/g, (c) => c.toUpperCase()),
        email,
      })
      toast.success(isSignUp ? "Workspace ready" : "Signed in")
      // Wait a tick so cookie is set before middleware sees it
      setTimeout(() => {
        router.push(from)
        router.refresh()
      }, 60)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong"
      toast.error(message)
      setSubmitting(false)
    }
  }

  return (
    <div className="relative grid min-h-screen overflow-hidden bg-bg lg:grid-cols-[1fr_minmax(0,560px)]">
      {/* ── Left canvas (hidden on small screens) ───────────────────────── */}
      <div className="relative hidden overflow-hidden border-r border-border bg-card/40 lg:flex">
        <div className="absolute inset-0">
          <GlowOrb
            size={620}
            color="hsl(var(--primary) / 0.55)"
            className="left-[-180px] top-[-120px]"
            intensity={0.95}
          />
          <GlowOrb
            size={520}
            color="hsl(var(--accent) / 0.45)"
            className="bottom-[-200px] right-[-120px]"
            intensity={0.85}
          />
        </div>
        <div className="relative z-10 flex w-full flex-col justify-between p-12">
          <Link href="/" className="inline-flex">
            <Wordmark />
          </Link>

          <div className="relative flex flex-col items-start gap-8">
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
              <RingPulse size={420} count={3} />
            </div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className="relative max-w-md"
            >
              <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-fg backdrop-blur">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                <span>Document Q&amp;A reimagined</span>
              </p>
              <h2 className="text-[44px] font-bold leading-[1.05] tracking-[-0.03em] text-fg">
                Ask anything
                <br />
                <span className="text-shimmer">across every document.</span>
              </h2>
              <p className="mt-4 max-w-sm text-[15px] leading-relaxed text-muted-fg">
                Upload PDFs, Word, Excel/CSV, PowerPoint, text, Markdown, HTML, JSON or images. Get
                cited, grounded answers with confidence scores in milliseconds.
              </p>
            </motion.div>

            <motion.ul
              initial="hidden"
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.08 } } }}
              className="relative flex flex-col gap-3"
            >
              {[
                "Cited answers with adjustable confidence",
                "Hybrid retrieval across vector + keyword",
                "Multi-document reasoning with refusal guardrails",
              ].map((line) => (
                <motion.li
                  key={line}
                  variants={{
                    hidden: { opacity: 0, x: -10 },
                    visible: { opacity: 1, x: 0 },
                  }}
                  className="flex items-center gap-2 text-sm text-fg/85"
                >
                  <ShieldCheck className="h-4 w-4 text-primary" />
                  {line}
                </motion.li>
              ))}
            </motion.ul>
          </div>

          <p className="relative text-xs text-muted-fg">
            © {new Date().getFullYear()} RAG Engine • Grounded answers, every time.
          </p>
        </div>
      </div>

      {/* ── Right form column ───────────────────────────────────────────── */}
      <div className="flex items-center justify-center px-6 py-12 sm:px-12">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-md"
        >
          <Link href="/" className="lg:hidden inline-flex mb-8">
            <Wordmark />
          </Link>

          <Tabs value={mode}>
            <TabsList className="mb-6 grid w-full grid-cols-2">
              <TabsTrigger value="sign-in" asChild>
                <Link href="/sign-in" prefetch={false}>
                  Sign in
                </Link>
              </TabsTrigger>
              <TabsTrigger value="sign-up" asChild>
                <Link href="/sign-up" prefetch={false}>
                  Create account
                </Link>
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <h1 className="text-3xl font-bold tracking-[-0.025em] text-fg">{copy.title}</h1>
          <p className="mt-1.5 text-sm text-muted-fg">{copy.subtitle}</p>

          <form className="mt-7 flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
            {isSignUp && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="name">Full name</Label>
                <div className="relative">
                  <User2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-fg" />
                  <Input
                    id="name"
                    autoComplete="name"
                    placeholder="Jane Doe"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-fg" />
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@workspace.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                {!isSignUp && (
                  <button
                    type="button"
                    className="text-xs font-medium text-primary hover:underline"
                    onClick={() => toast.info("Demo workspace — passwords aren’t actually stored.")}
                  >
                    Forgot?
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-fg" />
                <Input
                  id="password"
                  type="password"
                  autoComplete={isSignUp ? "new-password" : "current-password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <Button
              type="submit"
              size="lg"
              className="mt-2 w-full"
              disabled={submitting}
              variant="primary"
            >
              {submitting ? (
                "Signing you in…"
              ) : (
                <>
                  {copy.cta}
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-muted-fg">
            {isSignUp ? (
              <>
                Already have a workspace?{" "}
                <Link href="/sign-in" className="font-medium text-fg underline-offset-4 hover:underline">
                  Sign in
                </Link>
              </>
            ) : (
              <>
                New to RAG Engine?{" "}
                <Link href="/sign-up" className="font-medium text-fg underline-offset-4 hover:underline">
                  Create a workspace
                </Link>
              </>
            )}
          </p>

          <div className="mt-10 rounded-md border border-border bg-card/60 p-3 text-xs leading-relaxed text-muted-fg">
            <strong className="text-fg">Demo workspace.</strong> Auth is local only — sessions live in
            your browser, no credentials are sent off-device.
          </div>
        </motion.div>
      </div>
    </div>
  )
}
