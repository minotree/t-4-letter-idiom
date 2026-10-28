// Requires production preview on 5175 and dedicated temporary Chromium CDP on 9223. Clears test origin storage.
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';

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
  for (let i = 0; i < 200; i++) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(expression);
}

try {
  await cdp('Page.enable');
  await cdp('Page.bringToFront');
  await cdp('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true});
  await cdp('Storage.clearDataForOrigin', {origin:'http://127.0.0.1:5175',storageTypes:'all'});
  await cdp('Page.addScriptToEvaluateOnNewDocument', {source:'Math.random = () => 0;'});
  await cdp('Page.navigate', {url:'http://127.0.0.1:5175/'});
  await until(`!!document.querySelector('.home-courses')`);
  const datasets = [JSON.parse(await readFile('apps/toss/src/data/idioms.json','utf8')), JSON.parse(await readFile('data/english/words.json','utf8'))];
  for (const [index,mode] of ['hanja','english'].entries()) {
    const root = `[aria-label="${mode==='hanja'?'\uD55C\uC790':'\uC601\uC5B4'} \uD559\uC2B5"]`;
    const q = selector => JSON.stringify(root+' '+selector);
    await evaluate(`document.querySelectorAll('.bottom-nav button')[${index+1}].click()`);
    await until(`!!document.querySelector(${q('.letters button')})`);
    assert.equal(await evaluate(`!!document.querySelector('.completion-celebration')`),false);
    for (let step=1;step<=10;step++) {
      await evaluate(`document.querySelector(${q('.letters button:not(:disabled)')}).click()`);
      await until(`!!document.querySelector(${q('.cards li')})`);
      const id = await evaluate(`document.querySelector(${q('.cards li')}).dataset.id`);
      const item = datasets[index].find(item=>item.id===id);
      const letter = await evaluate(`document.querySelector(${q('.letters button[aria-pressed=true] strong')}).textContent`);
      const answer = mode==='hanja'?item.reading:item.word.split('/').map(s=>s.trim()).find(s=>s.toUpperCase().includes(letter));
      await evaluate(`document.querySelector(${q('.candidate input')}).click()`);
      await evaluate(`(()=>{const e=document.querySelector(${q('form input')});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(answer)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
      if (step===10) {
        await evaluate(`(()=>{const e=document.querySelector(${q('form input')});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'wrong-answer');e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
        await evaluate(`document.querySelector(${q('form')}).requestSubmit()`);
        assert.equal(await evaluate(`!!document.querySelector('.completion-celebration')`),false,'wrong answer must not celebrate');
        await evaluate(`(()=>{const e=document.querySelector(${q('form input')});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(answer)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
      }
      await evaluate(`document.querySelector(${q('form')}).requestSubmit()`);
      await until(`document.querySelector(${q('progress')}).value===${step}`);
      assert.equal(await evaluate(`!!document.querySelector('.completion-celebration')`),step===10);
    }
    assert.equal(await evaluate(`document.querySelectorAll('.completion-confetti-piece').length`),72);
    assert.deepEqual(await evaluate(`Array.from(new Set(Array.from(document.querySelectorAll('.completion-confetti-piece'),e=>e.style.getPropertyValue('--confetti-start'))))`),['15%','50%','85%']);
    assert.equal(await evaluate(`(()=>{
      const piece=document.querySelector('.completion-confetti-piece');
      const animation=piece.getAnimations()[0];
      const original=animation.currentTime;
      animation.pause();
      const sample=t=>{animation.currentTime=t;const style=getComputedStyle(piece);return {matrix:new DOMMatrixReadOnly(style.transform),opacity:Number(style.opacity)};};
      const rising=sample(500),peak=sample(1320),falling=sample(2100),end=sample(2400);
      animation.currentTime=original;animation.play();
      return peak.matrix.m42<rising.matrix.m42 && falling.matrix.m42>peak.matrix.m42
        && Math.abs(falling.matrix.m41-peak.matrix.m41)<.01 && end.opacity===0;
    })()`),true,'confetti rises, falls at peak x, and fades');
    assert.equal(await evaluate(`JSON.parse(localStorage.getItem('idioms:toss:${mode}:v1')).sessions`),1);
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.completion-celebration')).pointerEvents`),'none');
    assert.equal(await evaluate(`document.querySelector('.completion-celebration').getBoundingClientRect().bottom <= document.querySelector('.bottom-dock').getBoundingClientRect().top+1`),true);
    await cdp('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.completion-celebration')).display`),'none');
    await cdp('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]});
    await mkdir('tmp/browser-checks',{recursive:true});
    await evaluate(`document.querySelector(${q('.summary')}).scrollIntoView({block:'center'})`);
    await new Promise(resolve=>setTimeout(resolve,900));
    await cdp('Page.captureScreenshot',{format:'png'}).then(r=>writeFile(`tmp/browser-checks/toss-${mode}-celebration.png`,Buffer.from(r.data,'base64')));
    if (mode==='hanja') {
      await until(`!document.querySelector('.completion-celebration')`);
    } else {
      await evaluate(`document.querySelector('.bottom-nav button').click()`);
      await until(`!document.querySelector('.completion-celebration')`);
      await evaluate(`document.querySelectorAll('.bottom-nav button')[2].click()`);
      assert.equal(await evaluate(`!!document.querySelector('.completion-celebration')`),false,'returning must not replay');
    }
    await evaluate(`document.querySelector(${q('.summary button')}).click()`);
    await until(`document.querySelector(${q('progress')}).value===0`);
    assert.equal(await evaluate(`!!document.querySelector('.completion-celebration')`),false);
  }
  console.log('PASS: Hanja/English 10-answer celebration, no premature/wrong-answer celebration, 72 confetti pieces from three launch points, pointer passthrough, dock exclusion, reduced motion, timeout, navigation cancellation/no replay, restart.');
} finally { await cdp('Page.close'); socket.close(); }
