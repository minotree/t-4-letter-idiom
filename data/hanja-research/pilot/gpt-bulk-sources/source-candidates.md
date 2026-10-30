# 한국 한자 훈음·부수·총획 대량 대조 출처 조사

- 기준일: 2026-10-30
- 범위: 데이터 원본 및 정식 API의 구조·권리·접근성. 개별 한자값 생성 및 1,566자 매칭 미실행.
- 구분: **직접 열람**은 원저작자의 문서 웹페이지를 열어 본 것, **원본 미열람**은 안내 페이지만 보고 실제 대량 데이터 파일은 읽지 못한 것. 모든 조회일 2026-10-30.

## 후보 비교

| ID | 제공자·원천·버전 | 직접 URL / 접근·형식 | 훈음 | 부수 문자/부수명 | 한국 교육용 총획 | 호환 문자 및 범위 | 판정 |
|---|---|---|---|---|---|---|---|
| S1 | 국립국어원 한국어기초사전, 온라인 갱신형(고정 배포 버전 미확인) | https://krdict.korean.go.kr/kor/openApi/openApiInfo ; 검색 `https://krdict.korean.go.kr/api/search`, 보기 `https://krdict.korean.go.kr/api/view`; XML, 인증키 필요 | 단어·한자어의 원어 및 뜻풀이 제공, **한 글자별 대표 훈음 일괄 필드 미확인** | 개별 사이트 한자 정보에 표시될 수 있으나 API 대량 응답 필드 미확인 | API 대량 응답 필드 미확인 | 1,566자 전수 포함률 미확인, 호환 글자 원형 유지 검증 미실행 | 보조 검증, 한자 마스터 일괄 수집원으로는 보류 |
| S2 | libhangul, Choe Hwanjin, main 브랜치(고정 commit 미확인) | https://github.com/libhangul/libhangul/blob/main/data/hanja/hanja.txt ; 약 6.15MB 텍스트 파일. 원본 `raw`는 접근 시 크기 제한 오류 | 한자 단위 독음/설명 후보 (사용자 기존 1,522자) | 직접 지원 확인 못함 | 직접 지원 확인 못함 | 호환자 38자 별도 처리 필요, 전체 범위 수치 검증 미실행 | 기존 후보 유지, 원본 파일의 헤더 재검증 필요 |
| S3 | Unicode Consortium, Unihan 17.0.0 | https://www.unicode.org/Public/17.0.0/ucd/Unihan.zip ; ZIP/TSV 분리 텍스트, 정적 전체 배포 | `kHangul` 등 한국어 *독음* 참고, 한국어 *훈* 미제공 | `kRSUnicode`는 부수 **번호**/잔여획, 부수명 자체가 아님. `CJKRadicals.txt`는 부수 기호 매핑 지원 | `kTotalStrokes`는 일반 획수, 한국 교육용 확정값이 아님 | 코드포인트 기준/호환 관계는 별도 필드, 자동 NFKC 금지 | 기술적 대량 대조에 적합, 교육 정답 확정 금지 |
| S4 | 국립국어원 표준국어대사전, 실시간 사전 API | https://stdict.korean.go.kr/openapi/openApiInfo.do ; `https://stdict.korean.go.kr/api/search.do` / `view.do`, XML·JSON | 한자어 원어·뜻풀이, 한 글자 훈음 전체 필드 미확인 | 전용 필드 미확인 | 전용 필드 미확인 | 범위/호환 글자 원형 검색 성공률 미확인 | 한국어 단어 맥락 보조 검증 |
| S5 | 국립국어원 우리말샘, 실시간 사전 API | https://opendict.korean.go.kr/service/openApiInfo ; `https://opendict.korean.go.kr/api/search`, XML·JSON | 한자어 원어·뜻풀이, 한 글자 대표 훈음 일괄 필드 미확인 | 전용 필드 미확인 | 전용 필드 미확인 | 편집·수록 특성과 호환자 처리 미확인 | 한국어 맥락 보조, 개별 데이터 권리 확인 필요 |
| S6 | AnimCJK 원저작 프로젝트, 저장소 master (고정 commit 미확인) | https://github.com/parsimonhi/animCJK ; `svgsKo` 등 지역별 SVG 파일 | 없음 | 텍스트 사전 마스터로 적합하지 않음 | SVG 경로의 획 수가 한국 교육용 총획 확정값은 아님 | README 설명상 한국 폴더 535자(열람 시점 표기); 대상 1,566자 중 실제 커버리지 미측정 | 별도의 **한국식 획순 애니메이션** 후보 |

