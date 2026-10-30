"""Read a user-provided standard dictionary export; never modify source XML."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('--output', type=Path, default=Path('tmp/stdict-inspection.json'))
args = parser.parse_args()
learning = json.loads(Path('apps/toss/src/data/idioms.json').read_text(encoding='utf-8'))
keys = {(item['reading'], item['hanja']) for item in learning}
matches = {}
files = []
count = 0
for path in sorted(args.source.glob('*.xml')):
    files.append({'name': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    root = None
    for event, element in ET.iterparse(path, events=('start', 'end')):
        if root is None:
            root = element
        if event != 'end' or element.tag != 'item':
            continue
        count += 1
        info = element.find('word_info')
        if info is not None:
            word = re.sub(r'[-^\s]', '', info.findtext('word', ''))
            origins = info.findall('original_language_info')
            hanja = ''.join(x.findtext('original_language', '') for x in origins)
            only_hanja = bool(origins) and all(x.findtext('language_type') == '한자' for x in origins)
            if only_hanja and (word, hanja) in keys:
                senses = []
                for pos in info.findall('pos_info'):
                    for sense in pos.findall('.//sense_info'):
                        definition = sense.findtext('definition', '').strip()
                        if not definition:
                            continue
                        senses.append({
                            'code': sense.findtext('sense_code'),
                            'pos': pos.findtext('pos', ''),
                            'definition': definition,
                            'relations': [{'word': x.findtext('word', ''), 'type': x.findtext('type', '')} for x in sense.findall('lexical_info')],
                        })
                entry = {'targetCode': element.findtext('target_code'), 'word': word, 'hanja': hanja,
                         'pronunciations': [x.text for x in info.findall('pronunciation_info/pronunciation') if x.text],
                         'senses': senses, 'file': path.name}
                matches.setdefault(word + '|' + hanja, []).append(entry)
        element.clear()
        root.clear()
result = {'sourceFiles': files, 'itemsScanned': count, 'learningCount': len(learning),
          'matchedCount': sum((x['reading'] + '|' + x['hanja']) in matches for x in learning),
          'matches': matches,
          'unmatched': [x for x in learning if x['reading'] + '|' + x['hanja'] not in matches],
          'policy': 'Exact reading (only word separators removed) + exact original hanja. No homophone or compatibility folding. No examples/media copied. Meanings unchanged.'}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: result[k] for k in ('itemsScanned', 'learningCount', 'matchedCount')}, ensure_ascii=True))
