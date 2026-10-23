"""Record the 2026-10-23 agent comparison; never infer approval from fetch success."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/content-audit'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    source = ROOT / 'sajaseongeo_image_working.csv'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    reference = read('dictionary-reference.json')
    applied = read('applied-meaning-review.json')
    assert digest == reference['source_sha256'] == applied['source_after_sha256']
    supplements = read('supplementary-sources.json')
    changes = {item['after']['hanja']: item for item in applied['changes']}
    records = []
    for row in reference['rows']:
        direct = bool(row['entries'])
        records.append({
            'hanja': row['hanja'], 'reading': row['reading'],
            'status': '대표 뜻 1차 대조·사전 표제어 있음' if direct else '보조 자료 대조·직접 사전 근거 추가 확인 필요',
            'hanja_exact_match': row['hanja_match'],
            'applied_correction': row['hanja'] in changes,
            'sources': list(dict.fromkeys(entry['url'] for entry in row['entries'])) if direct else supplements.get(row['reading'], []),
            'expert_approved': False,
        })
    assert len(records) == 666
    assert sum(bool(row['entries']) for row in reference['rows']) == 628
    write('semantic-review.json', {
        'date': '2026-10-23', 'reviewer': 'Codex (agent first-pass comparison)',
        'source_sha256': digest, 'compared_rows': 666, 'dictionary_headword_rows': 628,
        'supplementary_only_rows': 38, 'all_senses_expert_verified': False,
        'limitations': [
            '代表 뜻과 한자·독음을 대조한 1차 검수이며 모든 역사적 용례·다의어·교육 표현의 전문가 승인은 아니다.',
            '직접 표제어가 없는 38개는 보조 자료의 품질이 서로 다르며 공식 사전 등록 여부나 정답성을 확정하지 않는다.',
            '한자 불일치 34개는 표기 변이 등을 개별 검토했으며 무조건 같은 말로 병합하지 않는다.',
            '근근자자·금슬지락·전도양양·허무맹랑·황당무계의 연결 표제어는 dictionary-extra.json을 함께 참조한다.',
            '동음이의어의 다른 한자 뜻을 근거로 사용하지 않는다. 초록은 抄錄, 전도는 顚倒, 감천은 感天. 회자의 방언 검색 결과는 膾炙의 근거가 아니다.',
        ], 'rows': records,
    })
    notes = read('review-notes.json')
    lookup = {row['reading']: row for row in reference['rows']}
    notes['notes']['춘치자명'] = {
        'status': '기존 뜻 유지·이전 확대 제안 철회',
        'note': '직접 사전 정의가 스스로 허물을 드러냄이라는 기존 뜻과 부합한다. 이전 고전 용례 기반의 포괄적 확대 제안은 적용하지 않는다.',
        'sources': [entry['url'] for entry in lookup['춘치자명']['entries']],
    }
    for change in applied['changes']:
        notes['notes'][change['after']['reading']] = {
            'status': '근거 대조 후 교정 적용', 'note': change['reason'],
            'sources': [entry['url'] for entry in change['references']],
        }
    notes['source_sha256'] = digest
    write('review-notes.json', notes)
    backup = OUT / 'history/2026-10-23-before-meaning-review/sajaseongeo_image_working.csv'
    with backup.open(encoding='utf-8-sig', newline='') as stream:
        before = list(csv.DictReader(stream))
    with source.open(encoding='utf-8-sig', newline='') as stream:
        after = list(csv.DictReader(stream))
    differences = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after) == 666 and len(differences) == 32
    field_counts = {}
    for a, b in differences:
        for key in a:
            if a[key] != b[key]:
                assert key in {'hanja', 'reading', 'meaning'}, key
                field_counts[key] = field_counts.get(key, 0) + 1
    assert field_counts == {'meaning': 26, 'hanja': 6, 'reading': 1}, field_counts
    old_lines = backup.read_bytes().splitlines(keepends=True)
    new_lines = source.read_bytes().splitlines(keepends=True)
    assert len(old_lines) == len(new_lines) == 667
    assert sum(a != b for a, b in zip(old_lines, new_lines)) == 32
    print(json.dumps({'source_sha256': digest, 'rows': len(after), 'changed_rows': len(differences), 'field_counts': field_counts, 'other_fields_unchanged': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