## 직접 원문과 사실 확인 내역

### S1 한국어기초사전
- **문서 직접 열람**: https://krdict.korean.go.kr/kor/openApi/openApiInfo — 검색·상세 보기 두 API, 인증키, XML 응답 및 검색 파라미터 확인. 검색 1페이지 최대 100건, start 1~1000. **실제 API 호출 미실행**, 전체 데이터 다운로드 방식은 확인하지 못함.
- **인증 발급·한도 문서 직접 열람**: https://krdict.korean.go.kr/eng/openApi/openApiRegister — 이메일 키 발급, 하루 최대 50,000회 요청 안내 확인. 키 발급 미실행. 요금 명시 없음(무료 호출 문구와 별도 운영 비용 보장 혼동 금지).
- **이용 조건 직접 열람**: https://krdict.korean.go.kr/kor/kboardPolicy/copyRightTermsInfo — 별도 표시 없는 텍스트 CC BY-SA 2.0 KR, 상업 이용 허용, 출처표시 및 개작물 동일조건. 멀티미디어는 개별 권리.
- **라이선스 전문**: https://creativecommons.org/licenses/by-sa/2.0/kr/legalcode.ko . 데이터 자체와 앱 코드 전체의 결합 효과는 여기서 단정하지 않음.
- **미확인**: 한 글자별 훈·음·부수명·총획을 API가 동일 필드로 대량 반환하는지, 전체 1,566자 커버리지, 대량 일괄 파일 내려받기, 이용 신청 조건 변경.

### S2 libhangul
- **프로젝트 원문 직접 열람**: https://github.com/libhangul/libhangul ; https://github.com/libhangul/libhangul/blob/main/README — 한자 사전 포함 라이브러리, 배포 releases 안내, 저장소 전체 LGPL-2.1 표기.
- **실제 파일 페이지 직접 열람, 파일 본문 미열람**: https://github.com/libhangul/libhangul/blob/main/data/hanja/hanja.txt — 6.15MB 및 Raw/Download 표시. https://raw.githubusercontent.com/libhangul/libhangul/main/data/hanja/hanja.txt 원본 열람은 콘텐츠 길이 제한으로 실패. 헤더 권리 문구 직접 대조 **미실행**.
- **파일별 BSD 3-Clause 주장(2차 문헌으로만 확인)**: https://github.com/SJY051/HanjaKey/blob/main/THIRD_PARTY_DATA.md . 이는 *libhangul 원저작자 자체의 확인은 아님*. 이 문헌은 데이터 파일 헤더에 BSD 3-Clause가 있다고 설명하므로 추가 확인 대상으로 분리. 코드의 LGPL-2.1을 데이터에 자동 적용하지 않음.
- **라이선스 후보 URL**: https://github.com/libhangul/libhangul/blob/main/COPYING (라이브러리 코드); 데이터 BSD 헤더 및 전문 직접 대조 실패, 상업적 앱 내 데이터 번들 가능성 **조건부 판단 보류**.
- 업데이트/버전: 고정 버전 태그 및 실제 현재 최신 release 미확인. API 호출한도 해당 없음, 파일 배포 방식. 다운로드 수행 미실행.

### S3 Unicode Unihan 17
- **버전 디렉터리 직접 열람**: https://www.unicode.org/Public/17.0.0/ucd/ ; `Unihan.zip` 존재(약 8.1MB), `CJKRadicals.txt` 존재 확인. https://www.unicode.org/versions/Unicode17.0.0/ 에 파일 목록 확인. ZIP 파일 자체 이번 조사에서 다운로드·파싱 **미실행**.
- **데이터 속성 설명 직접 열람**: https://www.unicode.org/reports/tr38/ . 이 URL은 현재 18.0 문서이므로 **17.0의 규칙을 완전하게 대체한다고 보지 않음**. 버전 고정문서: https://www.unicode.org/reports/tr38/tr38-39.html (이번 조사 별도 직접 열람 미실행). `kRSUnicode`는 분류용 번호/잔여 획, `kTotalStrokes`는 일반자형 정렬 목적이며 한국 표준 학습획수의 보증 아님.
- **라이선스 전문 직접 열람**: https://www.unicode.org/license.txt — Unicode License v3. 복제·수정·병합·배포·판매 허용, 저작권 및 허가 문구를 데이터 복사본 또는 관련 문서에 포함. 상업적 앱 번들에 적합한 허용형 조건. 해당 버전 데이터의 별도 예외 유무는 배포본 내 안내와 함께 확인할 것.
- 비용/API: 정적 ZIP 직접 다운로드, 인증키/호출당 과금 필요 없음; 서버 트래픽 정책 별도 미확인. 버전 고정 가능, 업데이트 시 신규 ZIP 별도 취득.

