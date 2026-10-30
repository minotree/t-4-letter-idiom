# sources.md — 48자 검토 (2026-10-30)

직접 열람은 웹 `open`으로 페이지 본문을 확인한 경우에만 사용. 검색 요약 및 첨부 후보는 직접 열람 근거가 아님. 출처 ID는 review.json의 검증된 제안값에만 부착한다.

| ID | 원본 제공자 / 원문 | 개별 URL | 열람 | 확인한 내용 | 이용 조건 | 제한 |
|---|---|---|---|---|---|---|
| S1 | 국립국어원 한국어기초사전, 낭보(朗報) | https://krdict.korean.go.kr/eng/dicSearch/SearchView?ParaWordNo=41252 | 직접 열람, 2026-10-30 | 朗: 밝을 랑·밝을 낭, 부수 月, 총획 11 | 국어사전 저작권 정책 https://kdict.korean.go.kr/info/copyright ; CC BY-SA 2.0 KR https://creativecommons.org/licenses/by-sa/2.0/kr/legalcode.ko | 10획 후보와 불일치, 부수 이름 부재; 11획은 분쟁 중 수치여서 JSON 확정값으로 채우지 않음 |
| S2 | 국립국어원 한국어기초사전, 요일(曜日) | https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=67865 | 직접 열람, 2026-10-30 | 曜: 빛날 요, 부수 日, 총획 18 | 같은 국어사전 저작권 정책; CC BY-SA 2.0 KR | 부수 이름 자체는 페이지 미표시; 원어 한자 표기 내용과 앱의 사용 범위는 라이선스 준수 필요 |

## 검토용 문서 — review.json sourceIds로 연결하지 않음

- **R1, Unicode Unihan 17.0.0 안내**: https://www.unicode.org/versions/Unicode17.0.0/ — 직접 열람, 2026-10-30. 버전, Unihan 데이터 공개 위치 확인. 개별 48자의 원문 속성행은 직접 재열람하지 않았으므로 값 확정 근거로 사용하지 않음. 데이터: https://www.unicode.org/Public/17.0.0/ucd/Unihan.zip .
- **R2, Unicode Unihan 속성 명세**: https://www.unicode.org/reports/tr38/tr38-38.html — 직접 열람, 2026-10-30. Unicode 17 대응 문서는 proposed 문서이므로 최종 규범 및 한국 교육용 총획의 직접 검증으로 사용하지 않음.
- **R3, Unicode 데이터 라이선스**: https://github.com/unicode-org/unihan-database/blob/main/LICENSE — 직접 열람, 2026-10-30. Unicode License v3: 저작권 및 허락 고지를 사본 또는 관련 문서에 포함하는 조건으로 복제·변경·배포·판매 등을 허용. 이 저장소의 현재 라이선스와 사용하려는 Unicode 17.0.0 배포 파일 라이선스의 일치 여부는 실제 배포 패키지에서 재확인할 것.
- **R4, 국어사전 저작권 정책**: https://kdict.korean.go.kr/info/copyright — 검색 요약 확인, 원문 직접 열람 미실행. 표기상 기본 텍스트 CC BY-SA 2.0 KR, 별도 표기 자료 및 멀티미디어 예외. 이 주소가 한국어기초사전의 해당 항목에 그대로 적용되는지 최종 확인 필요.
- **R5, CC BY-SA 2.0 KR 개요**: https://creativecommons.org/licenses/by-sa/2.0/kr/ — 검색 요약 확인. 복제·수정·상업적 배포 허용, 저작자 표시·동일조건변경허락, 추가 제한 금지. 전문 https://creativecommons.org/licenses/by-sa/2.0/kr/legalcode.ko 는 이번 턴 직접 열람 미실행.
- **R6, 비교용 爲 원문**: https://krdict.korean.go.kr/eng/dicSearch/SearchView?ParaWordNo=69661 — 검색 요약만 확인. 대상 글자는 為(U+70BA)이므로 **다른 글자 爲(U+7232)를 증거로 쓰지 않음**.
- **R7, 비교용 車 원문**: https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=70799 — 검색 요약만 확인. 대상 車(U+F902)와 다르므로 직접 원문 검증 불인정.

## 권리 적용 주의

텍스트 검색 무료 공개는 재사용 허락과 다름. 국어사전의 표기상 CC BY-SA 조건을 충족하는지, 원 데이터와 가공 데이터의 분리·공개 범위, 서비스별 약관이 별도로 적용되는지는 검토해야 한다. Unicode 데이터의 permissive 라이선스는 한국 한자 교육 내용의 정확성 인증이 아니다. 앱 코드 전체의 라이선스 전염 여부는 결론 내리지 않음.
