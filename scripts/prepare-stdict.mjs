// Convert the read-only inspection report into attributed supplementary data.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const report = JSON.parse(await readFile('tmp/stdict-inspection.json', 'utf8'));
const learning = JSON.parse(await readFile('apps/toss/src/data/idioms.json', 'utf8'));
const entries = {};
for (const item of learning) {
  const matches = report.matches[`${item.reading}|${item.hanja}`];
  if (!matches || matches.length !== 1) continue;
  const match = matches[0];
  if (!match.senses.length || !/^\d+$/.test(match.targetCode)) throw Error(`Invalid dictionary entry: ${item.id}`);
  entries[item.id] = { ...match };
}
if (Object.keys(entries).length !== report.matchedCount) throw Error('Match count changed; inspect input again.');
await mkdir('data/stdict', { recursive: true });
const output = JSON.stringify(entries, null, 2) + '\n';
await writeFile('data/stdict/entries.json', output);
await writeFile('data/stdict/source.json', JSON.stringify({
  title: '표준국어대사전', author: '국립국어원', exportDate: '2026-10-12',
  url: 'https://stdict.korean.go.kr/',
  policyUrl: 'https://stdict.korean.go.kr/join/copyrightPolicy.do',
  license: 'CC BY-SA 2.0 KR', licenseUrl: 'https://creativecommons.org/licenses/by-sa/2.0/kr/',
  modifications: '학습 항목과 독음·한자가 정확히 일치하는 항목을 추출하고 필드를 선별하여 JSON으로 변환. 표제어 구분 기호 제거. 용례·멀티미디어 제외. 기존 학습 뜻은 유지.',
  matchedCount: Object.keys(entries).length, learningCount: learning.length,
  entriesSha256: createHash('sha256').update(output).digest('hex'),
  sourceFiles: report.sourceFiles,
}, null, 2) + '\n');
await writeFile('data/stdict/unmatched.json', JSON.stringify(report.unmatched.map(({id,hanja,reading,category}) => ({id,hanja,reading,category})), null, 2) + '\n');
console.log(`Prepared ${Object.keys(entries).length} dictionary entries.`);
