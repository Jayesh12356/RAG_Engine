"use client"

import { useEffect, useRef, useState } from "react"

export function useTypewriter(
  phrases: string[],
  {
    typeSpeed = 55,
    deleteSpeed = 28,
    holdMs = 1600,
  }: { typeSpeed?: number; deleteSpeed?: number; holdMs?: number } = {},
): string {
  const [text, setText] = useState("")
  const indexRef = useRef(0)
  const phaseRef = useRef<"type" | "hold" | "delete">("type")
  const cursorRef = useRef(0)

  useEffect(() => {
    let timer: number | undefined
    const tick = () => {
      const phrase = phrases[indexRef.current % phrases.length]
      const phase = phaseRef.current
      if (phase === "type") {
        cursorRef.current += 1
        const next = phrase.slice(0, cursorRef.current)
        setText(next)
        if (cursorRef.current >= phrase.length) {
          phaseRef.current = "hold"
          timer = window.setTimeout(tick, holdMs)
          return
        }
        timer = window.setTimeout(tick, typeSpeed + Math.random() * 30)
      } else if (phase === "hold") {
        phaseRef.current = "delete"
        timer = window.setTimeout(tick, deleteSpeed)
      } else {
        cursorRef.current -= 1
        const next = phrase.slice(0, Math.max(0, cursorRef.current))
        setText(next)
        if (cursorRef.current <= 0) {
          phaseRef.current = "type"
          indexRef.current = (indexRef.current + 1) % phrases.length
        }
        timer = window.setTimeout(tick, deleteSpeed)
      }
    }
    timer = window.setTimeout(tick, typeSpeed)
    return () => {
      if (timer) window.clearTimeout(timer)
    }
  }, [phrases, typeSpeed, deleteSpeed, holdMs])

  return text
}
