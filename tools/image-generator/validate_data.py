"""Read idiom CSVs and maintain metadata only; never generate images."""

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from collections import defaultdict


ROOT = Path(__file__).resolve().parents[2]
FIELDS = ['id', 'hanja', 'reading', 'filename', 'status', 'review_status', 'error_message']


def filename_for(identifier, reading):
    # Keep Korean text while replacing Windows-invalid characters and whitespace.
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]', '_', reading.strip()).rstrip('. ')
    # Bound the component length, including the numeric prefix and extension.
    return f'{identifier:04d}_{safe[:100] or "unnamed"}.webp'


def source_table(raw):
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True))
    header = None
    if rows and rows[0][:2] == ['hanja', 'reading']:
        header = rows.pop(0)
        if len(set(header)) != len(header) or header.count('image_filename') > 1:
            raise ValueError('Duplicate source column names')
    width = len(header) if header else 2
    if any(len(row) != width for row in rows):
        raise ValueError('Source columns differ from expected schema')
    return header, rows


def load_source(source):
    raw = Path(source).read_bytes()
    records = []
    _, table = source_table(raw)
    for identifier, row in enumerate(table, 1):
        hanja, reading = row[:2]
        records.append(dict(zip(FIELDS, [str(identifier), hanja, reading,
                                       filename_for(identifier, reading),
                                       'pending', 'pending', ''])))
    return records, hashlib.sha256(raw).hexdigest()


def validate(records, source_hash, expected_count):
    duplicates = {}
    for field in ('hanja', 'reading'):
        groups = defaultdict(list)
        for row in records:
            groups[row[field].strip()].append(int(row['id']))
        found = [{'value': value, 'ids': ids} for value, ids in groups.items() if len(ids) > 1]
        duplicates[field] = {
            'group_count': len(found),
            'record_count': sum(len(group['ids']) for group in found),
            'extra_record_count': sum(len(group['ids']) - 1 for group in found),
            'groups': found,
        }
    whitespace, empty, non_four = [], [], []
    for row in records:
        for field in ('hanja', 'reading'):
            value = row[field]
            if any(char.isspace() for char in value):
                whitespace.append({'id': int(row['id']), 'field': field, 'value': value})
            if not value.strip():
                empty.append({'id': int(row['id']), 'field': field})
        length = len(row['hanja'])
        if length != 4:
            non_four.append({'id': int(row['id']), 'hanja': row['hanja'],
                             'reading': row['reading'], 'length': length})
    return {
        'source_sha256': source_hash,
        'total_count': len(records),
        'expected_count': expected_count,
        'count_matches': len(records) == expected_count,
        'duplicates': duplicates,
        'whitespace_count': len(whitespace),
        'whitespace': whitespace,
        'empty_value_count': len(empty),
        'empty_values': empty,
        'non_four_character_count': len(non_four),
        'non_four_character_items': non_four,
        'notes': 'Source values and order are preserved. Duplicate comparison trims edge whitespace. Length counts Unicode code points, including whitespace. Non-four-character and duplicate items are retained.',
    }


def preserve_manifest(records, manifest):
    if not manifest.exists():
        return records, False
    with manifest.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != FIELDS:
            raise ValueError('Existing manifest columns do not match; no files changed')
        existing = list(reader)
    if len(existing) != len(records):
        raise ValueError('Existing manifest count differs; no files changed')
    by_id = {}
    for row in existing:
        if None in row or any(value is None for value in row.values()):
            raise ValueError('Malformed existing manifest; no files changed')
        if row['id'] in by_id:
            raise ValueError('Duplicate existing manifest id; no files changed')
        by_id[row['id']] = row
    for row in records:
        old = by_id.get(row['id'])
        if old is None or any(old[key] != row[key] for key in FIELDS[:4]):
            raise ValueError(f'Existing manifest identity differs at id {row["id"]}; no files changed')
        for key in FIELDS[4:]:
            row[key] = old[key]
    return records, True


def atomic_write(path, content, encoding):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding=encoding, newline='',
                                         dir=path.parent, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run(source, manifest, report_path, expected_count=695):
    source, manifest, report_path = map(Path, (source, manifest, report_path))
    if len({path.resolve() for path in (source, manifest, report_path)}) != 3:
        raise ValueError('Source, manifest, and report must use distinct paths')
    records, source_hash = load_source(source)
    report = validate(records, source_hash, expected_count)
    records, preserved = preserve_manifest(records, manifest)
    report['existing_manifest_preserved'] = preserved
    # An existing manifest is never rewritten, even when all values match.
    if not preserved:
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
        atomic_write(manifest, buffer.getvalue(), 'utf-8-sig')
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'data/sajaseongeo_final_quiz_v3.csv')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/image_manifest.csv')
    parser.add_argument('--report', type=Path, default=ROOT / 'data/validation_report.json')
    parser.add_argument('--expected-count', type=int, default=695)
    args = parser.parse_args()
    try:
        report = run(args.source, args.manifest, args.report, args.expected_count)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.exit(1, f'Error: {error}\n')
    print(json.dumps({key: report[key] for key in (
        'total_count', 'count_matches', 'whitespace_count', 'empty_value_count',
        'non_four_character_count', 'existing_manifest_preserved')}, ensure_ascii=True))
    return 0 if report['count_matches'] and not report['empty_value_count'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
