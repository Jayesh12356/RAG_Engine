"use client"

import * as React from "react"

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  abort?: () => void
  onstart: ((event: Event) => void) | null
  onend: ((event: Event) => void) | null
  onerror: ((event: Event) => void) | null
  onresult: ((event: Event) => void) | null
}

interface SpeechRecognitionGlobals {
  SpeechRecognition?: { new (): SpeechRecognitionLike }
  webkitSpeechRecognition?: { new (): SpeechRecognitionLike }
}

export interface UseSpeechRecognitionOptions {
  /** BCP-47 language tag, defaults to navigator.language. */
  lang?: string
  /** Fired with the live (interim) transcript. */
  onPartial?: (text: string) => void
  /** Fired with the final transcript when the user stops talking. */
  onFinal?: (text: string) => void
  /** Fired on terminal errors. */
  onError?: (error: string) => void
}

export interface SpeechRecognitionState {
  supported: boolean
  listening: boolean
  start: () => void
  stop: () => void
  toggle: () => void
  error: string | null
}

export function useSpeechRecognition(options: UseSpeechRecognitionOptions = {}): SpeechRecognitionState {
  const { lang, onPartial, onFinal, onError } = options
  const [listening, setListening] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const recognitionRef = React.useRef<SpeechRecognitionLike | null>(null)
  const onPartialRef = React.useRef(onPartial)
  const onFinalRef = React.useRef(onFinal)
  const onErrorRef = React.useRef(onError)

  onPartialRef.current = onPartial
  onFinalRef.current = onFinal
  onErrorRef.current = onError

  const supported = React.useMemo(() => {
    if (typeof window === "undefined") return false
    const w = window as unknown as SpeechRecognitionGlobals
    return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition)
  }, [])

  const ensureInstance = React.useCallback((): SpeechRecognitionLike | null => {
    if (!supported) return null
    if (recognitionRef.current) return recognitionRef.current
    const w = window as unknown as SpeechRecognitionGlobals
    const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition
    if (!Ctor) return null
    const instance = new Ctor()
    instance.continuous = false
    instance.interimResults = true
    instance.lang = lang || (typeof navigator !== "undefined" ? navigator.language : "en-US")

    instance.onstart = () => {
      setListening(true)
      setError(null)
    }
    instance.onend = () => {
      setListening(false)
    }
    instance.onerror = (event: Event) => {
      const err = (event as unknown as { error?: string }).error || "Speech recognition error"
      setError(err)
      onErrorRef.current?.(err)
      setListening(false)
    }
    instance.onresult = (event: Event) => {
      const e = event as unknown as {
        results: Array<{
          0: { transcript: string }
          isFinal: boolean
          length: number
        }>
        resultIndex: number
      }
      let finalText = ""
      let interimText = ""
      for (let i = e.resultIndex; i < e.results.length; i += 1) {
        const item = e.results[i]
        const transcript = item[0]?.transcript || ""
        if (item.isFinal) finalText += transcript
        else interimText += transcript
      }
      if (interimText) onPartialRef.current?.(interimText)
      if (finalText) onFinalRef.current?.(finalText.trim())
    }

    recognitionRef.current = instance
    return instance
  }, [lang, supported])

  const start = React.useCallback(() => {
    const instance = ensureInstance()
    if (!instance) return
    try {
      instance.start()
    } catch {
      // start() throws if already running; ignore.
    }
  }, [ensureInstance])

  const stop = React.useCallback(() => {
    const instance = recognitionRef.current
    if (!instance) return
    try {
      instance.stop()
    } catch {
      /* no-op */
    }
  }, [])

  const toggle = React.useCallback(() => {
    if (listening) stop()
    else start()
  }, [listening, start, stop])

  React.useEffect(() => {
    return () => {
      const instance = recognitionRef.current
      if (instance) {
        try {
          if (typeof instance.abort === "function") {
            instance.abort()
          } else {
            instance.stop()
          }
        } catch {
          /* no-op */
        }
      }
    }
  }, [])

  return { supported, listening, start, stop, toggle, error }
}
