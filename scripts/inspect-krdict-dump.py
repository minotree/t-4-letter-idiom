"""Inspect feature names in the official bulk JSON archive without extracting it."""
import collections
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[1]
archive = root / 'tmp/krdict-full-json-202610.zip'
expected = 'c8f9ffbf7e9be1f1ec86fa29e4160a75eee8044fc081c27788dadf3ceb66d34e'
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise ValueError('Archive SHA-256 does not match the inspected release')
pattern = re.compile(rb'"att"\s*:\s*"([^"\\]+)"')
features = collections.Counter()
with ZipFile(archive) as z:
    files = [item for item in z.infolist() if not item.is_dir()]
    for item in files:
        with z.open(item) as stream:
            for line in stream:
                match = pattern.search(line)
                if match:
                    features[match.group(1).decode('utf-8')] += 1
    result = {'archiveSha256': expected, 'source': 'https://krdict.korean.go.kr/download/downloadPopup',
              'fileDate': '2026-10-19', 'archiveBytes': archive.stat().st_size,
              'uncompressedBytes': sum(item.file_size for item in files), 'fileCount': len(files),
              'method': 'line-by-line scan of att feature names; not a full JSON schema validation',
              'featureCounts': dict(sorted(features.items())), 'appDataApproved': False}
output = root / 'data/hanja-research/pilot/gpt-bulk-sources/krdict-dump-inspection.json'
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=True, indent=2))
