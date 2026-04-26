"use client"

import * as React from "react"
import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"
import { cn } from "@/lib/utils"
import { ChartBlock } from "./chart-block"
import { CodeBlock } from "./code-block"
import { MermaidBlock } from "./mermaid-block"

const REMARK_PLUGINS = [remarkGfm, remarkMath]
const REHYPE_PLUGINS = [rehypeKatex]

function extractText(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") return ""
  if (typeof node === "string" || typeof node === "number") return String(node)
  if (Array.isArray(node)) return node.map(extractText).join("")
  if (
    typeof node === "object" &&
    node !== null &&
    "props" in (node as { props?: { children?: React.ReactNode } })
  ) {
    return extractText((node as { props?: { children?: React.ReactNode } }).props?.children)
  }
  return ""
}

export interface MarkdownAnswerProps {
  content: string
  streaming?: boolean
  className?: string
}

export function MarkdownAnswer({
  content,
  streaming = false,
  className,
}: MarkdownAnswerProps) {
  const components: Components = React.useMemo(
    () => ({
      // Code blocks dispatch by language to specialised renderers when not streaming.
      code(props) {
        const { className, children, ...rest } = props as React.HTMLAttributes<HTMLElement> & {
          children?: React.ReactNode
        }
        const match = /language-([\w-]+)/i.exec(className || "")
        const lang = match ? match[1].toLowerCase() : ""
        const text = extractText(children).replace(/\n$/, "")
        const isFenced = (className || "").includes("language-") || text.includes("\n")

        if (!isFenced) {
          return (
            <code
              className="rounded bg-muted px-1 py-0.5 text-[0.92em] font-mono text-fg"
              {...rest}
            >
              {children}
            </code>
          )
        }

        // Image-request blocks should be replaced server-side. If one slips
        // through (e.g. the LLM emits one when image-gen is disabled), hide it.
        if (lang === "image-request") return null

        // While streaming, never try to render mermaid / charts — they need
        // complete syntactically-valid input and would otherwise flash error
        // panes. Fall back to a plain code block.
        if (!streaming) {
          if (lang === "mermaid") {
            return <MermaidBlock code={text} />
          }
          if (lang === "chart") {
            return <ChartBlock source={text} />
          }
        }

        return <CodeBlock language={lang || "text"} code={text} />
      },
      a({ href, children, ...rest }) {
        return (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-primary underline-offset-2 hover:underline"
            {...rest}
          >
            {children}
          </a>
        )
      },
      img({ src, alt }) {
        if (!src || typeof src !== "string") return null
        return (
          // Markdown answers can contain arbitrary remote URLs and base64
          // data: URLs from server-side image generation, neither of which fit
          // the next/image domain allowlist model — render as a plain <img>.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={alt || ""}
            className="my-3 h-auto max-w-full rounded-lg border border-border bg-card shadow-card"
          />
        )
      },
      table({ children, ...rest }) {
        return (
          <div className="my-3 overflow-x-auto rounded-lg border border-border">
            <table
              className="w-full border-collapse text-left text-[13px] tabular-nums"
              {...rest}
            >
              {children}
            </table>
          </div>
        )
      },
      thead({ children, ...rest }) {
        return (
          <thead
            className="bg-muted/60 text-[12px] font-semibold uppercase tracking-[0.18em] text-muted-fg"
            {...rest}
          >
            {children}
          </thead>
        )
      },
      th({ children, ...rest }) {
        return (
          <th
            className="border-b border-border px-3 py-2 align-bottom font-semibold text-fg"
            {...rest}
          >
            {children}
          </th>
        )
      },
      td({ children, ...rest }) {
        return (
          <td
            className="border-b border-border/60 px-3 py-2 align-top text-fg"
            {...rest}
          >
            {children}
          </td>
        )
      },
      tr({ children, ...rest }) {
        return (
          <tr className="even:bg-muted/30" {...rest}>
            {children}
          </tr>
        )
      },
      ul({ children, ...rest }) {
        return (
          <ul className="my-2 list-disc space-y-1 pl-5 marker:text-primary" {...rest}>
            {children}
          </ul>
        )
      },
      ol({ children, ...rest }) {
        return (
          <ol className="my-2 list-decimal space-y-1 pl-5 marker:text-primary" {...rest}>
            {children}
          </ol>
        )
      },
      li({ children, ...rest }) {
        return (
          <li className="leading-relaxed" {...rest}>
            {children}
          </li>
        )
      },
      blockquote({ children, ...rest }) {
        return (
          <blockquote
            className="my-3 border-l-2 border-primary/50 bg-primary/5 px-3 py-2 text-fg/90"
            {...rest}
          >
            {children}
          </blockquote>
        )
      },
      h1({ children, ...rest }) {
        return (
          <h1 className="mt-4 mb-2 text-xl font-semibold tracking-[-0.02em] text-fg" {...rest}>
            {children}
          </h1>
        )
      },
      h2({ children, ...rest }) {
        return (
          <h2 className="mt-4 mb-2 text-lg font-semibold tracking-[-0.02em] text-fg" {...rest}>
            {children}
          </h2>
        )
      },
      h3({ children, ...rest }) {
        return (
          <h3 className="mt-3 mb-1.5 text-base font-semibold text-fg" {...rest}>
            {children}
          </h3>
        )
      },
      p({ children, ...rest }) {
        return (
          <p className="my-2 leading-relaxed text-fg" {...rest}>
            {children}
          </p>
        )
      },
      hr() {
        return <hr className="my-4 border-border" />
      },
      strong({ children, ...rest }) {
        return (
          <strong className="font-semibold text-fg" {...rest}>
            {children}
          </strong>
        )
      },
    }),
    [streaming],
  )

  return (
    <div
      className={cn(
        "markdown-answer text-[15px] leading-relaxed text-fg",
        "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
        className,
      )}
    >
      <ReactMarkdown
        remarkPlugins={REMARK_PLUGINS}
        rehypePlugins={REHYPE_PLUGINS}
        components={components}
      >
        {content || ""}
      </ReactMarkdown>
    </div>
  )
}
