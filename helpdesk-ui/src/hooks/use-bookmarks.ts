"use client"

import * as React from "react"

import { getPreferences, putPreferences, type BookmarkPayload } from "@/lib/api"

export interface BookmarkItem {
  id: string
  question: string
  answer?: string
  createdAt: string
}

const STORAGE_KEY = "helpdesk.bookmarks"
const EVENT_NAME = "helpdesk:bookmarks-changed"
const SYNC_DEBOUNCE_MS = 600

function readBookmarks(): BookmarkItem[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as BookmarkItem[]) : []
  } catch {
    return []
  }
}

function writeBookmarks(items: BookmarkItem[]) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, 100)))
    window.dispatchEvent(new Event(EVENT_NAME))
  } catch {
    /* quota — ignore */
  }
}

function toPayload(items: BookmarkItem[]): BookmarkPayload[] {
  return items.map((b) => ({
    id: b.id,
    question: b.question,
    answer: b.answer ?? null,
    createdAt: b.createdAt ?? null,
  }))
}

function fromPayload(items: BookmarkPayload[]): BookmarkItem[] {
  return items.map((b) => ({
    id: b.id,
    question: b.question,
    answer: b.answer ?? undefined,
    createdAt: b.createdAt ?? new Date().toISOString(),
  }))
}

export interface UseBookmarksApi {
  bookmarks: BookmarkItem[]
  addBookmark: (item: Omit<BookmarkItem, "createdAt">) => void
  removeBookmark: (id: string) => void
  toggleBookmark: (item: Omit<BookmarkItem, "createdAt">) => void
  isBookmarked: (id: string) => boolean
  clearBookmarks: () => void
}

export function useBookmarks(): UseBookmarksApi {
  const [bookmarks, setBookmarks] = React.useState<BookmarkItem[]>(() => readBookmarks())
  const syncTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const hydratedRef = React.useRef(false)

  // Schedule a background sync to the user_preferences API.  Debounced so we
  // don't hammer the server on rapid toggles.
  const scheduleSync = React.useCallback((items: BookmarkItem[]) => {
    if (syncTimer.current) clearTimeout(syncTimer.current)
    syncTimer.current = setTimeout(() => {
      putPreferences({ bookmarks: toPayload(items) }).catch(() => {
        /* offline / 401 — localStorage already has the source of truth */
      })
    }, SYNC_DEBOUNCE_MS)
  }, [])

  // Hydrate from the backend once on mount; merge into local list keyed by id.
  React.useEffect(() => {
    if (hydratedRef.current) return
    hydratedRef.current = true
    getPreferences()
      .then((prefs) => {
        const remote = fromPayload(prefs.bookmarks ?? [])
        if (!remote.length) return
        const local = readBookmarks()
        const merged: BookmarkItem[] = [...remote]
        for (const item of local) {
          if (!merged.some((m) => m.id === item.id)) merged.push(item)
        }
        merged.sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""))
        writeBookmarks(merged)
        setBookmarks(merged)
      })
      .catch(() => {
        /* anonymous user / no cookie — localStorage only */
      })
  }, [])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    const refresh = () => setBookmarks(readBookmarks())
    window.addEventListener(EVENT_NAME, refresh)
    window.addEventListener("storage", (event) => {
      if (event.key === STORAGE_KEY) refresh()
    })
    return () => {
      window.removeEventListener(EVENT_NAME, refresh)
    }
  }, [])

  const addBookmark = React.useCallback(
    (item: Omit<BookmarkItem, "createdAt">) => {
      const list = readBookmarks().filter((b) => b.id !== item.id)
      list.unshift({ ...item, createdAt: new Date().toISOString() })
      writeBookmarks(list)
      setBookmarks(list)
      scheduleSync(list)
    },
    [scheduleSync],
  )

  const removeBookmark = React.useCallback(
    (id: string) => {
      const list = readBookmarks().filter((b) => b.id !== id)
      writeBookmarks(list)
      setBookmarks(list)
      scheduleSync(list)
    },
    [scheduleSync],
  )

  const isBookmarked = React.useCallback(
    (id: string) => bookmarks.some((b) => b.id === id),
    [bookmarks],
  )

  const toggleBookmark = React.useCallback(
    (item: Omit<BookmarkItem, "createdAt">) => {
      if (isBookmarked(item.id)) removeBookmark(item.id)
      else addBookmark(item)
    },
    [addBookmark, isBookmarked, removeBookmark],
  )

  const clearBookmarks = React.useCallback(() => {
    writeBookmarks([])
    setBookmarks([])
    scheduleSync([])
  }, [scheduleSync])

  return { bookmarks, addBookmark, removeBookmark, toggleBookmark, isBookmarked, clearBookmarks }
}
