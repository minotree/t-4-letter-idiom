"""Derive source-backed hun/eum pairs without changing learning text."""
from pathlib import Path
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
source = root / 'data/hanja-research/pilot/source-analysis'
manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8-sig'))
raw = (source / 'libhangul-hanja.txt').read_bytes()
assert hashlib.sha256(raw).hexdigest().upper() == manifest['libhangulSha256']
comparison = json.loads((source / 'candidate-comparison.json').read_text(encoding='utf-8'))
dataset = (root / 'apps/web/src/data/idioms.json').read_bytes()
assert hashlib.sha256(dataset).hexdigest() == comparison['summary']['datasetSha256']
rows = {}
issues = []
for line in raw.decode('utf-8').splitlines():
    if line.startswith('#') or not line.strip():
        continue
    parts = line.split(':', 2)
    if len(parts) != 3 or len(parts[1]) != 1:
        continue
    reading, char, description = parts
    for phrase in description.split(','):
        match = re.fullmatch(r'(.+?)\s+([가-힣])', phrase.strip())
        if not match and re.fullmatch(r'[가-힣]+', phrase.strip()) and re.fullmatch(r'[가-힣]', reading):
            phrase = phrase.strip() + ' ' + reading
            match = re.fullmatch(r'(.+?)\s+([가-힣])', phrase)
        if not match:
            if phrase.strip():
                issues.append({'character': char, 'original': phrase, 'reason': 'unparsed'})
            continue
        hun, eum = match.groups()
        # Only the user-approved presentation expansion; preserve original in audit.
        if char == '竹' and hun == '대':
            hun = '대나무'
        pair = {'hun': hun, 'eum': eum}
        if pair not in rows.setdefault(char, []):
            rows[char].append(pair)
characters = [item['character'] for item in comparison['characters']]
output = {char: rows.get(char, []) for char in characters}
out = root / 'data/hanja-readings'
out.mkdir(exist_ok=True)
supplements = json.loads((out / 'supplements.json').read_text(encoding='utf-8'))
assert supplements['inputSourceSha256'] == hashlib.sha256(raw).hexdigest()
original_pending = {c for c, v in output.items() if not v}
assert {entry['character'] for entry in supplements['entries']} == original_pending
assert len(supplements['entries']) == len(original_pending)
for entry in supplements['entries']:
    char = entry['character']
    assert entry['sources']
    pairs = entry.get('readings') if entry['kind'] == 'fact' else rows.get(entry['target'])
    assert pairs and all(p['hun'].strip() and re.fullmatch('[가-힣]', p['eum']) for p in pairs)
    output[char] = [dict(p) for p in pairs]
(out / 'readings.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
audit = {'datasetSha256': hashlib.sha256(dataset).hexdigest(), 'sourceSha256': hashlib.sha256(raw).hexdigest(),
         'sourceCommit': manifest['libhangulCommit'], 'total': len(output),
         'available': sum(bool(v) for v in output.values()), 'pending': [c for c,v in output.items() if not v],
         'policy': 'Original learning codepoints retained. Only the 44 reviewed supplements may supply missing readings; no runtime normalization. Not a full semantic dictionary audit.',
         'supplementsSha256': hashlib.sha256((out / 'supplements.json').read_bytes()).hexdigest(),
         'supplemented': sorted(original_pending),
         'overrides': [{'character': '竹', 'original': '대', 'display': '대나무', 'basis': 'user request 2026-10-30'}],
         'unparsed': [i for i in issues if i['character'] in output]}
(out / 'review.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
license_text = '\n'.join(line[2:] if line.startswith('# ') else line[1:] for line in raw.decode('utf-8').splitlines() if line.startswith('#'))
(out / 'libhangul-license.txt').write_text(license_text + '\n', encoding='utf-8')
notice = license_text + '\n\nSupplemental hun/eum sources (reviewed 2026-10-30)\n'
notice += '38 explicit Unicode canonical aliases; 2 reviewed semantic variants (爲/為 and 默/黙). Original characters unchanged.\n'
notice += 'Four additional lexical facts checked against traditional culture teaching tables; no explanatory prose or examples reproduced. These supplements are not relicensed as libhangul source material.\n'
for entry in supplements['entries']:
    if entry['kind'] != 'canonical-alias':
        notice += entry['character'] + ': ' + '; '.join(entry['sources']) + '\n'
(out / 'source-notice.txt').write_text(notice, encoding='utf-8')
print(json.dumps({k: audit[k] for k in ['total', 'available', 'pending']}, ensure_ascii=True))
