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

export function cleanPdfName(name: string | null | undefined): string {
  if (!name) return "Source document"
  // Strip a leading UUID-style prefix followed by an underscore, e.g.
  //   "4cefb52c-0282-4346-b159-9c180ab541e9_cv-jayesh-koli.pdf"
  //     -> "cv-jayesh-koli.pdf"
  const stripped = name.replace(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/i, "")
  // Remove the trailing extension and any trailing "(1)" duplicate-suffix
  const noExt = stripped.replace(/\.[a-z0-9]{1,5}$/i, "")
  return noExt.replace(/\s*\(\d+\)\s*$/i, "").trim() || stripped
}
