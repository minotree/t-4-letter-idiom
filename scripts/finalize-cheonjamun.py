"""Create the reviewed snapshot; immutable research inputs are hash checked."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/cheonjamun'
DRAFT_HASH = 'f9f25006421f28385bf9f4b52fc89dd93709ae47817054f5949095fd649017d6'
EVIDENCE_HASH = 'b144f88cc36b71945e06bbcc46184582da36a06b57bccf1f9f0658c2499b1164'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(BASE / 'draft/cheonjamun.csv') == DRAFT_HASH
assert sha(BASE / 'evidence/evidence.json') == EVIDENCE_HASH
qwen_path = BASE / 'review/qwen-20261023-232412-007265/results.json'
qwen = json.loads(qwen_path.read_text(encoding='utf-8'))
assert qwen['completed'] == qwen['requested'] == 250
assert qwen['input_sha256'] == DRAFT_HASH and qwen['evidence_sha256'] == EVIDENCE_HASH
rows = list(csv.DictReader((BASE / 'draft/cheonjamun.csv').open(encoding='utf-8-sig', newline='')))
results = {r['id']: r for r in qwen['results']}
assert len(results) == 250 and set(results) == {r['id'] for r in rows}
pending = {66, 140, 157, 199, 201, 239}
samples = {1, 3, 16, 50, 80, 125, 150, 175, 210, 250}
changes = {
    225: {'meaning': '나귀와 노새, 송아지와 수소를 가리킵니다.'},
    231: {'reading': '염필륜지', 'meaning': '몽염의 붓과 채륜의 종이 만드는 솜씨를 일컫습니다.'},
}
ledger = []
approved = []
for row in rows:
    n = int(row['sequence'])
    result = results[row['id']]
    reviewed = result['decision'] != 'keep' or n in samples
    action = 'hold' if n in pending else 'correct' if n in changes else 'retain'
    note = ('독음·문맥 또는 판본 이견의 직접 근거 보완 전 출제 보류.' if action == 'hold' else
            '倫은 인명 채륜의 륜. 발명 단정 대신 구절의 인물·솜씨로 풀이.' if n == 231 else
            '特을 특별한 것으로 풀이한 군더더기를 제거하고 가축 명칭만 설명.' if n == 225 else
            '8자 대구 전체를 4자 풀이로 대체하지 않고 기준 전사본의 이체자를 보존. 자동 제안은 채택하지 않음.' if result['decision'] == 'change' else
            '유지 표본: 제공 근거와 구절 범위 대조.' if n in samples else
            'Qwen 유지 판정, Codex 개별 의미 재검토 생략. 기계 검사 범위만 확인.')
    ledger.append({'id': row['id'], 'qwen_decision': result['decision'], 'action': action,
                   'codex_individually_reviewed': reviewed, 'reason': note,
                   'original': {k: row[k] for k in ('hanja', 'reading', 'meaning')},
                   'changes': changes.get(n, {}), 'evidence_item': row['id'],
                   'correction_evidence': ({'url': 'https://ko.wikisource.org/wiki/석봉_천자문',
                                            'locator': '驢騾犢特 훈음 행', 'note': '특별하다는 형용 해석을 제거. 가축 나열.'} if n == 225 else
                                           {'url': 'https://ko.wikisource.org/wiki/석봉_천자문',
                                            'locator': '恬筆倫紙 훈음 행 倫(물 륜)', 'note': '채륜의 인명 독음; 번역:천자문 해당 대구의 인물 대응도 비교.'} if n == 231 else None)})
    if action == 'hold':
        continue
    copy = dict(row)
    copy.update(changes.get(n, {}))
    copy['review_status'] = 'reviewed_for_app'
    copy['review_note'] = note if reviewed else 'Qwen 유지 판정; Codex 전수 의미 검토 아님.'
    approved.append(copy)
out = BASE / 'reviewed'
out.mkdir(exist_ok=True)
with (out / 'cheonjamun.csv').open('w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(approved)
report = {'input_sha256': DRAFT_HASH, 'evidence_sha256': EVIDENCE_HASH,
          'qwen_result_sha256': sha(qwen_path), 'reviewed_csv_sha256': sha(out / 'cheonjamun.csv'),
          'review_scope': '85 flagged rows + 10 keep samples; remaining keeps have structural checks only',
          'counts': {'qwen_keep': 165, 'qwen_change': 79, 'qwen_uncertain': 6,
                     'accepted_qwen_changes': 1, 'codex_additional_meaning_corrections': 2,
                     'eligible_rows': len(approved), 'held_rows': len(pending)},
          'edition_note': '기준은 위키문헌 석봉 천자문 전사본. 1691 어제서문 확인. 해당 전사본을 1583 간행본이라고 확정한 기존 조사 메타데이터는 채택하지 않음.',
          'source_urls': ['https://ko.wikisource.org/wiki/석봉_천자문',
                          'https://ko.wikisource.org/wiki/번역:천자문'],
          'limitations': ['전문가의 전체 의미 감수 아님', '기존 근거의 supported 표시는 Codex 전수 확인을 뜻하지 않음',
                         '현대 번역문을 대량 복사하지 않고 초안 풀이를 유지·수정함'], 'items': ledger}
(out / 'review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'Reviewed {len(approved)}, held {len(pending)}; SHA-256 {report["reviewed_csv_sha256"]}')
