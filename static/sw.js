/**
 * Service Worker — Rádio SC News PWA
 * Cache inteligente: estáticos em cache, conteúdo dinâmico em rede
 */
const CACHE = 'radio-sc-v2';
const STATIC = ['/', '/static/icon-192.png', '/static/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(STATIC.filter(u => {
        try { new URL(u, self.location.origin); return true; } catch { return false; }
      })))
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const { request } = e;
  const url = new URL(request.url);

  // Ignora extensões e outros domínios
  if (url.origin !== self.location.origin) return;
  if (request.method !== 'GET') return;

  // API e áudio: sempre rede
  if (url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/audio/') ||
      url.pathname.startsWith('/admin')) return;

  // Estáticos (/static/, /uploads/): cache primeiro
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/uploads/')) {
    e.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(resp => {
          if (resp.ok) {
            caches.open(CACHE).then(c => c.put(request, resp.clone()));
          }
          return resp;
        }).catch(() => cached);
      })
    );
    return;
  }

  // Navegação: rede primeiro, fallback no cache
  e.respondWith(
    fetch(request)
      .then(resp => {
        if (resp.ok && url.pathname === '/') {
          caches.open(CACHE).then(c => c.put(request, resp.clone()));
        }
        return resp;
      })
      .catch(() => caches.match('/') || caches.match(request))
  );
});
