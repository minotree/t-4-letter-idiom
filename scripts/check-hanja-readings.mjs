// Dedicated temporary Chromium only. Clears the two local preview origins.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { candidatesFor } from '../packages/shared/src/index.ts';
const port = process.env.CDP_PORT ?? '9223';
const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, {method:'PUT'})).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject) => { ws.onopen=resolve;ws.onerror=reject; });
let seq=0; const pending=new Map();
ws.onmessage=({data})=>{const m=JSON.parse(data),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result);}};
function cdp(method,params={}){return new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>reject(Error(method)),15000);pending.set(id,{resolve:r=>{clearTimeout(timer);resolve(r)},reject});ws.send(JSON.stringify({id,method,params}));});}
async function ev(expression){const r=await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function until(expression){for(let i=0;i<100;i++){if(await ev(expression))return;await new Promise(r=>setTimeout(r,70));}throw Error(expression);}
const data=JSON.parse(await readFile('apps/web/src/data/idioms.json','utf8'));
const pool=data.filter(item=>[...item.reading].some(ch=>candidatesFor(data,ch,new Set([item.id]),new Set()).length));
try {
 await cdp('Page.enable');
 for(const [app,origin] of [['web','http://127.0.0.1:4173'],['toss','http://127.0.0.1:5175']]){
  await cdp('Storage.clearDataForOrigin',{origin,storageTypes:'all'});
  const index=pool.findIndex(x=>x.hanja==='竹杖芒鞋'); assert.ok(index>=0);
  const seed=await cdp('Page.addScriptToEvaluateOnNewDocument',{source:`Math.random=()=>${(index+.1)/pool.length}`});
  for(const width of [320,390,844]){
   await cdp('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:true});
   await cdp('Page.navigate',{url:origin});
   await until(app==='web'?`!!document.querySelector('a[href="#main"]')`:`!!document.querySelector('.home-course button')`);
   await ev(app==='web'?`document.querySelector('a[href="#main"]').click()`:`document.querySelector('.home-course button').click()`);
   await until(`!!document.querySelector('.hanja-reading-heading button')`);
   assert.equal(await ev(`document.querySelector('.hanja-reading-heading').textContent`),'竹杖芒鞋');
   await ev(`document.querySelector('.hanja-reading-heading button').click()`);
   await until(`!!document.querySelector('.hanja-reading-popup')`);
   const content=await ev(`document.querySelector('.hanja-reading-popup').textContent`);
   assert.match(content,/훈: 대나무.*음: 죽/);
   assert.doesNotMatch(content,/부수|획수|획순/);
   assert.equal(await ev(`(()=>{const r=document.querySelector('.hanja-reading-popup').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth})()`),true);
   await ev(`document.querySelectorAll('.hanja-reading-heading button')[1].click()`);
   assert.equal(await ev(`document.querySelector('.hanja-reading-popup strong').textContent`),'杖');
   await ev(`document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))`);
   await until(`!document.querySelector('.hanja-reading-popup')`);
   assert.equal(await ev(`document.activeElement.textContent`),'杖');
   await ev(`document.querySelector('.hanja-reading-heading button').click()`);
   await ev(`document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))`);
   await until(`!document.querySelector('.hanja-reading-popup')`);
   assert.equal((await fetch(`${origin}/hanja-license.txt`)).status,200);
  }
  await cdp('Page.removeScriptToEvaluateOnNewDocument',{identifier:seed.identifier});
  const missingIndex=pool.findIndex(x=>x.hanja.includes('車'));assert.ok(missingIndex>=0);
  const missingSeed=await cdp('Page.addScriptToEvaluateOnNewDocument',{source:`Math.random=()=>${(missingIndex+.1)/pool.length}`});
  await cdp('Page.navigate',{url:origin});
  await until(app==='web'?`!!document.querySelector('a[href="#main"]')`:`!!document.querySelector('.home-course button')`);
  await ev(app==='web'?`document.querySelector('a[href="#main"]').click()`:`document.querySelector('.home-course button').click()`);
  await until(`!!document.querySelector('.hanja-reading-heading button')`);
  await ev(`Array.from(document.querySelectorAll('.hanja-reading-heading button')).find(b=>b.textContent==='車').click()`);
  assert.doesNotMatch(await ev(`document.querySelector('.hanja-reading-popup').textContent`),/확인 중/);
  assert.match(await ev(`document.querySelector('.hanja-reading-popup').textContent`),/음:/);
  await ev(app==='web'?`location.hash='#home'`:`document.querySelector('.bottom-nav button').click()`);
  await until(`!document.querySelector('.hanja-reading-popup')`);
  await cdp('Page.removeScriptToEvaluateOnNewDocument',{identifier:missingSeed.identifier});
  for (const [character,hun,eum] of [['昃','기울','측'],['虢','나라 이름','괵'],['輶','가벼울','유'],['颻','나부낄','요'],['為','할','위'],['黙','잠잠할','묵']]) {
   const itemIndex=pool.findIndex(x=>x.hanja.includes(character)); assert.ok(itemIndex>=0,character);
   const itemSeed=await cdp('Page.addScriptToEvaluateOnNewDocument',{source:`Math.random=()=>${(itemIndex+.1)/pool.length}`});
   await cdp('Page.navigate',{url:origin});
   await until(app==='web'?`!!document.querySelector('a[href="#main"]')`:`!!document.querySelector('.home-course button')`);
   await ev(app==='web'?`document.querySelector('a[href="#main"]').click()`:`document.querySelector('.home-course button').click()`);
   await until(`!!document.querySelector('.hanja-reading-heading button')`);
   await ev(`Array.from(document.querySelectorAll('.hanja-reading-heading button')).find(b=>b.textContent===${JSON.stringify(character)}).click()`);
   const text=await ev(`document.querySelector('.hanja-reading-popup').textContent`);
   assert.ok(text.includes(`훈: ${hun}　음: ${eum}`),character+': '+text);
   await cdp('Page.removeScriptToEvaluateOnNewDocument',{identifier:itemSeed.identifier});
  }
  console.log(`PASS ${app}: 竹 display, character switching, Escape/focus, outside close, license, 320/390/844px`);
 }
} finally {await cdp('Page.close');ws.close();}
