"""Inventory current learning characters and unreviewed source coverage."""
import collections
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source_dir = root / 'data/hanja-research/pilot/source-analysis'
dataset_path = root / 'apps/web/src/data/idioms.json'
raw_dataset = dataset_path.read_bytes()
entries = json.loads(raw_dataset)
manifest = json.loads((source_dir / 'manifest.json').read_text(encoding='utf-8-sig'))
dictionary_bytes = (source_dir / 'libhangul-hanja.txt').read_bytes()
if hashlib.sha256(dictionary_bytes).hexdigest().upper() != manifest['libhangulSha256']:
    raise ValueError('Dictionary hash differs from manifest')
tree = json.loads((source_dir / 'animcjk-tree.json').read_text(encoding='utf-8-sig'))
if tree.get('truncated') or tree.get('sha') != manifest['animcjkCommit']:
    raise ValueError('Git tree is incomplete or not at the expected commit')
folders = ('svgsKo', 'svgsJa', 'svgsZhHant', 'svgsZhHans')
available = {folder: set() for folder in folders}
for item in tree['tree']:
    parts = item['path'].split('/')
    if len(parts) == 2 and parts[0] in available and parts[1].endswith('.svg') and parts[1][:-4].isdigit():
        available[parts[0]].add(int(parts[1][:-4]))
dictionary = collections.defaultdict(list)
for line in dictionary_bytes.decode('utf-8-sig').splitlines():
    if line.startswith('#'):
        continue
    parts = line.split(':', 2)
    if len(parts) == 3 and len(parts[1]) == 1 and parts[2].strip():
        item = {'reading': parts[0], 'description': parts[2]}
        if item not in dictionary[parts[1]]:
            dictionary[parts[1]].append(item)
def is_han(char):
    cp = ord(char)
    return 0x3400 <= cp <= 0x9fff or 0xf900 <= cp <= 0xfaff or 0x20000 <= cp <= 0x323af
occurrences = collections.Counter(c for e in entries for c in e['hanja'] if is_han(c))
characters = []
for c, count in sorted(occurrences.items(), key=lambda item: ord(item[0])):
    characters.append({'character': c, 'codePoint': f'U+{ord(c):04X}', 'occurrences': count,
                       'dictionaryCandidates': dictionary[c],
                       'animcjkFolders': [folder for folder in folders if ord(c) in available[folder]],
                       'reviewStatus': 'unreviewed'})
summary = {'entryCount': len(entries), 'uniqueCharacters': len(characters), 'occurrences': sum(occurrences.values()),
           'datasetSha256': hashlib.sha256(raw_dataset).hexdigest(), 'manifest': manifest,
           'dictionaryCharactersWithDescription': sum(bool(c['dictionaryCandidates']) for c in characters),
           'animcjkFolderCoverage': {folder: sum(folder in c['animcjkFolders'] for c in characters) for folder in folders},
           'countsAreAvailabilityOnly': True}
(source_dir / 'inventory.json').write_text(json.dumps({'summary': summary, 'characters': characters}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
