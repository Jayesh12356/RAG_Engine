import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateString: string) {
  const date = new Date(dateString)
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date)
}

export function formatRelativeTime(input: string | Date): string {
  const date = typeof input === "string" ? new Date(input) : input
  const seconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (Number.isNaN(seconds) || seconds < 0) return "just now"
  if (seconds < 5) return "just now"
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return formatDate(date.toISOString())
}

export function truncate(str: string, length: number) {
  if (!str) return ""
  if (str.length <= length) return str
  return str.slice(0, length) + "…"
}

export function initialsFromName(name?: string | null): string {
  if (!name) return "U"
  const parts = name.trim().split(/\s+/).slice(0, 2)
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "U"
}

export function uid(prefix = "id"): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID()}`
  }
  return `${prefix}_${Math.random().toString(36).slice(2, 11)}`
}

const UUID_PREFIX_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/i

/** Drop a leading UUID-and-underscore so display names match what the user uploaded. */
export function stripUuidPrefix(name: string | null | undefined): string {
  if (!name) return ""
  return name.replace(UUID_PREFIX_RE, "")
}

/**
 * Clean a filename keeping its extension — used for the documents page where
 * operators expect to see the real file (``Onboarding.pdf``) rather than a
 * stripped citation label.
 */
export function cleanFilename(name: string | null | undefined): string {
  if (!name) return "Untitled document"
  const stripped = stripUuidPrefix(name)
  return stripped.trim() || name.trim() || "Untitled document"
}

/** Format a long opaque id as ``aaaaaaaa…zzzz`` for compact display. */
export function shortId(id: string | null | undefined, head = 8, tail = 4): string {
  if (!id) return ""
  if (id.length <= head + tail + 1) return id
  return `${id.slice(0, head)}…${id.slice(-tail)}`
}

export function cleanPdfName(name: string | null | undefined): string {
  if (!name) return "Source document"
  // Strip a leading UUID-style prefix followed by an underscore, e.g.
  //   "4cefb52c-0282-4346-b159-9c180ab541e9_cv-jayesh-koli.pdf"
  //     -> "cv-jayesh-koli.pdf"
  const stripped = stripUuidPrefix(name)
  // Remove the trailing extension and any trailing "(1)" duplicate-suffix
  const noExt = stripped.replace(/\.[a-z0-9]{1,5}$/i, "")
  return noExt.replace(/\s*\(\d+\)\s*$/i, "").trim() || stripped
}
