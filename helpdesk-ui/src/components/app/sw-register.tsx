"use client"

import * as React from "react"

/**
 * Registers the offline-shell service worker exactly once per browser session.
 * Skipped in development to avoid stale caches drowning hot reloads.
 */
export function ServiceWorkerRegistrar() {
  React.useEffect(() => {
    if (typeof window === "undefined") return
    if (process.env.NODE_ENV !== "production") return
    if (!("serviceWorker" in navigator)) return

    const onLoad = () => {
      navigator.serviceWorker.register("/sw.js").catch((err) => {
        console.warn("[sw] registration failed", err)
      })
    }
    window.addEventListener("load", onLoad)
    return () => window.removeEventListener("load", onLoad)
  }, [])

  return null
}
