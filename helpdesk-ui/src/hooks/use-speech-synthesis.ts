"use client"

import * as React from "react"

export interface UseSpeechSynthesisOptions {
  rate?: number
  pitch?: number
  volume?: number
  lang?: string
}

export interface SpeechSynthesisState {
  supported: boolean
  speaking: boolean
  speak: (text: string, options?: UseSpeechSynthesisOptions) => void
  cancel: () => void
  toggle: (text: string, options?: UseSpeechSynthesisOptions) => void
}

function stripMarkdownForSpeech(input: string): string {
  return input
    .replace(/```[\s\S]*?```/g, " (code block) ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_~>#-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

export function useSpeechSynthesis(): SpeechSynthesisState {
  const [speaking, setSpeaking] = React.useState(false)
  const supported = React.useMemo(() => {
    if (typeof window === "undefined") return false
    return typeof window.speechSynthesis !== "undefined"
  }, [])

  const cancel = React.useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  const speak = React.useCallback(
    (text: string, options?: UseSpeechSynthesisOptions) => {
      if (!supported || !text.trim()) return
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(stripMarkdownForSpeech(text))
      utterance.rate = options?.rate ?? 1
      utterance.pitch = options?.pitch ?? 1
      utterance.volume = options?.volume ?? 1
      utterance.lang = options?.lang ?? (typeof navigator !== "undefined" ? navigator.language : "en-US")
      utterance.onend = () => setSpeaking(false)
      utterance.onerror = () => setSpeaking(false)
      utterance.onstart = () => setSpeaking(true)
      window.speechSynthesis.speak(utterance)
    },
    [supported],
  )

  const toggle = React.useCallback(
    (text: string, options?: UseSpeechSynthesisOptions) => {
      if (speaking) cancel()
      else speak(text, options)
    },
    [cancel, speak, speaking],
  )

  React.useEffect(() => {
    return () => {
      if (supported) window.speechSynthesis.cancel()
    }
  }, [supported])

  return { supported, speaking, speak, cancel, toggle }
}
