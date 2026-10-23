"""Apply the curated 38-entry review without changing IDs or production metadata."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/content-audit'
SOURCE = ROOT / 'sajaseongeo_image_working.csv'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    plan = read('supplementary-review.json')
    raw = SOURCE.read_bytes()
    before_hash = hashlib.sha256(raw).hexdigest()
    log_path = OUT / 'applied-supplementary-review.json'
    if before_hash != plan['base_source_sha256']:
        if log_path.exists() and read(log_path.name)['source_after_sha256'] == before_hash:
            print('Review already applied; current CSV matches recorded output.')
            return
        raise RuntimeError('CSV hash differs from reviewed input; refuse to apply')
    planned = {item['hanja']: item for item in plan['rows']}
    assert len(planned) == len(plan['rows']) == 38
    assert all(len(item['sources']) >= 2 for item in planned.values())
    lines = raw.decode('utf-8-sig').splitlines(keepends=True)
    header = next(csv.reader([lines[0]]))
    output = [raw.splitlines(keepends=True)[0]]
    changed = []
    found = set()
    for line in lines[1:]:
        row = dict(zip(header, next(csv.reader([line]))))
        item = planned.get(row['hanja'])
        if item:
            found.add(row['hanja'])
            assert row['reading'] == item['reading']
            assert row['meaning'] == item['before_meaning']
        if item and item['meaning'] != row['meaning']:
            before = dict(row)
            row['meaning'] = item['meaning']
            buffer = io.StringIO(newline='')
            csv.writer(buffer, lineterminator='\r\n' if line.endswith('\r\n') else '\n').writerow([row[key] for key in header])
            output.append(buffer.getvalue().encode('utf-8'))
            changed.append({'before': before, 'after': row, 'reason': item['note'], 'sources': item['sources']})
        else:
            output.append(line.encode('utf-8'))
    assert found == set(planned) and len(changed) == 4
    result = b''.join(output)
    after_hash = hashlib.sha256(result).hexdigest()
    archive = OUT / 'history/2026-10-23-before-supplementary-review'
    archive.mkdir(exist_ok=False)
    (archive / SOURCE.name).write_bytes(raw)
    for name in ['semantic-review.json', 'review-notes.json', 'review-queue.csv', 'structural.json', 'supplementary-sources.json']:
        (archive / name).write_bytes((OUT / name).read_bytes())
    (archive / 'content-audit.md').write_bytes((ROOT / 'docs/content-audit.md').read_bytes())
    SOURCE.write_bytes(result)
    write('applied-supplementary-review.json', {
        'date': plan['date'], 'source_before_sha256': before_hash,
        'source_after_sha256': after_hash, 'compared_rows': 38,
        'retained_rows': 34, 'changed_rows': 4, 'changes': changed,
    })
    semantic = read('semantic-review.json')
    assert semantic['source_sha256'] == before_hash
    semantic['source_sha256'] = after_hash
    semantic['supplementary_compared_rows'] = 38
    semantic['supplementary_pending_rows'] = 0
    semantic['supplementary_review'] = 'supplementary-review.json'
    semantic['dictionary_reference_source_sha256'] = before_hash
    semantic['limitations'] = [
        '한자·독음·대표 뜻의 에이전트 검수이며 모든 역사적 용례에 대한 전문가 승인은 아니다.',
        '직접 사전 정의 628개와 보충 대조 38개를 구분한다. 사전 직접 정의 미확보는 오류 판정이나 검수 대기와 같은 뜻이 아니다.',
        '보충 대조는 고전 원문·기관/시험 자료·구성 낱말 사전·교육 해설을 사용했다. 동일 풀이의 재게시를 독립 근거로 단정하지 않는다.',
    ]
    notes = read('review-notes.json')
    for row in semantic['rows']:
        item = planned.get(row['hanja'])
        if item:
            row['status'] = '보충 교차 검수 완료·' + item['decision']
            row['applied_correction'] = row['applied_correction'] or item['decision'] == '뜻 보완'
            row['sources'] = [source['url'] for source in item['sources']]
            row['review_note'] = item['note']
            notes['notes'][item['reading']] = {
                'status': row['status'], 'note': item['note'], 'sources': row['sources'],
            }
    notes['source_sha256'] = after_hash
    write('semantic-review.json', semantic)
    write('review-notes.json', notes)
    write('supplementary-sources.json', {item['reading']: [source['url'] for source in item['sources']] for item in plan['rows']})
    # Verify the actual bytes and fields, including untouched image/approval metadata.
    before_rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    after_rows = list(csv.DictReader(io.StringIO(result.decode('utf-8-sig'))))
    assert len(before_rows) == len(after_rows) == 666
    for before, after in zip(before_rows, after_rows):
        assert all(before[key] == after[key] for key in header if key != 'meaning')
    assert len(raw.splitlines(keepends=True)) == len(result.splitlines(keepends=True))
    assert sum(a != b for a, b in zip(raw.splitlines(keepends=True), result.splitlines(keepends=True))) == 4
    report = ['# 보충 38개 한자·독음·뜻 검수 (2026-10-23)', '',
              '38개 전체 대조 완료: 34개 유지, 4개 뜻 보완. 한자·독음 변경 및 항목 삭제 없음.', '',
              '직접 사전 표제어의 유무와 학습 풀이의 적합성 판단을 구분했다. 아래는 에이전트가 대표 뜻을 대조한 결과이며, 전문가 감수나 모든 고전 용례의 확인을 뜻하지 않는다. 출처 본문 또는 검색에 노출된 본문과 앞선 사전 수집 자료를 확인했다. 동일 내용의 재게시를 별개의 독립 증거로 세지 않았고, 구성 낱말·한자/독음 목록은 해당 범위의 근거로만 사용했다.', '',
              '| 성어·독음 | 결정 | 대조 결과 | 근거 |', '| --- | --- | --- | --- |']
    for item in plan['rows']:
        links = ' · '.join(f'[자료 {index}]({source["url"]})' for index, source in enumerate(item['sources'], 1))
        report.append(f'| {item["hanja"]} / {item["reading"]} | {item["decision"]} | {item["note"]} | {links} |')
    report.extend(['', '## 뜻 보완 전후', ''])
    for item in plan['rows']:
        if item['decision'] == '뜻 보완':
            report.extend([f'### {item["reading"]}', '', f'- 전: {item["before_meaning"]}', f'- 후: {item["meaning"]}', ''])
    report.extend(['## 데이터 보존', '',
                   f'- 적용 전 SHA-256: `{before_hash}`.', f'- 적용 후 SHA-256: `{after_hash}`.',
                   '- 적용 전 CSV·검수 자료: `../data/content-audit/history/2026-10-23-before-supplementary-review/`.',
                   '- 666개 행과 ID 유지, 지정한 뜻 4개만 변경. 이미지 파일명·제작 승인 메타데이터·다른 행의 원본 바이트 보존.',
                   '- 직접 사전 조회 원본 `dictionary-reference.json`은 적용 전 CSV 해시를 유지한다. 의미 교정 후 조회했다고 소급 변경하지 않는다.',
                   '- 이전 `scripts/finalize-content-review.py`는 이전 검수 입력용 기록이다. 최신 CSV에는 이번 적용 로그와 `scripts/audit-content.py`를 사용한다.', ''])
    (ROOT / 'docs/content-audit-supplementary.md').write_text('\n'.join(report), encoding='utf-8')
    print(json.dumps({'rows': len(after_rows), 'compared': 38, 'retained': 34, 'meaning_updates': len(changed),
                      'source_after_sha256': after_hash, 'other_fields_and_lines_preserved': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
