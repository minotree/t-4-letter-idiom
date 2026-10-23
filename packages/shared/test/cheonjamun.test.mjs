import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { loadIdioms, normalizeHanjaForSearch, candidatesFor } from '../src/index.ts';

const read = path => readFileSync(new URL(`../../../${path}`, import.meta.url), 'utf8');
const csv = read('data/cheonjamun/reviewed/cheonjamun.csv');
const review = JSON.parse(read('data/cheonjamun/reviewed/review.json'));
const additions = loadIdioms(csv);

test('검토본은 해시·종류·교정·출제 보류를 지킨다', () => {
  assert.equal(createHash('sha256').update(csv).digest('hex'), review.reviewed_csv_sha256);
  assert.equal(additions.length, 244);
  assert.ok(additions.every(item => item.category === 'cheonjamun' && [...item.hanja].length === 4));
  assert.equal(additions.find(item => item.hanja === '恬筆倫紙').reading, '염필륜지');
  for (const item of review.items.filter(item => item.action === 'hold')) {
    assert.ok(!additions.some(row => row.hanja === item.original.hanja));
  }
});

test('통합 JSON은 기존 ID·분류를 보존하고 중복 없이 다른 종류로 연결한다', () => {
  const merged = JSON.parse(read('apps/web/src/data/idioms.json'));
  const original = loadIdioms(read('sajaseongeo_image_working.csv'));
  assert.equal(merged.length, 909);
  assert.equal(new Set(merged.map(item => normalizeHanjaForSearch(item.hanja))).size, merged.length);
  assert.deepEqual(merged.slice(0, original.length), original);
  assert.equal(merged.filter(item => item.hanja === '夫唱婦隨').length, 1);
  assert.equal(merged.find(item => item.hanja === '夫唱婦隨').category, 'idiom');
  const eligible = candidatesFor(merged, '가', new Set(['家家戶戶']), new Set());
  assert.ok(eligible.some(item => item.category === 'idiom'));
  assert.ok(eligible.some(item => item.category === 'cheonjamun'));
  assert.ok(!eligible.some(item => item.id === '家家戶戶'));
});

test('기감훼상은 감불생심을 사용한 뒤에도 한글 독음으로 이어진다', () => {
  const merged = JSON.parse(read('apps/web/src/data/idioms.json'));
  const used = new Set(['豈敢毁傷', '敢不生心']);
  for (const ch of '기감훼상') {
    const expected = merged.filter(item => item.reading.includes(ch) && !used.has(item.id));
    assert.deepEqual(candidatesFor(merged, ch, used, new Set()), expected);
  }
  assert.ok(candidatesFor(merged, '상', used, new Set()).some(item => item.reading === '설상가상'));
});
