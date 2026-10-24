import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeReadingForSearch, matchingAnswers, candidatesFor } from '../src/index.ts';

test('독음 검색은 두음 변이와 받침을 비교하고 퀴즈 판정은 유지한다', () => {
  for (const [a, b] of [['녹', '록'], ['유', '류'], ['이', '리'], ['여', '녀'], ['예', '례'], ['낙', '락'], ['뇌', '뢰']]) {
    assert.equal(normalizeReadingForSearch(a), normalizeReadingForSearch(b));
  }
  assert.ok(normalizeReadingForSearch('청산유수').includes(normalizeReadingForSearch('류')));
  assert.equal(normalizeReadingForSearch(' 녹 의 홍 상 '), normalizeReadingForSearch('녹의홍상'));
  assert.notEqual(normalizeReadingForSearch('록'), normalizeReadingForSearch('로'));
  assert.notEqual(normalizeReadingForSearch('가'), normalizeReadingForSearch('나'));
  assert.equal(matchingAnswers([{ reading: '청산유수' }], '청산류수').length, 0);
});

test('문제 후보는 두음 변이를 허용하며 세션 제외·미출제 우선을 유지한다', () => {
  const items = [
    { id: 'a', reading: '녹의홍상' },
    { id: 'b', reading: '세록치부' },
    { id: 'c', reading: '홍로점설' },
    { id: 'd', reading: '청산유수' },
  ];
  assert.deepEqual(candidatesFor(items, '녹', new Set(), new Set()).map(x => x.id), ['a', 'b']);
  assert.deepEqual(candidatesFor(items, '록', new Set(['a']), new Set()).map(x => x.id), ['b']);
  assert.deepEqual(candidatesFor(items, '녹', new Set(), new Set(['a'])).map(x => x.id), ['b']);
  assert.deepEqual(candidatesFor(items, '록', new Set(), new Set(['a', 'b'])).map(x => x.id), ['a', 'b']);
  assert.deepEqual(candidatesFor(items, '류', new Set(), new Set()).map(x => x.id), ['d']);
  assert.deepEqual(candidatesFor(items, '녹록', new Set(), new Set()), []);
});
