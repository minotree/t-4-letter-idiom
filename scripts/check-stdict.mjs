import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const raw = await readFile('data/stdict/entries.json', 'utf8');
const entries = JSON.parse(raw);
const source = JSON.parse(await readFile('data/stdict/source.json', 'utf8'));
const learning = JSON.parse(await readFile('apps/toss/src/data/idioms.json', 'utf8'));
const unmatched = JSON.parse(await readFile('data/stdict/unmatched.json', 'utf8'));
assert.equal(createHash('sha256').update(raw).digest('hex'), source.entriesSha256);
assert.equal(Object.keys(entries).length, source.matchedCount);
assert.equal(source.matchedCount + unmatched.length, learning.length);
for (const [id, entry] of Object.entries(entries)) {
  const item = learning.find(item => item.id === id);
  assert.ok(item);
  assert.equal(entry.word, item.reading);
  assert.equal(entry.hanja, item.hanja);
  assert.match(entry.targetCode, /^\d+$/);
  assert.ok(entry.senses.length);
  for (const sense of entry.senses) {
    assert.ok(sense.definition.trim());
    assert.equal(typeof sense.definition, 'string'); // Render as React text, including book-title angle brackets.
    assert.ok(!('examples' in sense));
  }
}
assert.equal(source.license, 'CC BY-SA 2.0 KR');
console.log(`PASS: ${source.matchedCount} exact dictionary matches; ${unmatched.length} unlinked; hashes and definitions valid.`);