### S4 표준국어대사전
- **원저작자 API 명세 직접 열람**: https://stdict.korean.go.kr/openapi/openApiInfo.do — XML/JSON, 키 필요, 원어(original_language), 뜻풀이 등 제공 확인. **한 글자 단독 부수·총획 API 필드 미확인**.
- **공식 API 허브 직접 열람**: https://kdict.korean.go.kr/info/openapi — 사전별 이용 정책이 다르다고 안내.
- **이용 조건 원문**: https://kdict.korean.go.kr/info/copyright (페이지 열람, 사전별 적용/제3자 용례 개별조건은 미확인); https://creativecommons.org/licenses/by-sa/2.0/kr/legalcode.ko (표준국어대사전 개별 항목에 자동 적용이라고 가정 금지).
- 과금·일일 제한·전체 다운로드 허용 여부·커버리지 미확인. API 실제 호출 미실행.

### S5 우리말샘
- **원저작자 API 명세 직접 열람**: https://opendict.korean.go.kr/service/openApiInfo — XML/JSON 검색, 인증키, `original_language`·`definition` 예시 확인. API 결과에 외부 매체 출처가 붙는 사례 있으므로 각 항목의 권리를 살펴야 함.
- **이용 조건 안내**: https://kdict.korean.go.kr/info/copyright (원문 직접 열람); 적용 권리 범위 및 타 출처 인용의 별도 조건 추가 확인 필요.
- 호출량·요금·고정 덤프 및 1,566자 매칭률 미확인. 인증키 발급·API 호출 미실행.

### S6 AnimCJK (별도 획순)
- **프로젝트 원문 직접 열람**: https://github.com/parsimonhi/animCJK/blob/master/README.md — 언어권 폴더와 SVG의 획별 path + CSS 애니메이션 방식, 파일명=문자 Unicode 10진수 확인. 한국 폴더 535자라는 설명(저장소 소개 시점에 따라 수치 변동 가능).
- **라이선스 적용 범위 원문 직접 열람**: https://github.com/parsimonhi/animCJK/blob/master/licenses/COPYING.txt — 한자 SVG/graphics는 Arphic Public License, 다른 코드·파일 LGPL 계열. **SVG와 프로그램 라이선스 구분 필수**.
- **Arphic 전문 직접 열람**: https://github.com/parsimonhi/animCJK/blob/master/licenses/APL/english/ARPHICPL.TXT — 재배포 시 라이선스 원문 유지, 수정 파일 변경 고지, 수정물의 자유 배포 조건. 앱 전체 코드로 미치는 영향은 법적 검토 없이 확정하지 않음.
- API/비용: 정적 GitHub 저장소 파일 내려받기; 정식 상용 호출형 API는 확인하지 못함. 해당 1,566자의 SVG 존재 조사·실제 재생·한국 획순 대조는 이번 범위 밖으로 **미실행**.

## 교차 검증·출처 계보
- 표준국어대사전·우리말샘·한국어기초사전은 모두 국립국어원 계열로, 다른 웹사이트에 인용된 동일 어휘를 독립 검증으로 계산하지 않음.
- HanjaKey 및 ATPIA 등의 2차 통합 저장소는 데이터 재게시/변환 사례이지 Unihan·국립국어원·libhangul에 대해 독립 관찰을 추가하는 원천이 아님.
- Unihan `kHangul`을 한국어 훈으로 해석하지 않고, `kRSUnicode` 번호를 부수 이름으로 해석하지 않음.
- 호환 한자 38자의 NFKC는 탐색 힌트만 허용. 코드포인트·읽기·자형·획수·획순 원문 유지가 기본.
