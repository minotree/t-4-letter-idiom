// Local-only preview: the production builds on isolated origins start with 羲暉朗曜.
// It intercepts only learning-history reads in these preview pages; it does not
// alter the regular app's storage or source code.
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const words = JSON.parse(await readFile(resolve(root, 'apps/web/src/data/idioms.json'), 'utf8'));
const target = '羲暉朗曜';
if (!words.some(word => word.id === target)) throw new Error('테스트할 한자성어를 찾지 못했습니다.');
const history = words.filter(word => word.id !== target).map(word => word.id);
const webSaved = JSON.stringify(history);
const tossSaved = JSON.stringify({ history, favorites: [], completed: [], mistakes: [], sessions: 0 });
const fixture = `<script>(()=>{const get=Storage.prototype.getItem;Storage.prototype.getItem=function(key){if(this===localStorage&&key==='idioms:web:history:v1')return ${JSON.stringify(webSaved)};if(this===localStorage&&key==='idioms:toss:hanja:v1')return ${JSON.stringify(tossSaved)};return get.call(this,key)}})();</script>`;
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.txt': 'text/plain; charset=utf-8' };

async function listen(app, port) {
  const dist = resolve(root, `apps/${app}/dist`);
  await stat(resolve(dist, 'index.html'));
  const server = createServer(async (req, res) => {
    try {
      if (req.method !== 'GET' && req.method !== 'HEAD') { res.writeHead(405).end(); return; }
      const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      if (pathname === '/sw.js') { res.writeHead(200, { 'Content-Type': 'text/javascript; charset=utf-8', 'Cache-Control': 'no-store' }).end('// Local test preview: no offline cache.'); return; }
      const path = resolve(dist, `.${pathname === '/' ? '/index.html' : pathname}`);
      if (!path.startsWith(dist + sep)) { res.writeHead(403).end(); return; }
      let contents = await readFile(path);
      if (path === resolve(dist, 'index.html')) contents = Buffer.from(contents.toString('utf8').replace('<head>', `<head>${fixture}`));
      res.writeHead(200, { 'Content-Type': mime[extname(path)] ?? 'application/octet-stream', 'Cache-Control': 'no-store' });
      res.end(req.method === 'HEAD' ? undefined : contents);
    } catch { res.writeHead(404).end(); }
  });
  await new Promise((resolveListen, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolveListen); });
  console.log(`${app}: http://127.0.0.1:${port}/${app === 'web' ? '#main' : ''}`);
}
await Promise.all([listen('web', 4195), listen('toss', 4196)]);
