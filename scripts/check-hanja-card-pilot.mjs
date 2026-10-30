// Requires the isolated SVG preview server on 4186 and dedicated Chromium CDP on 9236.
import assert from 'node:assert/strict';
const target = await (await fetch('http://127.0.0.1:9236/json/new?about:blank', { method: 'PUT' })).json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let sequence = 0;
const pending = new Map();
socket.onmessage = ({ data }) => {
  const message = JSON.parse(data);
  const task = pending.get(message.id);
  if (task) { pending.delete(message.id); message.error ? task.reject(message.error) : task.resolve(message.result); }
};
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Timeout: ${method}`)); }, 15000);
    pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value); }, reject: error => { clearTimeout(timer); reject(error); } });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function wait(expression) {
  for (let i = 0; i < 100; i++) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(`Condition not met: ${expression}`);
}
try {
  await cdp('Page.enable');
  await cdp('Page.navigate', { url: 'http://127.0.0.1:4186/card-pilot.html' });
  await wait(`document.querySelectorAll('[data-character]').length === 4`);
  for (const width of [320, 390, 844]) {
    await cdp('Emulation.setDeviceMetricsOverride', { width, height: 700, deviceScaleFactor: 1, mobile: true });
    for (const character of ['羲', '暉', '朗', '曜']) {
      await evaluate(`document.querySelector('[data-character="${character}"]').click()`);
      assert.equal(await evaluate(`document.querySelector('dialog').open`), true);
      assert.equal(await evaluate(`document.querySelector('#character-title').textContent`), character);
      assert.equal(await evaluate(`document.documentElement.scrollWidth <= innerWidth`), true);
      assert.equal(await evaluate(`document.querySelector('dialog').scrollWidth <= document.querySelector('dialog').clientWidth`), true);
      if (character === '羲' || character === '暉') {
        assert.equal(await evaluate(`document.querySelector('#reading').textContent`), character === '羲' ? '숨 희 · 복희 희' : '빛 휘 · 햇빛 휘');
        assert.equal(await evaluate(`document.querySelector('#radical').textContent`), character === '羲' ? '羊 (양 양)' : '日 (날 일)');
        assert.equal(await evaluate(`document.querySelector('#strokes').textContent`), character === '羲' ? '16획' : '13획');
      }
      {
        await wait(`document.querySelector('object')?.contentDocument?.querySelector('path[clip-path]')`);
        assert.equal(await evaluate(`document.querySelector('#controls').hidden`), false);
        if (character === '羲') {
          assert.equal(await evaluate(`document.querySelector('#stroke-note').textContent.includes('중국 자료')`), true);
          assert.equal(await evaluate(`document.querySelector('object').getAttribute('data')`), '32690-zhhans.svg');
          assert.equal(await evaluate(`document.querySelector('object').contentDocument.querySelectorAll('path[clip-path]').length`), 16);
        }
        if (character === '暉') {
          assert.equal(await evaluate(`document.querySelector('#stroke-note').textContent.includes('일본 자료')`), true);
          assert.equal(await evaluate(`document.querySelector('object').getAttribute('data')`), '26249-ja.svg');
          assert.equal(await evaluate(`document.querySelector('object').contentDocument.querySelectorAll('path[clip-path]').length`), 13);
        }
        if (character === '朗') {
          assert.equal(await evaluate(`document.querySelector('#strokes').textContent`), '11획 (한국어기초사전 기준)');
          assert.equal(await evaluate(`document.querySelector('#radical').textContent`), '月 (달 월)');
        }
        if (character === '曜') {
          assert.equal(await evaluate(`document.querySelector('#strokes').textContent`), '18획');
          assert.equal(await evaluate(`document.querySelector('#radical').textContent`), '日 (날 일)');
        }
        await evaluate(`document.querySelector('[data-action="pause"]').click()`);
        assert.equal(await evaluate(`document.querySelector('object').contentDocument.querySelector('path[clip-path]').style.animationPlayState`), 'paused');
        await evaluate(`document.querySelector('[data-action="play"]').click()`);
        assert.equal(await evaluate(`document.querySelector('object').contentDocument.querySelector('path[clip-path]').style.animationPlayState`), 'running');
        await evaluate(`document.querySelector('[data-action="restart"]').click()`);
        await wait(`document.querySelector('object')?.contentDocument?.querySelector('path[clip-path]')`);
      }
      await evaluate(`document.querySelector('.close').click()`);
      await wait(`document.activeElement.dataset.character === '${character}'`);
      assert.equal(await evaluate(`!document.querySelector('dialog').open && !document.querySelector('object')`), true);
      assert.equal(await evaluate(`document.activeElement.dataset.character`), character);
    }
  }
  await evaluate(`document.querySelector('[data-character="羲"]').click()`);
  await cdp('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await cdp('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await wait(`!document.querySelector('dialog').open`);
  await wait(`document.activeElement.dataset.character === '羲'`);
  assert.equal(await evaluate(`document.activeElement.dataset.character`), '羲');
  console.log('PASS: 4 characters, 320/390/844px, dialog, fallbacks, playback controls, close, Escape and focus restoration');
} finally {
  socket.close();
  await fetch(`http://127.0.0.1:9236/json/close/${target.id}`);
}
