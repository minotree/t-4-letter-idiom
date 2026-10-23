import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { loadIdioms, normalizeHanjaForSearch } from '../packages/shared/src/index.ts';
import { createHash } from 'node:crypto';

const root = new URL('../', import.meta.url);
const csv = await readFile(new URL('sajaseongeo_image_working.csv', root), 'utf8');
const idioms = loadIdioms(csv);
const reviewedCsv = await readFile(new URL('data/cheonjamun/reviewed/cheonjamun.csv', root), 'utf8');
const review = JSON.parse(await readFile(new URL('data/cheonjamun/reviewed/review.json', root), 'utf8'));
if (createHash('sha256').update(reviewedCsv).digest('hex') !== review.reviewed_csv_sha256) {
  throw new Error('천자문 검토본 해시가 검토 기록과 다릅니다.');
}
const cheonjamun = loadIdioms(reviewedCsv);
if (cheonjamun.some(item => item.category !== 'cheonjamun')) throw new Error('천자문 종류가 올바르지 않습니다.');
const existing = new Map(idioms.map(item => [normalizeHanjaForSearch(item.hanja), item]));
const overlaps = [];
for (const item of cheonjamun) {
  const key = normalizeHanjaForSearch(item.hanja);
  const prior = existing.get(key);
  if (prior) {
    if (prior.reading !== item.reading) throw new Error(`중복 자료 독음 충돌: ${item.hanja}`);
    overlaps.push({ hanja: item.hanja, retainedId: prior.id, retainedCategory: prior.category, otherCategory: item.category });
  } else {
    idioms.push(item);
    existing.set(key, item);
  }
}
if (!idioms.length) throw new Error('학습 데이터가 비어 있습니다.');
await mkdir(new URL('apps/web/src/data/', root), { recursive: true });
await writeFile(new URL('apps/web/src/data/idioms.json', root), JSON.stringify(idioms));
console.log(`천자문 ${cheonjamun.length}개 중 중복 ${overlaps.length}개: ${overlaps.map(item => item.hanja).join(', ')}`);
console.log(`학습 데이터 ${idioms.length}개 준비 완료 (ID·자료 종류·한자·독음·뜻)`);
