"""Read-only structural intake of the external draft; no semantic approval."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/cheonjamun/draft'
rows = list(csv.DictReader((BASE / 'cheonjamun.csv').open(encoding='utf-8-sig', newline='')))
sources = json.loads((BASE / 'sources.json').read_text(encoding='utf-8-sig'))
notes = json.loads((BASE / 'review-notes.json').read_text(encoding='utf-8-sig'))
source_ids = {source['id'] for source in sources}
errors = []
if len(rows) != 250:
    errors.append('Expected 250 rows')
for sequence, row in enumerate(rows, 1):
    if row['id'] != f'cheonjamun-{sequence:03}' or row['sequence'] != str(sequence):
        errors.append(f'Invalid ID/sequence: {sequence}')
    if row['category'] != 'cheonjamun' or len(row['hanja']) != 4 or not re.fullmatch('[가-힣]{4}', row['reading']):
        errors.append(f'Invalid category/length/reading: {sequence}')
    if not row['meaning'].strip() or row['review_status'] not in {'draft', 'uncertain'}:
        errors.append(f'Missing meaning/invalid status: {sequence}')
    if not set(row['source_ids'].split(';')) <= source_ids:
        errors.append(f'Unknown source ID: {sequence}')
hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in BASE.iterdir() if path.is_file()}
hash_checks = []
for item in notes['metadata'].get('output_files', []):
    path = ROOT / item['path']
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    hash_checks.append({'path': item['path'], 'matches': actual == item['sha256'], 'recorded': item['sha256'], 'actual': actual})
inputs = []
for item in notes['metadata'].get('input_files', []):
    path = ROOT / item['path'].split(' (')[0]
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    inputs.append({'path': str(path.relative_to(ROOT)), 'exists': path.exists(), 'matches': actual == item['sha256']})
characters = Counter(''.join(row['hanja'] for row in rows))
report = {'draft_only': True, 'semantic_approved': False, 'rows': len(rows),
          'characters': sum(characters.values()), 'unique_characters': len(characters),
          'duplicate_characters': {key: count for key, count in characters.items() if count > 1},
          'statuses': dict(Counter(row['review_status'] for row in rows)),
          'structural_errors': errors, 'hashes': hashes, 'recorded_output_hash_checks': hash_checks,
          'recorded_input_checks': inputs, 'review_items': len(notes.get('items', [])),
          'evidence_gaps': ['Dictionary reference uses a homepage and generic locator; item-specific evidence is needed.',
                            'No bounded evidence excerpts are provided for local Qwen comparison.',
                            'Handoff claims zero unconfirmed entries but lists pronunciation decisions for follow-up; not final approval.']}
output = ROOT / 'data/cheonjamun/review'
output.mkdir(exist_ok=True)
(output / 'intake.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
if errors:
    raise SystemExit(1)
