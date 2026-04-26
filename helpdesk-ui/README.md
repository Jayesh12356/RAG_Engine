# RAG Engine — UI

Next.js 14 (App Router) frontend for the [RAG Engine](../README.md) document Q&A platform. Premium glass + neutral aesthetic, light + dark themes, accessible Radix primitives, single-token typography (15/14/13/12/11px tiers), and rich answer rendering — Markdown + code + math + Mermaid + Recharts + generated images.

> Looking for the bootstrap path? Open the repo-root [`START_HERE.md`](../START_HERE.md) and paste it into Cursor / Claude / Antigravity / Codex. It installs everything (including this UI) and starts both servers.

---

## Routes

| Path | Description |
| --- | --- |
| `/` | Marketing landing page (hero, features, providers marquee, demo card, testimonial). |
| `/sign-in`, `/sign-up` | Cookie-based auth shell (lightweight; `rag_engine_uid` cookie gates `/app/*`). |
| `/app` | Authenticated entry; redirects into the in-app shell. |
| `/app/query` | One-shot grounded answers with citations and confidence. |
| `/app/chat` | Multi-turn conversation with sessions rail, slash commands and streaming. |
| `/app/documents` | Library: upload, inspect chunks, delete; supports every format the backend accepts. |
| `/app/status` | Live health tiles: provider, vector DB, relational DB, latency. |

A simple cookie-based middleware ([`src/middleware.ts`](src/middleware.ts)) redirects unauthenticated visitors from `/app/*` to `/sign-in`.

---

## Tech stack

- **Framework** — [Next.js 14](https://nextjs.org/) App Router (React 18, Server Components).
- **Styling** — Tailwind CSS, `tailwindcss-animate`, custom design tokens, light/dark via `next-themes`.
- **Primitives** — Radix UI (Dialog, DropdownMenu, Popover, Tabs, Tooltip, ScrollArea, Switch, …) wrapped in local `src/components/ui/*`.
- **Motion** — Framer Motion 12.
- **Answer rendering** — `react-markdown` + `remark-gfm` + `remark-math`, `rehype-katex`, `rehype-pretty-code` + Shiki, Mermaid, Recharts.
- **State** — local React state + cookie-backed session ([`src/lib/auth.ts`](src/lib/auth.ts)).
- **Streaming client** — Server-Sent Event reader for `/query/stream` and `/chat/stream`.
- **Icons** — `lucide-react`. **Toasts** — `sonner`. **Command palette** — `cmdk`.

---

## Local development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`. The dev server hot-reloads on save.

By default the UI talks to `http://localhost:8000`. Point at a different backend with:

```bash
# helpdesk-ui/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

When deploying to Vercel, set `NEXT_PUBLIC_API_URL` to your hosted backend URL — leaving it empty in production silently falls back to `localhost` and breaks every API call.

---

## Build, lint, type-check

```bash
npm run lint       # next lint (ESLint)
npm run build      # production build (also type-checks)
npm run start      # serve the production build locally
```

The build step type-checks the entire app and fails on any TypeScript error. CI runs `npm run lint && npm run build`.

---

## Folder layout

```text
src/
  app/
    page.tsx                   # Landing
    sign-in/, sign-up/         # Auth shell
    app/                       # Authenticated app shell
      layout.tsx               # Sidebar + topbar + onboarding tour
      query/page.tsx
      chat/page.tsx
      documents/page.tsx
      status/page.tsx
    layout.tsx, globals.css
    favicon.ico, opengraph-image.tsx
  components/
    answer/                    # MarkdownAnswer, CodeBlock, ChartBlock, SourceLink, ConfidenceGauge
    app/                       # Sidebar, Topbar, MobileNav, CommandDialog, OnboardingTour, UserMenu
    auth/                      # AuthShell, sign-in/up forms
    chat/                      # Composer, MessageBubble, SessionsRail, ConfidenceGauge, slash menu
    documents/                 # UploadZone, DocCard, InspectSheet
    landing/                   # Hero, Features, ProvidersMarquee, DemoCard, Testimonial, Footer
    query/                     # One-shot query surface helpers
    status/                    # StatusTile
    ui/                        # Primitives: Button, Card, Dialog, Dropdown, Input, Switch, Tooltip, Kbd, ...
    motion/                    # Reusable motion variants
    theme-provider.tsx
  lib/
    auth.ts                    # Cookie-based session + useSession hook
    api.ts                     # Backend client (fetch + SSE)
    motion.ts, utils.ts        # Helpers (cn, uid, formatRelativeTime, ...)
  middleware.ts                # /app/* auth gate
  types/index.ts               # Shared TS types
```

---

## Design tokens

The UI converges on a single typographic scale to keep every surface symmetric:

- **Body / reading** — `text-[15px]` (Markdown answer body, query/composer textareas, message bubble content).
- **Default UI** — `text-sm` (buttons, inputs, dropdown rows, sidebar links).
- **Compact UI** — `text-[13px]` (`Button size="sm"`, breadcrumbs, source chips, table cells, code-block body).
- **Meta** — `text-xs` (12px) (footers, disclaimers, doc-card service, sessions meta, dropdown labels).
- **Eyebrow** — single token: `text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-fg`.

Card-radius tiers: `rounded-md` (controls), `rounded-lg` (Card primitive), `rounded-xl` (inset panels), `rounded-2xl` (section / answer surfaces).

---

## Troubleshooting

- **Port 3000 in use** — Next.js will offer 3001 automatically. Set `PORT=3000` after freeing the port if you want to stay there.
- **Auth-loop on `/app/*`** — clear the `rag_engine_uid` cookie or sign in again at `/sign-in`.
- **API calls hit `localhost:8000` from Vercel** — `NEXT_PUBLIC_API_URL` is unset in your Vercel project. Set it and redeploy.
- **Mermaid / KaTeX not rendering** — ensure the page is the answer surface (these are scoped to `MarkdownAnswer`); a runtime error in the dynamic loader will fall back to the raw fenced block.

For the full backend setup (FastAPI, Qdrant, Postgres, OCR, providers) see the repo-root [`README.md`](../README.md) and [`docs/reference/MANUAL.md`](../docs/reference/MANUAL.md).
