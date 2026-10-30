# 음훈 변환 구조 검토

- 목적: 기존 원본에서 변환한 음·훈 쌍의 구조와 불일치 후보 분류. 사전 사실 검수는 아님.
- 입력: `data/hanja-readings/review.json`의 sourceSha256 및 datasetSha256, `readings.json`, 원본 `data/hanja-research/pilot/source-analysis/libhangul-hanja.txt`.
- 범위: 竹의 사용자 승인 표현, 독음이 생략된 6개 항목, 미파싱 구절. 스크립트로 형태 검사한 전체 자료의 중복 검토는 제외.
- 기준: 제공된 원본만 사용. 한자 기원·뜻·음은 기억으로 추가·수정하지 말 것. 원본 쓰기 금지.
- 출력: `data/hanja-readings/qwen-review.txt`. 글자·원본·제안·유지/수정/불확실·이유·근거 위치·확인 범위·미확인 사항. 출처 접근은 하지 않았다고 표시.
- Codex 검토: 변환 로직·해시·누락·중복·불일치와 실제 UI 표본 확인. 유지 항목 전체 의미 감수로 확대 해석하지 않음.
