"use client"

import { useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"
import { AnimatePresence, motion } from "framer-motion"
import { Sidebar } from "@/components/app/sidebar"
import { Topbar } from "@/components/app/topbar"
import { CommandProvider } from "@/components/app/command-palette"
import { CommandPaletteDialog } from "@/components/app/command-dialog"
import { OnboardingTour } from "@/components/app/onboarding-tour"
import { ServiceWorkerRegistrar } from "@/components/app/sw-register"
import { ShortcutOverlay } from "@/components/app/shortcut-overlay"
import { SourceViewerProvider } from "@/components/answer/source-viewer"
import { useSession } from "@/lib/auth"
import { Spinner } from "@/components/ui/spinner"

export default function AppShellLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { user, ready } = useSession()

  useEffect(() => {
    if (!ready) return
    if (!user) router.replace(`/sign-in?from=${encodeURIComponent(pathname || "/app/chat")}`)
  }, [user, ready, router, pathname])

  if (!ready || !user) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size={28} />
      </div>
    )
  }

  return (
    <CommandProvider>
      <SourceViewerProvider>
        <div className="flex h-screen w-full overflow-hidden bg-bg text-fg">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <Topbar />
            <AnimatePresence mode="wait" initial={false}>
              <motion.main
                key={pathname}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                className="relative flex-1 min-h-0 overflow-hidden"
              >
                {children}
              </motion.main>
            </AnimatePresence>
          </div>
          <OnboardingTour />
          <CommandPaletteDialog />
          <ShortcutOverlay />
          <ServiceWorkerRegistrar />
        </div>
      </SourceViewerProvider>
    </CommandProvider>
  )
}
