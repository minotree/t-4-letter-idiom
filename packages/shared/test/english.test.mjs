import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { englishCandidates, matchesEnglish, englishHint, englishLength, englishLetters } from '../src/index.ts';
const words = JSON.parse(readFileSync(new URL('../../../data/english/words.json', import.meta.url), 'utf8'));
test('영어 이관 데이터 3339개와 안정 ID·필수 값 검증', () => {
  assert.equal(words.length, 3339);
  assert.equal(new Set(words.map(item => item.id)).size, words.length);
  assert.ok(words.every(item => item.category === 'english' && item.word && item.meaning && item.partOfSpeech));
  assert.ok(words.every(item => !('isBookmarked' in item) && !('isQuizUsed' in item)));
});
test('영어 후보는 선택 글자 포함·세션 제외·미출제 우선 및 소진 복귀', () => {
  const all = englishCandidates(words, 'Y', new Set(), new Set());
  const used = new Set([all[0].id]);
  assert.ok(englishCandidates(words, 'Y', used, new Set()).every(item => item.id !== all[0].id));
  assert.deepEqual(englishCandidates(words, 'Y', used, new Set(all.slice(0, -1).map(item => item.id))), [all.at(-1)]);
  assert.deepEqual(englishCandidates(words, 'Y', used, new Set(all.map(item => item.id))), all.slice(1));
  assert.deepEqual(englishCandidates(words, '', used, new Set()), []);
});
test('영어 정답은 선택 후보·대소문자·복합어·영미 철자와 선택 글자를 구분', () => {
  const you = words.find(item => item.word === 'YOU');
  assert.equal(matchesEnglish(you, ' you ', 'Y'), true);
  assert.equal(matchesEnglish(you, 'the', 'Y'), false);
  const variant = words.find(item => item.word === 'VIGOR/VIGOUR');
  assert.equal(matchesEnglish(variant, 'vigor', 'V'), true);
  assert.equal(matchesEnglish(variant, 'vigour', 'U'), true);
  assert.equal(matchesEnglish(variant, 'vigor', 'U'), false);
  assert.equal(englishLength(variant), '5 / 6');
  assert.equal(englishHint(variant, 'U', 2), 'VI○○○○');
  assert.deepEqual(englishLetters({ word: 'LIVING ROOM' }), ['L', 'I', 'V', 'I', 'N', 'G', 'R', 'O', 'O', 'M']);
  assert.deepEqual(englishLetters({ word: 'THAT' }), ['T', 'H', 'A', 'T']);
});
