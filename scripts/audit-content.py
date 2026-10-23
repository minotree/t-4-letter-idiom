"""Read-only content screening. Unihan is a character reading check, not an idiom dictionary."""
import argparse
import csv
import hashlib
import json
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def initial_variants(reading):
    # Screening allowance for Korean initial-sound rules (not an automatic correction).
    result = {reading}
    if len(reading) != 1 or not ('가' <= reading <= '힣'):
        return result
    number = ord(reading) - 0xAC00
    onset, vowel, final = number // 588, (number % 588) // 28, number % 28
    if onset == 5:  # ㄹ -> ㄴ / ㅇ
        new_onset = 11 if vowel in {2, 6, 7, 12, 17, 20} else 2
        result.add(chr(0xAC00 + new_onset * 588 + vowel * 28 + final))
    if onset == 2 and vowel in {6, 12, 17, 20}:  # ㄴ -> ㅇ
        result.add(chr(0xAC00 + 11 * 588 + vowel * 28 + final))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unihan', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/content-audit/structural.json')
    args = parser.parse_args()
    source = ROOT / 'sajaseongeo_image_working.csv'
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    with source.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    readings = {}
    variants = {}
    with zipfile.ZipFile(args.unihan) as archive:
        for line in archive.read('Unihan_Readings.txt').decode('utf-8').splitlines():
            parts = line.split('\t')
            if len(parts) == 3 and parts[1] == 'kHangul':
                readings[chr(int(parts[0][2:], 16))] = {item.split(':')[0] for item in parts[2].split()}
        for line in archive.read('Unihan_Variants.txt').decode('utf-8').splitlines():
            parts = line.split('\t')
            if len(parts) == 3 and parts[1] in {'kSemanticVariant', 'kTraditionalVariant', 'kSimplifiedVariant'}:
                variants.setdefault(chr(int(parts[0][2:], 16)), {})[parts[1]] = parts[2]
    findings = []
    by_hanja, by_normalized, by_reading = defaultdict(list), defaultdict(list), defaultdict(list)
    compatibility_rows = []
    lengths = Counter()
    character_checks = 0
    for index, row in enumerate(rows, 2):
        hanja, reading, meaning = (row.get(key, '') for key in ('hanja', 'reading', 'meaning'))
        item = {'csv_line': index, 'hanja': hanja, 'reading': reading, 'meaning': meaning}
        by_hanja[hanja].append(item)
        by_normalized[unicodedata.normalize('NFKC', hanja)].append(item)
        by_reading[reading].append(item)
        lengths[len(hanja)] += 1
        reasons = []
        if not all((hanja.strip(), reading.strip(), meaning.strip())):
            reasons.append({'type': 'missing_field'})
        if not re.fullmatch('[가-힣]+', reading):
            reasons.append({'type': 'non_hangul_reading'})
        if any('CJK' not in unicodedata.name(ch, '') for ch in hanja):
            reasons.append({'type': 'non_hanja_character'})
        if any(row[key] != row[key].strip() for key in ('hanja', 'reading', 'meaning')):
            reasons.append({'type': 'outer_whitespace'})
        if len(hanja) != len(reading):
            reasons.append({'type': 'length_mismatch'})
        else:
            for offset, (character, syllable) in enumerate(zip(hanja, reading)):
                normalized = unicodedata.normalize('NFKC', character)
                accepted = set(readings.get(character, set())) | set(readings.get(normalized, set()))
                if not accepted:
                    reasons.append({'type': 'unihan_missing', 'position': offset + 1, 'character': character})
                    continue
                character_checks += 1
                allowed = set().union(*(initial_variants(value) for value in accepted))
                if syllable not in allowed:
                    reasons.append({'type': 'unihan_reading_candidate', 'position': offset + 1,
                                    'character': character, 'actual': syllable, 'reference': sorted(accepted)})
        if unicodedata.normalize('NFKC', hanja) != hanja:
            compatibility_rows.append(item)
        if reasons:
            findings.append({**item, 'reasons': reasons})
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError('Source changed during audit')
    report = {
        'source': source.name, 'source_sha256': before, 'source_unchanged': before == after,
        'rows': len(rows), 'unique_hanja': len(by_hanja), 'character_reading_checks': character_checks,
        'length_distribution': dict(sorted(lengths.items())), 'unihan_version': '17.0.0',
        'unihan_sha256': hashlib.sha256(args.unihan.read_bytes()).hexdigest(),
        'limitations': ['Character readings only; idiom meaning correctness is not automatically validated.',
                       'Initial sound variants are permissive screening rules, not contextual pronunciation validation.',
                       'No automatic edits or approval status changes.'],
        'findings': findings,
        'exact_duplicate_groups': [group for group in by_hanja.values() if len(group) > 1],
        'normalized_duplicate_groups': [group for group in by_normalized.values() if len(group) > 1],
        'same_reading_groups': [group for group in by_reading.values() if len(group) > 1],
        'compatibility_character_row_count': len(compatibility_rows),
        'compatibility_character_rows': compatibility_rows,
        'same_reading_variant_evidence': {
            ch: variants.get(ch, {}) for ch in '卷捲為爲嘆歎'
        },
        'matching_normalization_examples': [
            {'character': ch, 'normalized': unicodedata.normalize('NFKC', ch),
             'literal_candidate_count': sum(ch in row['hanja'] for row in rows),
             'normalized_candidate_count': sum(unicodedata.normalize('NFKC', ch) in unicodedata.normalize('NFKC', row['hanja']) for row in rows)}
            for ch in ['不', '不', '金', '金', '利', '利']
        ],
        'semantic_dictionary_verified': False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    notes_path = ROOT / 'data/content-audit/review-notes.json'
    notes = json.loads(notes_path.read_text(encoding='utf-8'))['notes'] if notes_path.exists() else {}
    flagged = {item['csv_line']: item for item in findings}
    semantic_path = args.output.parent / 'semantic-review.json'
    semantic = json.loads(semantic_path.read_text(encoding='utf-8')) if semantic_path.exists() else {}
    if semantic and semantic.get('source_sha256') != before:
        raise RuntimeError('Semantic review source hash does not match current CSV')
    semantic_rows = {item['hanja']: item for item in semantic.get('rows', [])}
    duplicate_readings = {group[0]['reading'] for group in report['same_reading_groups']}
    with (args.output.parent / 'review-queue.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = ['csv_line', 'hanja', 'reading', 'meaning', 'structure', 'character_reading_screen',
                  'same_reading_group', 'external_evidence_status', 'review_note', 'suggested_meaning', 'sources', 'dictionary_full_check']
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for index, row in enumerate(rows, 2):
            note = notes.get(row['reading'], {})
            meaning_review = semantic_rows.get(row['hanja'], {})
            writer.writerow({
                'csv_line': index, **{key: row[key] for key in ('hanja', 'reading', 'meaning')},
                'structure': '항목별 결과는 structural.json 참고' if index in flagged else '자동 검사 지적 없음',
                'character_reading_screen': '추가 대조 항목' if index in flagged else '문자 단위 후보음 부합(성어 검증 아님)',
                'same_reading_group': '표기 중복 검토' if row['reading'] in duplicate_readings else '',
                'external_evidence_status': meaning_review.get('status', note.get('status', '외부 사전 대조 대기')),
                'review_note': note.get('note', ''), 'suggested_meaning': note.get('suggested_meaning', ''),
                'sources': ' | '.join(dict.fromkeys(meaning_review.get('sources', []) + note.get('sources', []))),
                'dictionary_full_check': '전체 용례·전문가 검수 미완료',
            })
    print(json.dumps({key: report[key] for key in ('rows', 'unique_hanja', 'character_reading_checks', 'length_distribution', 'compatibility_character_row_count', 'source_unchanged')}, ensure_ascii=False))
    print(json.dumps({'findings': findings, 'same_reading_groups': report['same_reading_groups']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
