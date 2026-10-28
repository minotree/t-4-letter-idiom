// Requires Toss dev on 5175 and dedicated temporary Chromium CDP on 9223.
// Injects a local SDK mock; never requests a real advertisement.
import assert from 'node:assert/strict';

const target = await (await fetch('http://127.0.0.1:9223/json/new?about:blank', { method: 'PUT' })).json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let id = 0;
const pending = new Map();
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  const task = pending.get(message.id);
  if (task) { pending.delete(message.id); message.error ? task.reject(message.error) : task.resolve(message.result); }
};
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const sequence = ++id;
    const timeout = setTimeout(() => { pending.delete(sequence); reject(new Error(method)); }, 15000);
    pending.set(sequence, { resolve: value => { clearTimeout(timeout); resolve(value); }, reject });
    socket.send(JSON.stringify({ id: sequence, method, params }));
  });
}
async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function until(expression) {
  for (let i = 0; i < 100; i++) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(expression);
}
try {
  await cdp('Page.enable');
  await cdp('Page.bringToFront');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await cdp('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.__bannerCalls = [];
    window.__appsInToss = { ads: {
      initialize: Object.assign(({callbacks}) => {
        if (location.hash === '#init-failure') callbacks.onInitializationFailed(new Error('mock'));
        else callbacks.onInitialized();
      }, {isSupported: () => location.hash !== '#unsupported'}),
      attachBanner: (id, target, options) => {
        window.__bannerCalls.push(id);
        window.__bannerCallbacks = options.callbacks;
        const child = document.createElement('div');
        child.style.height = '96px';
        child.textContent = 'Mock advertisement';
        target.append(child);
        options.callbacks.onAdRendered({});
        return {destroy: () => child.remove()};
      }
    }};
  ` });
  await cdp('Page.navigate', { url: 'http://127.0.0.1:5175/' });
  await until(`document.querySelector('.bottom-banner') && getComputedStyle(document.querySelector('.bottom-banner')).visibility === 'visible'`);
  assert.equal(await evaluate(`window.__bannerCalls.every(id => id === 'ait.v2.live.e2aee41b54214449')`), true);
  for (const width of [320, 390, 844]) {
    await cdp('Emulation.setDeviceMetricsOverride', { width, height: 844, deviceScaleFactor: 1, mobile: true });
    await until(`(() => {
      const banner = document.querySelector('.bottom-banner').getBoundingClientRect();
      const nav = document.querySelector('.bottom-nav').getBoundingClientRect();
      return banner.height === 96 && banner.bottom <= nav.top + 1 && banner.left >= -1 && banner.right <= innerWidth + 1 && parseFloat(getComputedStyle(document.querySelector('.app')).paddingBottom) >= document.querySelector('.bottom-dock').offsetHeight;
    })()`);
  }
  await evaluate(`document.querySelectorAll('.bottom-nav button')[1].click()`);
  await until(`!!document.querySelector('.learning-tabs')`);
  await evaluate(`document.querySelectorAll('.learning-tabs button')[1].click()`);
  await until(`!!document.querySelector('input[type=search]')`);
  await evaluate(`document.querySelector('input[type=search]').focus()`);
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.bottom-banner')).visibility`), 'hidden');
  await evaluate(`document.activeElement.blur()`);
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.bottom-banner')).visibility`), 'visible');
  for (const callback of ['onNoFill', 'onAdFailedToRender']) {
    await evaluate(`window.__bannerCallbacks.${callback}({})`);
    await until(`document.querySelector('.bottom-banner').hidden`);
    assert.equal(await evaluate(`document.querySelector('.bottom-dock').offsetHeight === document.querySelector('.bottom-nav').offsetHeight`), true);
    await evaluate(`window.__bannerCallbacks.onAdRendered({})`);
    await until(`!document.querySelector('.bottom-banner').hidden`);
  }
  for (const mode of ['unsupported', 'init-failure']) {
    await cdp('Page.navigate', { url: `http://127.0.0.1:5175/?case=${mode}#${mode}` });
    await until(`document.querySelector('.bottom-banner')?.hidden`);
    assert.equal(await evaluate(`window.__bannerCalls.length`), 0);
  }
  console.log('PASS: banner layout, production ID, input hiding, no-fill, render/init failure, unsupported environment (mock SDK).');
} finally {
  await cdp('Page.close');
  socket.close();
}

