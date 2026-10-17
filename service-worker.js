/* Cache do shell para abrir as páginas visitadas; preços e API precisam de internet. */
const CACHE = 'tradepulse-shell-v2';
const SHELL = [
  './',
  './index.html',
  './dashboard.html',
  './operar.html',
  './risco.html',
  './alertas.html',
  './simulador.html',
  './backtest.html',
  './desempenho.html',
  './conexao.html',
  './common.css',
  './common.js',
  './app-enhancements.js',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png'
];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache =>
    cache.addAll(SHELL).catch(() => Promise.all(SHELL.map(url => cache.add(url).catch(() => null))))
  ).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(key => key.startsWith('tradepulse-shell-') && key !== CACHE).map(key => caches.delete(key)))
  ).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  const url = new URL(req.url);
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).then(response => {
      if (response.ok) caches.open(CACHE).then(cache => cache.put(req, response.clone()));
      return response;
    }).catch(async () => (await caches.match(req)) || (await caches.match('./index.html'))));
    return;
  }
  if (/\.(?:html|css|js|webmanifest|svg)$/.test(url.pathname)) {
    event.respondWith(caches.match(req).then(cached => {
      const network = fetch(req).then(response => {
        if (response.ok) caches.open(CACHE).then(cache => cache.put(req, response.clone()));
        return response;
      }).catch(() => cached);
      return cached || network;
    }));
  }
});
