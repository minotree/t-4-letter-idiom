import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { parseCsv } from '../packages/shared/src/index.ts';

const sourceRoot = process.argv[2];
if (!sourceRoot) throw new Error('사용법: node scripts/import-english.mjs <영어 프로젝트 경로>');
const csvPath = resolve(sourceRoot, 'words_completed.csv');
const jsonPath = resolve(sourceRoot, 'packages/core/src/assets/vocab.json');
const [csv, json] = await Promise.all([readFile(csvPath), readFile(jsonPath)]);
const [header, ...rows] = parseCsv(csv.toString('utf8'));
const source = JSON.parse(json.toString('utf8'));
if (!Array.isArray(source) || source.length !== rows.length) throw new Error('CSV와 JSON의 항목 수가 다릅니다.');
const fields = { word: '영단어', meaning: '뜻', partOfSpeech: '품사', synonym: '동의어', example: '예문', exampleMeaning: '예문해석' };
if (Object.values(fields).some(field => !header.includes(field)) || !header.includes('난이도')) throw new Error('원본 CSV 필수 열 누락');
const levels = { 초급: 'beginner', 중급: 'intermediate', 고급: 'advanced', 특급: 'special' };
const ids = new Set();
const words = source.map((item, index) => {
  if (rows[index].length !== header.length) throw new Error('CSV 열 수 불일치');
  for (const [key, field] of Object.entries(fields)) {
    let expected = rows[index][header.indexOf(field)].trim();
    if (key === 'word') expected = expected.toUpperCase();
    if ((item[key] ?? '') !== expected) throw new Error(`CSV/JSON 불일치: ${index + 2}행 ${key}`);
  }
  const level = rows[index][header.indexOf('난이도')].trim();
  if (!Object.hasOwn(levels, level) || item.level !== levels[level]) throw new Error(`난이도 불일치: ${index + 2}행 ${level}`);
  const id = 'english:' + item.word.toLowerCase();
  if (!item.word || !item.meaning || !item.partOfSpeech || ids.has(id)) throw new Error('누락 또는 중복 단어');
  ids.add(id);
  return { id, category: 'english', ...Object.fromEntries([...Object.keys(fields), 'level'].map(key => [key, item[key] ?? ''])) };
});
const out = new URL('../data/english/', import.meta.url);
await mkdir(out, { recursive: true });
await writeFile(new URL('words.json', out), JSON.stringify(words) + '\n');
const hash = value => createHash('sha256').update(value).digest('hex');
await writeFile(new URL('source.json', out), JSON.stringify({ category: 'english', source_project: 't-crossword-app', source_csv: 'words_completed.csv', csv_sha256: hash(csv), source_json: 'packages/core/src/assets/vocab.json', json_sha256: hash(json), rows: words.length, original_project_modified: false, fields_excluded: ['isBookmarked', 'isQuizUsed'], imported_on: new Date().toISOString().slice(0, 10) }, null, 2) + '\n');
console.log(`영어 ${words.length}개 이관: CSV/JSON 모든 학습 필드 대조 통과. 원본 프로젝트 변경 없음.`);
