import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadIdioms, candidatesFor, matchingAnswers, readingHint, normalizeHanjaForSearch, migrateIdiomHistory, SESSION_LIMIT } from '../src/index.ts';

const idioms = loadIdioms(readFileSync(new URL('../../../sajaseongeo_image_working.csv', import.meta.url), 'utf8'));

test('천자문 종류를 보존하고 잘못된 종류를 거절하며 기존 ID를 유지한다', () => {
  const rows = loadIdioms('category,hanja,reading,meaning\ncheonjamun,天地玄黃,천지현황,하늘과 땅의 빛깔');
  assert.equal(rows[0].category, 'cheonjamun');
  assert.equal(rows[0].id, '天地玄黃');
  assert.throws(() => loadIdioms('category,hanja,reading,meaning\nunknown,天地玄黃,천지현황,뜻'));
  assert.throws(() => loadIdioms('category,hanja,reading,meaning\n,天地玄黃,천지현황,뜻'));
});
test('최종 CSV를 검증하고 제작 관리 열을 제외한다', () => {
  assert.equal(idioms.length, 666);
  assert.equal(new Set(idioms.map(item => item.id)).size, idioms.length);
  assert.deepEqual(Object.keys(idioms[0]), ['id', 'category', 'hanja', 'reading', 'meaning']);
  assert.ok(idioms.every(item => item.category === 'idiom'));
});
test('따옴표·쉼표·줄바꿈·BOM을 읽고 손상된 CSV를 거절한다', () => {
  const rows = loadIdioms('\uFEFFhanja,reading,meaning\r\n家家戶戶,가가호호,"집마다, 모든 집\n""뜻"""');
  assert.equal(rows[0].meaning, '집마다, 모든 집\n"뜻"');
  assert.throws(() => loadIdioms('hanja,reading,meaning\n家,가,"미완성'));
  assert.throws(() => loadIdioms('hanja,reading,meaning\n家,가'));
});
test('같은 세션은 절대로 반복하지 않고 이전 세션은 미출제 소진 시 허용한다', () => {
  const all = idioms.filter(item => item.reading.includes('가'));
  const session = new Set([all[0].id]);
  const history = new Set(all.slice(0, -1).map(item => item.id));
  assert.deepEqual(candidatesFor(idioms, '가', session, history), [all.at(-1)]);
  const exhausted = new Set(all.map(item => item.id));
  assert.deepEqual(candidatesFor(idioms, '가', session, exhausted), all.slice(1));
  assert.deepEqual(candidatesFor(idioms, '가', exhausted, exhausted), []);
});
test('모든 유효 후보의 독음을 허용하고 띄어쓰기를 정규화한다', () => {
  const candidates = candidatesFor(idioms, '가', new Set(['家家戶戶']), new Set());
  for (const item of candidates) assert.ok(matchingAnswers(candidates, item.reading).includes(item));
  assert.equal(matchingAnswers(candidates, '가 급 인 족')[0].hanja, '家給人足');
  assert.deepEqual(matchingAnswers(candidates, '가가호호'), []);
  assert.deepEqual(matchingAnswers(candidates, ''), []);
});
test('같은 독음의 다른 한자 성어를 손실 없이 반환한다', () => {
  const same = [
    { id: '同音', category: 'idiom', hanja: '同音', reading: '동음', meaning: '같은 소리' },
    { id: '同陰', category: 'idiom', hanja: '同陰', reading: '동음', meaning: '같은 그늘' },
  ];
  assert.deepEqual(matchingAnswers(same, '동음'), same);
});
test('정리한 표기 변이 세 그룹은 각각 한 항목만 출제한다', () => {
  for (const [reading, hanja] of [['권토중래', '捲土重來'], ['귤화위지', '橘化為枳'], ['맥수지탄', '麥秀之嘆']]) {
    const items = idioms.filter(item => item.reading === reading);
    assert.equal(items.length, 1);
    assert.equal(items[0].hanja, hanja);
    for (const ch of reading) {
      assert.ok(!candidatesFor(idioms, ch, new Set([hanja]), new Set()).some(item => item.reading === reading));
    }
  }
});
test('Hangul matching ignores Hanja and preserves session/history rules', () => {
  const all = idioms.filter(item => item.reading.includes('상'));
  assert.deepEqual(candidatesFor(idioms, '상', new Set(), new Set()), all);
  const session = new Set([all[0].id]);
  const history = new Set(all.slice(0, -1).map(item => item.id));
  assert.deepEqual(candidatesFor(idioms, '상', session, history), [all.at(-1)]);
  assert.deepEqual(candidatesFor(idioms, '상', session, new Set(all.map(item => item.id))), all.slice(1));
  assert.deepEqual(candidatesFor(idioms, '傷', new Set(), new Set()), []);
  assert.deepEqual(candidatesFor(idioms, '', new Set(), new Set()), []);
  assert.deepEqual(candidatesFor(idioms, '상상', new Set(), new Set()), []);
  assert.deepEqual(candidatesFor(idioms, '\u1109\u1161\u11bc', new Set(), new Set()), all);
  assert.ok(all.some(item => item.hanja.includes('相')));
  assert.ok(all.some(item => item.hanja.includes('上')));
});

test('검수로 한자가 바뀐 성어의 기존 학습 이력을 보존한다', () => {
  const validIds = new Set(idioms.map(item => item.id));
  const previous = ['輕躁浮薄', '龍尾鳳湯', '李下不正冠', '耳懸令鼻懸令', '前途遼遠', '弊袍破笠'];
  const expected = ['輕佻浮薄', '龍味鳳湯', '李下不整冠', '耳懸鈴鼻懸鈴', '前途遙遠', '敝袍破笠'];
  assert.deepEqual(migrateIdiomHistory([...previous, ...expected, '家家戶戶', '삭제된성어'], validIds), [...expected, '家家戶戶']);
  assert.deepEqual(migrateIdiomHistory(['卷土重來', '橘化爲枳', '麥秀之歎'], validIds), ['捲土重來', '橘化為枳', '麥秀之嘆']);
  assert.notEqual(normalizeHanjaForSearch('令'), normalizeHanjaForSearch('鈴'));
  assert.notEqual(normalizeHanjaForSearch('尾'), normalizeHanjaForSearch('味'));
});
test('사전 검수에서 확인한 독음과 핵심 뜻을 회귀 검사한다', () => {
  assert.equal(idioms.find(item => item.hanja === '伯樂一顧').reading, '백낙일고');
  assert.ok(!idioms.some(item => item.reading === '백락일고'));
  assert.match(idioms.find(item => item.reading === '일언지하').meaning, /딱 잘라/);
  assert.match(idioms.find(item => item.reading === '홍로점설').meaning, /의혹/);
  assert.match(idioms.find(item => item.reading === '망양보뢰').meaning, /본래/);
});
test('최대 20번 연결하는 동안 같은 성어를 다시 사용하지 않는다', () => {
  let current = idioms.find(item => item.hanja === '家家戶戶');
  const used = new Set([current.id]);
  let count = 0;
  while (count < SESSION_LIMIT) {
    const next = [...current.reading].flatMap(ch => candidatesFor(idioms, ch, used, new Set()))[0];
    if (!next) break;
    assert.ok(!used.has(next.id));
    used.add(next.id); current = next; count++;
  }
  assert.equal(count, SESSION_LIMIT);
  assert.equal(used.size, SESSION_LIMIT + 1);
  assert.equal(readingHint('가급인족', 2), '가급○○');
});
