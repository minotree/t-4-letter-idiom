// Requires a dedicated Chromium CDP on 9236 and a local pilot server on 4187.
import assert from 'node:assert/strict';
const target = await (await fetch('http://127.0.0.1:9236/json/new?about:blank', { method: 'PUT' })).json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let sequence = 0;
const pending = new Map();
socket.onmessage = ({ data }) => {
  const message = JSON.parse(data), task = pending.get(message.id);
  if (task) { pending.delete(message.id); message.error ? task.reject(message.error) : task.resolve(message.result); }
};
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Timeout: ${method}`)); }, 15000);
    pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value); }, reject: error => { clearTimeout(timer); reject(error); } });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
try {
  await call('Page.enable');
  await call('Page.navigate', { url: 'http://127.0.0.1:4187/svg-regional-comparison/preview.html' });
  for (let i = 0; i < 100; i++) {
    if (await evaluate(`document.querySelectorAll('object').length===3 && [...document.querySelectorAll('object')].every(o=>o.contentDocument?.querySelector('path[clip-path]'))`)) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  const counts = await evaluate(`[...document.querySelectorAll('object')].map(o=>o.contentDocument?.querySelectorAll('path[clip-path]').length)`);
  assert.deepEqual(counts, [13, 16, 16]);
  await evaluate(`new Promise(resolve=>setTimeout(resolve,1500))`);
  const offsets = await evaluate(`[...document.querySelectorAll('object')].map(o=>parseFloat(getComputedStyle(o.contentDocument.querySelector('path[clip-path]')).strokeDashoffset))`);
  assert.ok(offsets.every(value => value > 0 && value < 3339), 'First strokes are animating');
  console.log('PASS: three regional SVGs load and first strokes animate');
} finally {
  socket.close();
  await fetch(`http://127.0.0.1:9236/json/close/${target.id}`);
}
