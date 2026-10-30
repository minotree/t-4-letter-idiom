# GPT 우선 검수 결과 인수 (2026-10-30)

## 결론

제출 결과는 48자 조사 대장으로 보관한다. 曜와 朗의 일부 제안값에는 개별 근거가 있으나, 나머지 46자의 새 훈음·부수·총획은 확인하지 못했다. 朗 총획 충돌도 해결되지 않았다. 전체 데이터 완성 또는 앱 적용 가능으로 판단하지 않는다.

## Codex 확인

- `gpt-priority/`의 `review.json`, `sources.md`, `issues.md`, `summary.md`를 인수했다. 제출 원본은 수정하지 않았다.
- 로컬 Python JSON 검사: 입력 대상과 결과 모두 정확히 48자, 중복 없음·문자 집합 일치·코드포인트 일치. 기존 후보의 libhangulCandidates·unihanProperties·nfkcResearchHint·reviewStatus와 contexts가 입력과 일치하고 sourceIds S1·S2가 문서에 존재한다.
- 결과 metadata의 학습 JSON SHA-256을 실제 `apps/web/src/data/idioms.json`과 직접 대조하여 일치했다. GPT는 입력 파일의 해시 문자열만 복사했고 원본을 재계산하지 않았음을 구분해 기록했다.
- 입력의 `occurrences`, `animcjkFolders`는 결과의 `existingValues`에 포함되지 않았다. 따라서 summary의 기존값 ‘손실 없이 보존’은 모든 입력 필드 기준으로는 성립하지 않는다. 원본 `source-analysis/priority-review.json`을 함께 보존해야 한다.
- 제안값이 있는 항목은 曜·朗 두 글자뿐이며 나머지 46자는 null. 전체 판정은 유지 1건·불확실 47건이다. 曜의 훈음·부수 문자·총획과 朗의 훈음·부수 문자를 각각 아래 사전 페이지의 원어 한자 항목에서 Codex가 직접 대조했다. 부수 이름은 미확인이다.
- [요일(曜日)](https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=67865): 曜 빛날 요, 부수 日, 총획 18. [낭보(朗報)](https://krdict.korean.go.kr/eng/dicSearch/SearchView?ParaWordNo=41252): 朗 밝을 랑/낭, 부수 月, 총획 11. 이 사전 값은 같은 사전에서의 확인이며 별도 독립 출처와의 교차 검증을 뜻하지 않는다.
- [한국어기초사전 저작권 정책](https://krdict.korean.go.kr/kor/kboardPolicy/copyRightTermsInfo)을 Codex가 직접 열람했다. 별도 표시가 없는 사이트 자료에 CC BY-SA 2.0 대한민국 조건을 안내하고 저작자 표시·동일조건 등을 요구한다. 해당 한자 필드의 출처·추출 및 배포 형태에 대한 최종 검토는 남아 있다. 이미지·음성 등은 별도 조건이다.
- 朗은 사전의 11획, Unihan의 10획, AnimCJK SVG의 11개 획 경로가 관찰되지만, 각 자형과 획수 기준을 직접 대조하지 못했다. 충돌 원인·한국 학습용 표시값은 미확정이다.
- GPT가 지적한 為/爲, 樂/樂/樂 및 羲/義는 코드포인트와 문맥을 보존한다. NFKC 탐색 단서를 표시 값으로 자동 치환하지 않는다.

## 다음 검토

46자의 개별 근거 확보, 朗의 필획 기준과 자형 비교, 한국용 획순 누락 범위 및 앱 배포 조건을 해결해야 한다. 기존 후보·성어 자료 전체를 다시 조사하는 대신 미확인·충돌만 분담한다. 앱 코드, 학습 데이터, 기존 조사 원본은 이번 검토에서 변경하지 않았다.
