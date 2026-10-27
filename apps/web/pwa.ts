import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import type { Plugin } from 'vite';

export function offlineApp(): Plugin {
  return {
    name: 'idioms-offline',
    apply: 'build',
    generateBundle(_, bundle) {
      const publicFiles = ['manifest.webmanifest', 'favicon.png', 'apple-touch-icon.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png'];
      const files = [...Object.keys(bundle), ...publicFiles];
      const hash = createHash('sha256').update(JSON.stringify(bundle));
      for (const file of publicFiles) hash.update(readFileSync(new URL(`public/${file}`, import.meta.url)));
      const version = hash.digest('hex').slice(0, 16);
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: `
const CACHE = 'idioms-web-${version}';
const FILES = ${JSON.stringify(files)};
const urls = FILES.map(file => new URL(file, self.registration.scope).href);
async function cachedOrFetch(request, key) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(key);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok && response.type !== 'opaque') await cache.put(key, response.clone());
  return response;
}
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(urls))));
self.addEventListener('message', event => { if (event.data?.type === 'SKIP_WAITING') self.skipWaiting(); });
self.addEventListener('activate', event => event.waitUntil((async () => {
  for (const key of await caches.keys()) if (key.startsWith('idioms-web-') && key !== CACHE) await caches.delete(key);
  await self.clients.claim();
})()));
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || new URL(event.request.url).origin !== self.location.origin) return;
  if (event.request.mode === 'navigate') {
    event.respondWith(cachedOrFetch(event.request, new URL('index.html', self.registration.scope).href));
  } else if (urls.includes(event.request.url)) {
    event.respondWith(cachedOrFetch(event.request, event.request));
  }
});
` });
    },
  };
}
