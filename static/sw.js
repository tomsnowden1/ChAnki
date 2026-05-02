const VERSION = 'v2';
const STATIC_CACHE = `chanki-static-${VERSION}`;
const API_CACHE = `chanki-api-${VERSION}`;

const STATIC_ASSETS = [
  '/',
  '/static/app.js',
  '/static/tone.js',
  '/static/chanki.css',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/vendor/lucide.js',
  '/static/fonts/source-serif-4.woff2',
  '/static/fonts/inter-tight.woff2',
  '/static/fonts/jetbrains-mono.woff2',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== STATIC_CACHE && k !== API_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Never cache queue submissions or any sync writes
  if (url.pathname.startsWith('/api/sync/')) return;

  // Network-first for read-only API endpoints
  if (url.pathname.startsWith('/api/search') || url.pathname.startsWith('/api/settings')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          // Only cache successful responses — never store 4xx/5xx in the cache
          if (res.ok) {
            const copy = res.clone();
            caches.open(API_CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Cache-first for static shell
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req).then((res) => {
        if (res.ok && (url.pathname === '/' || url.pathname.startsWith('/static/'))) {
          const copy = res.clone();
          caches.open(STATIC_CACHE).then((c) => c.put(req, copy));
        }
        return res;
      }))
    );
  }
});
