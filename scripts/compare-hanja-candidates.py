"""Build source-preserving research comparisons; never approve or normalize entries."""
import collections
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / 'data/hanja-research/pilot/source-analysis'
raw_radicals = (folder / 'CJKRadicals-17.0.0.txt').read_bytes()
if hashlib.sha256(raw_radicals).hexdigest() != '826f83be25cd18fb8a5015a514704504e1982e840ea14d058bf583e1cc620c83':
    raise ValueError('Unexpected radical source hash')
manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8-sig'))
raw_dictionary = (folder / 'libhangul-hanja.txt').read_bytes()
if hashlib.sha256(raw_dictionary).hexdigest().upper() != manifest['libhangulSha256']:
    raise ValueError('Unexpected libhangul source hash')
data = json.loads((folder / 'unihan-candidates.json').read_text(encoding='utf-8'))
dataset_sha = hashlib.sha256((root / 'apps/web/src/data/idioms.json').read_bytes()).hexdigest()
if data['summary']['inventoryDatasetSha256'] != dataset_sha:
    raise ValueError('Learning data changed; regenerate input inventory')
radicals = {}
for line in raw_radicals.decode('utf-8-sig').splitlines():
    line = line.split('#', 1)[0].strip()
    if not line:
        continue
    number, radical_cp, ideograph_cp = (field.strip() for field in line.split(';'))
    radicals[number] = {'symbol': chr(int(radical_cp, 16)) if radical_cp else None,
                        'ideograph': chr(int(ideograph_cp, 16)) if ideograph_cp else None}
dictionary = collections.defaultdict(list)
for line in raw_dictionary.decode('utf-8-sig').splitlines():
    parts = line.split(':', 2)
    if len(parts) == 3 and len(parts[1]) == 1 and parts[2].strip():
        candidate = {'reading': parts[0], 'description': parts[2]}
        if candidate not in dictionary[parts[1]]:
            dictionary[parts[1]].append(candidate)
output = []
for row in data['characters']:
    comparison = []
    for value in row['unihanProperties'].get('kRSUnicode', '').split():
        radical_number, _, remaining = value.partition('.')
        mapped = radicals.get(radical_number)
        comparison.append({'raw': value, 'number': radical_number, 'remainingStrokes': remaining,
                           'unicodeMapping': mapped,
                           'radicalNameCandidates': dictionary.get(mapped['ideograph'], []) if mapped and mapped['ideograph'] else [],
                           'status': 'unreviewed'})
    hint = row['nfkcResearchHint']
    output.append({'character': row['character'], 'codePoint': row['codePoint'], 'contexts': row['contexts'],
                   'libhangulCandidates': row['libhangulCandidates'],
                   'nfkcResearchHint': hint,
                   'hintCandidates': dictionary.get(hint, []) if hint else [],
                   'radicalCandidates': comparison,
                   'unihanTotalStrokes': row['unihanProperties'].get('kTotalStrokes'),
                   'status': 'unreviewed'})
missing = [item for item in output if not item['libhangulCandidates']]
pilot = json.loads((root / 'data/hanja-research/pilot/gpt-followup/hanja-pilot.json').read_text(encoding='utf-8-sig'))
pilot_values = {item['character']: item for item in pilot}
conflicts, equal, no_comparison = [], [], []
for item in output:
    existing = pilot_values.get(item['character'])
    if not existing:
        continue
    source = existing['totalStrokes']
    other = source['value']
    # The independently opened national dictionary explicitly reports 11 for 朗,
    # although the submitted approved value remains null due to disagreement.
    if item['character'] == '\u6717':
        other = 11
        source = {'value': 11, 'sourceIds': ['S1'], 'sourceUrl': 'https://krdict.korean.go.kr/eng/dicSearch/SearchView?ParaWordNo=41252', 'status': 'reported_not_resolved'}
    value = item['unihanTotalStrokes']
    record = {'character': item['character'], 'codePoint': item['codePoint'], 'unihanTotalStrokes': value,
              'pilotSource': source, 'status': 'unreviewed'}
    if other is None or value is None:
        no_comparison.append(record)
    elif int(value) == other:
        equal.append(record)
    else:
        conflicts.append(record)
summary = {'datasetSha256': dataset_sha, 'characterCount': len(output), 'missingReadingCandidates': len(missing),
           'missingWithHint': sum(bool(x['nfkcResearchHint']) for x in missing),
           'missingWithHintCandidate': sum(bool(x['hintCandidates']) for x in missing),
           'radicalCharactersMapped': sum(all(r['unicodeMapping'] for r in x['radicalCandidates']) and bool(x['radicalCandidates']) for x in output),
           'radicalCharactersWithNameCandidates': sum(any(r['radicalNameCandidates'] for r in x['radicalCandidates']) for x in output),
           'pilotComparable': len(equal) + len(conflicts), 'pilotEqual': len(equal), 'pilotConflict': len(conflicts), 'pilotIncomparable': len(no_comparison)}
def write(name, payload):
    (folder / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
write('candidate-comparison.json', {'summary': summary, 'characters': output})
write('reading-missing-comparison.json', {'summary': summary, 'characters': missing})
write('pilot-stroke-comparison.json', {'summary': summary, 'conflicts': conflicts, 'equal': equal, 'incomparable': no_comparison})
print(json.dumps(summary, ensure_ascii=True, indent=2))
