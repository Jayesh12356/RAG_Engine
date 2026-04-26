// Minimal offline-shell service worker for RAG Engine.
// We pre-cache the app shell entry points and serve them from cache when
// the network is unavailable, falling back to /offline.html for any
// uncached navigation request.

const SHELL_CACHE = "rag-shell-v1"
const SHELL_URLS = ["/offline.html", "/manifest.webmanifest", "/icon.svg"]

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_URLS)),
  )
  self.skipWaiting()
})

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL_CACHE).map((k) => caches.delete(k))),
    ),
  )
  self.clients.claim()
})

self.addEventListener("fetch", (event) => {
  const { request } = event
  // Only handle GET requests; everything else (POST /query etc.) bypasses SW.
  if (request.method !== "GET") return

  // For navigations, try the network first then fall back to /offline.html.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match("/offline.html").then((cached) => cached || Response.error()),
      ),
    )
    return
  }

  // For static assets, use stale-while-revalidate against the shell cache.
  const url = new URL(request.url)
  if (url.origin === location.origin && /\.(?:js|css|svg|webmanifest|woff2?)$/i.test(url.pathname)) {
    event.respondWith(
      caches.open(SHELL_CACHE).then(async (cache) => {
        const cached = await cache.match(request)
        const network = fetch(request)
          .then((res) => {
            if (res && res.ok) cache.put(request, res.clone())
            return res
          })
          .catch(() => cached)
        return cached || network
      }),
    )
  }
})
