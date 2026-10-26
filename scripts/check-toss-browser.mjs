// Run Toss dev on 5174 and a dedicated headless Chromium CDP on 9223. Clears only the test origin storage.
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { candidatesFor, normalizeReadingForSearch } from '../packages/shared/src/index.ts';

const dataset = JSON.parse(await readFile(new URL('../apps/toss/src/data/idioms.json', import.meta.url), 'utf8'));
const target = await (await fetch('http://127.0.0.1:9223/json/new?about:blank', { method: 'PUT' })).json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let id = 0;
const pending = new Map();
const pageErrors = [];
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown') pageErrors.push(message.params.exceptionDetails);
  const task = pending.get(message.id);
  if (task) { pending.delete(message.id); message.error ? task.reject(message.error) : task.resolve(message.result); }
};
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const sequence = ++id;
    const timer = setTimeout(() => { pending.delete(sequence); reject(new Error(`CDP timeout: ${method}`)); }, 15000);
    pending.set(sequence, { resolve: result => { clearTimeout(timer); resolve(result); }, reject: error => { clearTimeout(timer); reject(error); } });
    socket.send(JSON.stringify({ id: sequence, method, params }));
  });
}
async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function until(expression) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 70));
  }
  throw new Error(`Condition not met: ${expression}`);
}
const clickText = text => evaluate(`Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === ${JSON.stringify(text)} && b.getClientRects().length)?.click()`);
try {
  await cdp('Page.enable'); await cdp('Runtime.enable');
  await cdp('Page.bringToFront');
  await cdp('Storage.clearDataForOrigin', {origin:'http://127.0.0.1:5174',storageTypes:'all'});
  await cdp('Page.addScriptToEvaluateOnNewDocument', { source: 'Math.random = () => 0;' });
  await cdp('Page.navigate', {url:'http://127.0.0.1:5174/'});
  await until(`document.body.textContent.includes('아는 말이 이어지면,')`);
  await cdp('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
  await mkdir('tmp/browser-checks', { recursive: true });
  await cdp('Page.captureScreenshot',{format:'png'}).then(r=>writeFile('tmp/browser-checks/toss-home.png',Buffer.from(r.data,'base64')));
  await clickText('한자 이음 시작 ↗');
  await until(`!!document.querySelector('.letters button:not(:disabled)')`);
  await cdp('Page.captureScreenshot',{format:'png'}).then(r=>writeFile('tmp/browser-checks/toss-quiz.png',Buffer.from(r.data,'base64')));
  await evaluate(`document.querySelector('.letters button:not(:disabled)').click()`);
  await until(`!!document.querySelector('.candidate input')`);
  const candidate = await evaluate(`document.querySelector('.cards li').dataset.id`);
  const solution = dataset.find(x=>x.id===candidate).reading;
  await evaluate(`document.querySelector('.candidate input').scrollIntoView({block:'center'}); new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
  await evaluate(`document.querySelector('.candidate input').click()`);
  await until(`!document.querySelector('form input').disabled`);
  await until(`!!document.querySelector('.floating-answer')`);
  assert.equal(await evaluate(`(()=>{const f=document.querySelector('.floating-answer').getBoundingClientRect(),a=document.querySelector('.selected-candidate').getBoundingClientRect();return f.width <= innerWidth && f.top>=0 && f.bottom<=innerHeight && f.left>=0 && f.right<=innerWidth && (f.top>=a.bottom || f.bottom<=a.top);})()`),true);
  assert.equal(await evaluate(`document.activeElement.id`),'hanja-answer');
  await until(`getComputedStyle(document.querySelector('.bottom-nav')).visibility === 'hidden'`);
  await evaluate(`document.querySelector('.floating-close').click()`);
  await until(`!document.querySelector('.floating-answer')`);
  await evaluate(`document.querySelector('.candidate input').click()`);
  await until(`!!document.querySelector('.floating-answer')`);
  await evaluate(`document.querySelector('.cards').dispatchEvent(new Event('scroll'))`);
  await until(`!document.querySelector('.floating-answer')`);
  async function enter(value) {
    await evaluate(`(()=>{const e=document.querySelector('form input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    await evaluate(`document.querySelector('form').requestSubmit()`);
  }
  await enter('틀린답');
  await until(`document.body.textContent.includes('힌트:')`);
  await enter(solution);
  await until(`document.body.textContent.includes('이번 이음 1/10')`);
  assert.equal(await evaluate(`document.querySelectorAll('.chain > li').length`),2);
  assert.equal(await evaluate(`document.querySelectorAll('.chain-bridge').length`),1);
  await cdp('Page.captureScreenshot',{format:'png'}).then(r=>writeFile('tmp/browser-checks/toss-chain.png',Buffer.from(r.data,'base64')));
  await evaluate(`document.querySelector('.bottom-nav button').click()`); await evaluate(`document.querySelectorAll('.bottom-nav button')[1].click()`);
  assert.equal(await evaluate(`document.body.textContent.includes('이번 이음 1/10')`),true);
  await clickText('나의 단어장');
  await until(`document.body.textContent.includes('915개')`);
  await evaluate(`document.querySelector('.favorite-button').click()`);
  assert.equal(await evaluate(`JSON.parse(localStorage.getItem('idioms:toss:hanja:v1')).favorites.length`),1);
  assert.equal(await evaluate(`Object.keys(localStorage).some(k=>k.startsWith('idioms:web:'))`),false);
  await evaluate(`document.querySelector('.bottom-nav button').click()`); await clickText('영어 이음 시작 ↗');
  await until(`document.querySelector('[aria-label="영어 학습"] .letters button') !== null`);
  const englishWords = JSON.parse(await readFile(new URL('../data/english/words.json', import.meta.url), 'utf8'));
  for (let step = 1; step <= 10; step++) {
    await evaluate(`document.querySelector('[aria-label="영어 학습"] .letters button:not(:disabled)').click()`);
    await until(`!!document.querySelector('[aria-label="영어 학습"] .candidate input')`);
    const candidateId = await evaluate(`document.querySelector('[aria-label="영어 학습"] .cards li').dataset.id`);
    const chosen = englishWords.find(w=>w.id===candidateId);
    assert.ok(chosen, candidateId);
    const selectedLetter = await evaluate(`document.querySelector('[aria-label="영어 학습"] .letters button[aria-pressed="true"] strong').textContent`);
    await evaluate(`document.querySelector('[aria-label="영어 학습"] .candidate input').scrollIntoView({block:'center'});new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
    await evaluate(`document.querySelector('[aria-label="영어 학습"] .candidate input').click()`);
    const form = chosen.word.split('/').map(s=>s.trim()).find(s=>s.toUpperCase().includes(selectedLetter));
    await evaluate(`(()=>{const e=document.querySelector('[aria-label="영어 학습"] form input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(form)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    await evaluate(`document.querySelector('[aria-label="영어 학습"] form').requestSubmit()`);
    await until(`document.querySelector('[aria-label="영어 학습"]').textContent.includes('이번 이음 ${step}/10')`);
  }
  assert.equal(await evaluate(`JSON.parse(localStorage.getItem('idioms:toss:english:v1')).sessions`),1);
  assert.equal(await evaluate(`document.querySelector('[aria-label="영어 학습"] .chain').children.length`),11);
  assert.equal(await evaluate(`document.querySelectorAll('[aria-label="영어 학습"] .chain-complete').length`),1);
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
  for (const [width,height] of [[320,700],[844,390],[1280,900]]) {
    await cdp('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<900});
    assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true,`overflow at ${width}x${height}`);
  }
  await cdp('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await cdp('Page.captureScreenshot',{format:'png'}).then(r=>writeFile('tmp/toss-mobile.png',Buffer.from(r.data,'base64')));
  const existingRecords = {history:englishWords.filter(w=>w.level!=='special').map(w=>w.id),favorites:['english:you'],completed:['english:that'],mistakes:['english:the'],sessions:5};
  await evaluate(`localStorage.setItem('idioms:toss:english:v1',${JSON.stringify(JSON.stringify(existingRecords))})`);
  await cdp('Page.reload');
  await until(`!!document.querySelector('.home-courses')`);
  await clickText('영어 이음 시작 ↗');
  await until(`document.querySelector('[aria-label="영어 학습"] .current h2')?.textContent === 'ABSTRACTION'`);
  assert.deepEqual(JSON.parse(await evaluate(`localStorage.getItem('idioms:toss:english:v1')`)),existingRecords);
  await evaluate(`Array.from(document.querySelectorAll('[aria-label="영어 학습"] .letters button')).find(b=>b.querySelector('strong').textContent==='C').click()`);
  await until(`!!document.querySelector('li[data-id="english:accrue"] input')`);
  await evaluate(`document.querySelector('li[data-id="english:accrue"] input').scrollIntoView({block:'center'});new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
  await evaluate(`document.querySelector('li[data-id="english:accrue"] input').click()`);
  await evaluate(`(()=>{const e=document.querySelector('#english-answer');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'accrue');e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await evaluate(`document.querySelector('[aria-label="영어 학습"] form').requestSubmit()`);
  await until(`document.querySelector('[aria-label="영어 학습"] .current h2')?.textContent==='ACCRUE'`);
  const addedRecords = JSON.parse(await evaluate(`localStorage.getItem('idioms:toss:english:v1')`));
  assert.ok(addedRecords.completed.includes('english:accrue') && addedRecords.completed.includes('english:that'));
  assert.deepEqual(addedRecords.favorites,existingRecords.favorites);
  assert.deepEqual(addedRecords.mistakes,existingRecords.mistakes);
  assert.equal(addedRecords.sessions,5);
  await clickText('나의 단어장');
  await until(`!!document.querySelector('[aria-label="영어 학습"] input[type=search]')`);
  await evaluate(`(()=>{const e=document.querySelector('[aria-label="영어 학습"] input[type=search]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'abstraction');e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await until(`document.querySelector('[aria-label="영어 학습"] .book-list h3')?.textContent==='ABSTRACTION'`);
  assert.equal(pageErrors.length,0,JSON.stringify(pageErrors));
  console.log('PASS: home, mobile width, floating input, chain, book, storage separation, English 10-answer completion, special word start/candidate/answer/search, existing records retained, no runtime exceptions');
} finally { await cdp('Page.close'); socket.close(); }
