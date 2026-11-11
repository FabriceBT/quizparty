/* Service worker : rend l'application installable et garde une copie des pages/fichiers déjà vus.
   Stratégie « réseau d'abord » : on prend toujours la version la plus récente, et la copie ne sert que hors connexion. */
const CACHE = 'fouquiz-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const req = e.request, url = new URL(req.url);
  // Jamais de copie pour l'API, les WebSockets, les parties en cours ni les autres sites.
  if (req.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')
      || url.pathname.startsWith('/ws/') || url.pathname.startsWith('/j/') || url.pathname.startsWith('/q/')) return;
  e.respondWith(fetch(req).then((res) => {
    if (res.ok && (url.pathname.startsWith('/static/') || req.mode === 'navigate')) {
      const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy));
    }
    return res;
  }).catch(() => caches.match(req).then((hit) => hit || (req.mode === 'navigate'
    ? new Response('<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
        '<body style="font-family:sans-serif;text-align:center;padding:40px"><h1>📡 Hors connexion</h1>' +
        '<p>Fouquiz a besoin d’une connexion Internet pour jouer. Réessayez dans un instant.</p>' +
        '<button onclick="location.reload()" style="font-size:18px;padding:10px 20px">Réessayer</button></body>',
        { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } })
    : Response.error()))));
});
