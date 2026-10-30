# 44자 보완 검토 (2026-10-30)

- 결과: 1,522 → 1,566자, 누락 44 → 0. 성어 원문·ID·독음은 변경하지 않았다. `supplements.json`에 글자별 원본·제안·판정 이유·출처를 보존하고 생성기가 이 명시 목록만 사용한다. 원본 조사 자료는 읽기 전용으로 유지했다.
- 38개 호환 한자: Python Unicode Database의 canonical decomposition을 글자별 확인하고 대응하는 libhangul 원본 음훈의 존재를 확인했다. NFKC 런타임 치환 기능을 추가한 것이 아니다. 저장한 Unicode 버전·decomposition 및 기존 libhangul 원본 해시로 입력을 식별한다. 정규화 근거: https://www.unicode.org/reports/tr15/ . 38개 모두 분해 대상과 앱 출력 쌍을 테스트한다.
- 為 → 爲: Unicode 17 `Unihan_Variants.txt`의 `U+70BA kSemanticVariant U+7232<kHKGlyph`. 黙 → 默: 같은 파일의 `U+9ED9 kSemanticVariant U+9ED8`. 黙은 대만 교육부 이체자사전 A04773-001도 직접 열어 관계를 확인했다: https://dict.variants.moe.edu.tw/dictView.jsp?ID=53187 . 한국 훈음은 중국어 독음을 번역하지 않고 해시 검증된 기존 libhangul 爲·默 항목에서 가져왔다. semantic variant 전체를 무조건 동의자로 쓰지 않고 이 두 글자만 명시 검토했다.
- 昃: `기울 / 측`. 주해천자문 신습한자 표의 `昃:기울 측/햇살 기울 측` 확인. https://db.cyberseodang.or.kr/front/alphaList/BookMain.do?bnCode=jti_5a0901&titleId=C6
- 虢: `나라 이름 / 괵`. 같은 책 표의 `虢:나라 이름 괵` 확인. https://db.cyberseodang.or.kr/front/sabuList/BookMain.do?bnCode=jti_5a0901&titleId=C77
- 輶: `가벼울 / 유`. 같은 책 표의 `輶:가벼울 유` 확인. https://db.cyberseodang.or.kr/front/sabuList/BookMain.do?bnCode=jti_5a0901&titleId=C104
- 颻: `나부낄 / 요`. 같은 책 표의 `颻:나부낄 요` 확인. https://db.cyberseodang.or.kr/front/sabuList/BookMain.do?bnCode=jti_5a0901&titleId=C101
- 위 네 글자는 최소한의 사전 사실(훈·음 쌍)만 직접 구성했다. 출처의 설명·번역문·예문·이미지·획순은 복제하지 않았다. libhangul 조건을 다른 출처에 덮어 적용하지 않으며 `source-notice.txt`에 원본 조건과 보완 출처를 구분한다. 팝업 고지 문구도 복수 출처에 맞춰 변경했다.
- 웹 확인 한계: C101 URL 직접 열기는 처음 실패했지만 같은 책 C104의 목차 링크를 통해 실제 C101 본문 및 신습한자 표를 열어 확인했다. C69는 가도멸괵 항목이 아니어서 근거로 쓰지 않았다. 검색 요약만 본 것을 직접 본문 검증으로 기록하지 않았다.
- 분담: Qwen2.5 Coder 14B에 6개의 제공 근거 문자열만 비교하도록 맡겼다. `qwen-supplements-review.json`은 입력 해시·범위·원본 출력·파싱 결과를 보존. ID 6개·중복 없음·입력 해시 일치는 확인했으나, 네 훈음에서 근거와 무관한 번역 및 이체자 관계와의 혼동이 나타나 **네 unsupported 판정은 미채택**했다. 두 variant supported 판정은 Codex의 원본 대조와 일치하나 독립 출처로 계산하지 않았다. Codex가 6개 전부 및 38개 대응표를 최종 확인했다.
- 남은 범위: 이번 44자의 누락 보완 완료와 전체 1,566자 의미의 전문가 감수는 구분한다. 기존 복수 훈음의 문맥별 선정은 변경하지 않는다. 실제 토스/PWA 설치 기기 검증은 별도다.
