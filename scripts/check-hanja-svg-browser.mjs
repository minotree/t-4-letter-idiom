// Requires the isolated preview server on 4186 and dedicated Chromium CDP on 9236.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
const base = new URL('../data/hanja-research/pilot/svg-local/', import.meta.url);
const target = await (await fetch('http://127.0.0.1:9236/json/new?about:blank', { method: 'PUT' })).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let id = 0;
const pending = new Map();
ws.onmessage = ({ data }) => {
  const message = JSON.parse(data);
  const task = pending.get(message.id);
  if (task) { pending.delete(message.id); message.error ? task.reject(message.error) : task.resolve(message.result); }
};
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const sequence = ++id;
    const timer = setTimeout(() => { pending.delete(sequence); reject(new Error(`Timeout: ${method}`)); }, 30000);
    pending.set(sequence, { resolve: value => { clearTimeout(timer); resolve(value); }, reject: error => { clearTimeout(timer); reject(error); } });
    ws.send(JSON.stringify({ id: sequence, method, params }));
  });
}
async function evaluate(expression) {
  const r = await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}
const sample = `Array.from(document.querySelectorAll('object'), o => ({file:o.getAttribute('data'),paths:Array.from(o.contentDocument.querySelectorAll('path[clip-path]'),p=>({offset:parseFloat(getComputedStyle(p).strokeDashoffset),state:getComputedStyle(p).animationPlayState,animation:p.getAnimations()[0]?.playState}))}))`;
try {
  await cdp('Page.enable');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 1280, height: 960, deviceScaleFactor: 1, mobile: false });
  await cdp('Page.navigate', { url: 'http://127.0.0.1:4186/preview.html' });
  let loaded = false;
  for (let i = 0; i < 50; i++) {
    loaded = await evaluate(`document.querySelectorAll('object').length===5 && Array.from(document.querySelectorAll('object')).every(o=>o.contentDocument?.querySelector('path[clip-path]'))`);
    if (loaded) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(loaded, 'All five SVG documents load');
  await evaluate(`new Promise(r=>setTimeout(r,1400))`);
  const running = await evaluate(sample);
  assert.ok(running.every(r => r.paths[0].offset > 0 && r.paths[0].offset < 3339), 'First stroke is progressing in all files');
  assert.ok(running.every(r => r.paths[1].offset > 3300), 'Later strokes are still waiting');
  await evaluate(`control('paused'); new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))`);
  const paused = await evaluate(sample);
  await evaluate(`new Promise(r=>setTimeout(r,300))`);
  const held = await evaluate(sample);
  assert.ok(held.every(r => r.paths.every(p => p.state === 'paused')));
  assert.ok(held.every((r,i) => Math.abs(r.paths[0].offset-paused[i].paths[0].offset)<2), 'Pause holds progress');
  await evaluate(`control('running'); new Promise(r=>setTimeout(r,19000))`);
  const ended = await evaluate(sample);
  assert.ok(ended.every(r => r.paths.every(p => p.offset === 0)), 'All strokes finish after resume');
  const screenshot = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  await writeFile(new URL('preview-complete.png', base), Buffer.from(screenshot.data, 'base64'));
  await writeFile(new URL('browser-results.json', base), JSON.stringify({ checkedAt: new Date().toISOString(), browser: (await cdp('Browser.getVersion')).product, checks: ['five SVG documents load', 'first stroke progresses while later strokes wait', 'pause holds progress', 'resume completes all strokes'], pathCounts: ended.map(r=>({file:r.file,count:r.paths.length})), koreanLearningStandardCompared: false, coldOfflineReloadTested: false }, null, 2)+'\n');
  console.log('PASS: 5 SVGs load, animate in sequence, pause, resume and finish.');
} finally { ws.close(); }
