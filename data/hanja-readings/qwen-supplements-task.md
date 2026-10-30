# 44자 보완 근거 비교

- 목적: 원본을 변경하지 않고 보완안과 제공 근거 사이의 불일치만 분류한다.
- 입력: `supplements.json`의 inputSourceSha256, 항목별 코드포인트·대응 글자·훈/음·sources/evidence. 파일 접근 권한이 없는 모델에는 필요한 값만 프롬프트로 전달한다.
- 범위: 38개 canonical-alias는 스크립트로 코드포인트별 canonical decomposition과 원본 훈음 존재를 검사한다. Qwen은 나머지 6개의 제공 근거 문자열과 제안만 비교한다. 웹 출처 재열람·전체 파일 확인을 했다고 표시하지 않는다.
- 판정: 제공 근거가 제안 훈/음을 직접 지원하는지, 이체자 관계만 지원하는지 구분. 음훈이 제공되지 않은 관계 자료로 한국 음훈을 지어내지 않는다. 실제 한자·한글을 수정하지 말고 항목 ID와 supported/unsupported만 JSON으로 반환한다.
- 금지: 기억 기반 사전 보완, 출처 접근 주장, 원본·앱 수정.
- 결과: `qwen-supplements-review.json`. Codex가 ID·누락·중복·근거를 확인해 채택 여부를 `supplement-review.md`에 남긴다.
