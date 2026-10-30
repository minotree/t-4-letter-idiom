import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { hanjaReadings } from '../src/index.ts';
const read = path => readFileSync(new URL(`../../../${path}`, import.meta.url));
const data = JSON.parse(read('data/hanja-readings/readings.json'));
const audit = JSON.parse(read('data/hanja-readings/review.json'));

test('음훈 자료는 원본 해시·미확인 글자·사용자 승인 표현을 보존한다', () => {
  assert.equal(createHash('sha256').update(read('data/hanja-research/pilot/source-analysis/libhangul-hanja.txt')).digest('hex'), audit.sourceSha256);
  assert.equal(Object.keys(data).length, audit.total);
  assert.equal(Object.values(data).filter(v => v.length).length, audit.available);
  assert.deepEqual(Object.keys(data).filter(c => !data[c].length), audit.pending);
  for (const pairs of Object.values(data)) {
    assert.equal(new Set(pairs.map(x => `${x.hun}:${x.eum}`)).size, pairs.length);
    for (const pair of pairs) { assert.ok(pair.hun.trim()); assert.match(pair.eum, /^[가-힣]$/); }
  }
  assert.ok(hanjaReadings(data, '竹').some(x => x.hun === '대나무' && x.eum === '죽'));
  assert.equal(audit.available, 1566);
  assert.equal(audit.pending.length, 0);
  assert.equal(audit.supplemented.length, 44);
  const supplements = JSON.parse(read('data/hanja-readings/supplements.json'));
  assert.equal(createHash('sha256').update(read('data/hanja-readings/supplements.json')).digest('hex'), audit.supplementsSha256);
  assert.equal(new Set(supplements.entries.map(e => e.character)).size, 44);
  for (const entry of supplements.entries) {
    assert.ok(hanjaReadings(data, entry.character).length, entry.character);
    if (entry.kind === 'canonical-alias') assert.equal(entry.character.normalize('NFC'), entry.target);
  }
  assert.deepEqual(hanjaReadings(data, '樂'), hanjaReadings(data, '樂'));
  for (const [c, hun, eum] of [['昃','기울','측'],['虢','나라 이름','괵'],['輶','가벼울','유'],['颻','나부낄','요'],['為','할','위'],['黙','잠잠할','묵']]) {
    assert.ok(hanjaReadings(data, c).some(p => p.hun === hun && p.eum === eum), c);
  }
  assert.deepEqual(hanjaReadings(data, '?'), []);
  assert.ok(hanjaReadings(data, '樂').some(x => x.eum === '악'));
  assert.ok(hanjaReadings(data, '樂').some(x => x.eum === '요'));
});
