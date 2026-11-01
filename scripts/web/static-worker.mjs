// Build a closed allow-list from public build files. No private runtime caching.
import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

export async function writeStaticWorker(outDir) {
  const files = [];
  async function scan(path = '') {
    for (const item of await readdir(join(outDir, path), { withFileTypes: true })) {
      const name = path ? `${path}/${item.name}` : item.name;
      if (item.isDirectory()) await scan(name);
      else if (name === 'offline.html' || name === 'offline.css' || name === 'manifest.webmanifest' || name === 'mark.svg' || /^icon-\d+\.png$/.test(name) || name.startsWith('assets/')) files.push(`/${name}`);
    }
  }
  await scan();
  files.sort();
  const digest = createHash('sha256');
  for (const file of files) digest.update(await readFile(join(outDir, file)));
  const version = digest.digest('hex').slice(0, 16);
  const source = `const CACHE = 'arbit-static-${version}';
const STATIC = new Set(${JSON.stringify(files)});
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll([...STATIC]))));
self.addEventListener('activate', event => event.waitUntil(Promise.all([caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('arbit-static-') && key !== CACHE).map(key => caches.delete(key)))), self.clients.claim()])));
self.addEventListener('message', event => { if (event.data === 'APPLY_UPDATE') self.skipWaiting(); });
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (/^\\/(api|auth|internal|exports|events)(\\/|$)/.test(url.pathname)) return;
  if (STATIC.has(url.pathname) && !url.search) {
    event.respondWith(caches.open(CACHE).then(async cache => (await cache.match(event.request)) || fetch(event.request)));
    return;
  }
  if (event.request.mode === 'navigate') event.respondWith(fetch(event.request).catch(() => caches.open(CACHE).then(cache => cache.match('/offline.html'))));
});
`;
  await writeFile(join(outDir, 'sw.js'), source);
  return { version, files };
}
