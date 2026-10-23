"""Apply the explicitly curated review, checking the exact input hash and preserving other CSV bytes."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'sajaseongeo_image_working.csv'
plan = json.loads((ROOT / 'data/content-audit/meaning-corrections.json').read_text(encoding='utf-8'))
reference = json.loads((ROOT / 'data/content-audit/dictionary-reference.json').read_text(encoding='utf-8'))
raw = source.read_bytes()
digest = hashlib.sha256(raw).hexdigest()
if digest != plan['base_source_sha256'] or digest != reference['source_sha256']:
    raise RuntimeError('Review input hash mismatch; do not apply to a different CSV version')
records = raw.decode('utf-8-sig').splitlines(keepends=True)
header = next(csv.reader([records[0]]))
changes = {item['reading']: item for item in plan['changes']}
evidence = {item['reading']: item for item in reference['rows']}
output = [raw.splitlines(keepends=True)[0]]
log = []
for line in records[1:]:
    row_values = next(csv.reader([line]))
    row = dict(zip(header, row_values))
    change = changes.get(row['reading'])
    if change:
        before = dict(row)
        refs = evidence[row['reading']]
        if not refs['entries']:
            raise RuntimeError(f"No dictionary evidence for {row['reading']}")
        for key in ('hanja', 'meaning'):
            if key in change:
                row[key] = change[key]
        if 'new_reading' in change:
            row['reading'] = change['new_reading']
        # Keep production metadata intact; review evidence lives in its own audit log.
        buffer = io.StringIO(newline='')
        csv.writer(buffer, lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[key] for key in header])
        output.append(buffer.getvalue().encode('utf-8'))
        log.append({'before': before, 'after': row, 'reason': change['reason'], 'references': refs['entries']})
    else:
        output.append(line.encode('utf-8'))
if len(log) != len(changes):
    raise RuntimeError('Not every curated change matched exactly one source record')
result = b''.join(output)
archive = ROOT / 'data/content-audit/history/2026-10-23-before-meaning-review'
archive.mkdir(parents=True, exist_ok=False)
(archive / source.name).write_bytes(raw)
for path in ['structural.json', 'review-queue.csv', 'review-notes.json', 'dictionary-reference.json']:
    original = ROOT / 'data/content-audit' / path
    (archive / path).write_bytes(original.read_bytes())
source.write_bytes(result)
report = {'date': plan['date'], 'source_before_sha256': digest,
          'source_after_sha256': hashlib.sha256(result).hexdigest(), 'changed_rows': len(log),
          'changes': log}
(ROOT / 'data/content-audit/applied-meaning-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'Applied {len(log)} reviewed records; original snapshot preserved')
