"""Collect unreviewed Unicode properties for the exact learning characters."""
import collections
import hashlib
import json
import unicodedata
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[1]
outdir = root / 'data/hanja-research/pilot/source-analysis'
archive = root / 'tmp/hanja-unihan-17.zip'
expected_hash = 'f7a48b2b545acfaa77b2d607ae28747404ce02baefee16396c5d2d7a8ef34b5e'
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected_hash:
    raise ValueError('Unexpected Unihan archive hash')
inventory = json.loads((outdir / 'inventory.json').read_text(encoding='utf-8'))
dataset = json.loads((root / 'apps/web/src/data/idioms.json').read_text(encoding='utf-8'))
if hashlib.sha256((root / 'apps/web/src/data/idioms.json').read_bytes()).hexdigest() != inventory['summary']['datasetSha256']:
    raise ValueError('Learning dataset differs from inventory; regenerate inventory first')
fields = {'kRSUnicode', 'kTotalStrokes', 'kAlternateTotalStrokes', 'kHangul', 'kKorean', 'kCompatibilityVariant'}
values = collections.defaultdict(dict)
with ZipFile(archive) as z:
    for filename in ('Unihan_IRGSources.txt', 'Unihan_DictionaryLikeData.txt', 'Unihan_Readings.txt'):
        for line in z.read(filename).decode('utf-8-sig').splitlines():
            if line.startswith('#') or not line.strip():
                continue
            cp, field, value = line.split('\t', 2)
            if field in fields:
                values[cp][field] = value
results = []
for c in inventory['characters']:
    char, cp = c['character'], c['codePoint']
    results.append({'character': char, 'codePoint': cp, 'occurrences': c['occurrences'],
                    'contexts': [{'id': e['id'], 'hanja': e['hanja'], 'reading': e['reading']} for e in dataset if char in e['hanja']],
                    'libhangulCandidates': c['dictionaryCandidates'], 'animcjkFolders': c['animcjkFolders'],
                    'unihanProperties': values[cp],
                    'nfkcResearchHint': unicodedata.normalize('NFKC', char) if unicodedata.normalize('NFKC', char) != char else None,
                    'reviewStatus': 'unreviewed'})
summary = {'version': '17.0.0', 'sourceUrl': 'https://www.unicode.org/Public/17.0.0/ucd/Unihan.zip',
           'archiveSha256': expected_hash, 'inventoryDatasetSha256': inventory['summary']['datasetSha256'],
           'count': len(results), 'withRadical': sum('kRSUnicode' in r['unihanProperties'] for r in results),
           'withTotalStrokes': sum('kTotalStrokes' in r['unihanProperties'] for r in results),
           'withAlternateStrokes': sum('kAlternateTotalStrokes' in r['unihanProperties'] for r in results),
           'noLibhangulDescription': sum(not r['libhangulCandidates'] for r in results),
           'missingWithNfkcHint': sum(not r['libhangulCandidates'] and r['nfkcResearchHint'] is not None for r in results),
           'multiReading': sum(len({v['reading'] for v in r['libhangulCandidates']}) > 1 for r in results)}
(outdir / 'unihan-candidates.json').write_text(json.dumps({'summary': summary, 'characters': results}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
review = [r for r in results if not r['libhangulCandidates'] or r['character'] in '\u7fb2\u6689\u6717\u66dc']
(outdir / 'priority-review.json').write_text(json.dumps({'summary': summary, 'characters': review}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=True, indent=2))
for r in results:
    if r['character'] in '\u7fb2\u6689\u6717\u66dc':
        print(json.dumps({k: r[k] for k in ('codePoint', 'unihanProperties')}, ensure_ascii=True))
