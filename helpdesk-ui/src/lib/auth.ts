"use client"

import { useEffect, useState } from "react"
import { uid } from "@/lib/utils"

export type SessionUser = {
  id: string
  name: string
  email: string
}

const STORAGE_KEY = "rag_engine.user"
const COOKIE_KEY = "rag_engine_uid"

function getUserFromStorage(): SessionUser | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as SessionUser
  } catch {
    return null
  }
}

function setCookie(value: string | null) {
  if (typeof document === "undefined") return
  if (!value) {
    document.cookie = `${COOKIE_KEY}=; path=/; max-age=0; SameSite=Lax`
    return
  }
  document.cookie = `${COOKIE_KEY}=${encodeURIComponent(value)}; path=/; max-age=2592000; SameSite=Lax`
}

export function readSessionFromCookie(cookieHeader?: string | null): string | null {
  if (!cookieHeader) return null
  const m = cookieHeader.match(new RegExp(`(?:^|; )${COOKIE_KEY}=([^;]+)`))
  return m ? decodeURIComponent(m[1]) : null
}

export function signIn(input: { name: string; email: string }): SessionUser {
  const user: SessionUser = {
    id: uid("user"),
    name: input.name,
    email: input.email,
  }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
  }
  setCookie(user.id)
  return user
}

export function signOut(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(STORAGE_KEY)
    window.localStorage.removeItem("rag_engine.tour_seen")
  }
  setCookie(null)
}

export function getCurrentUser(): SessionUser | null {
  return getUserFromStorage()
}

export function useSession(): { user: SessionUser | null; ready: boolean } {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const u = getUserFromStorage()
    setUser(u)
    if (u) setCookie(u.id)
    setReady(true)

    const onStorage = (e: StorageEvent) => {
      if (e.key !== STORAGE_KEY) return
      setUser(getUserFromStorage())
    }
    window.addEventListener("storage", onStorage)
    return () => window.removeEventListener("storage", onStorage)
  }, [])
  return { user, ready }
}
