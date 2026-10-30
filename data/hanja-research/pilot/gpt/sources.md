# sources.md
조사일: **2026-10-30**. '직접 열람'은 웹 원문 HTML 확인이며 SVG 바이트 다운로드·파싱을 뜻하지 않습니다. 웹 페이지는 원문이 갱신될 수 있습니다.

## 한국어 텍스트 출처

| ID | 제공자 / 원문 문서 | 직접 URL | 확인 방법 / 뒷받침 | 이용 조건 |
|---|---|---|---|---|
| S1 | 국립국어원 한국어기초사전 `의분` | https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=71870 | 검색으로 본문 확인: 義 옳을 의, 羊, 13획, 다수 추가 훈 | L1 |
| S2 | NAMEChart `정의` | https://www.namechart.kr/name/%EC%A0%95%EC%9D%98 | 원문 직접 열람: 義 '뜻 의', 羊, 13 | 미확인, 복제/번들 승인 불가 |
| S3 | NAMEChart `춘휘` | https://namechart.kr/name/%EC%B6%98%ED%9C%98 | 원문 직접 열람: 暉 햇빛 휘·빛날 휘, 日, 13; 輝 별개 | 미확인, 복제/번들 승인 불가 |
| S4 | 모야랜드 `朗` | https://www.moyaland.com/_new/hanja/item_01.php?it_id=1331446636 | 원문 직접 열람: 밝을 랑, 月, 11획. 다른 출처 10획과 충돌 | 약관 별도 검토 필요, 복제/번들 승인 불가 |
| S5 | 국립국어원 한국어기초사전 `요일` | https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=67865 | 검색 본문 확인: 曜 빛날 요, 日, 18 | L1 |
| S6 | 국립국어원 한국어기초사전 `천막` | https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=77549 | 검색 본문 확인: 天 하늘 천, 大, 4 | L1 |
| S7 | 국립국어원 한국어기초사전 `지도` | https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=57319 | 검색 본문 확인: 地 땅 지, 土, 6 | L1 |
| S8 | 국립국어원 한국어기초사전 `현미` | https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=87160 | 검색 본문 확인: 玄 검을 현, 玄, 5 | L1 |
| S9 | 국립국어원 한국어기초사전 `황해` | https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=69796 | 검색 본문 확인: 黃 누를 황, 黃, 12 (黄 아님) | L1 |
| S10 | 국립국어원 한국어기초사전 `우주복` | https://krdict.korean.go.kr/kor/dicSearch/SearchView?ParaWordNo=69382 | 검색 본문 확인: 宇 집 우·宀·6, 宙 집 주·宀·8 | L1 |

### 교차 검토만 사용(파일 JSON의 사실 출처 ID는 아님)
- https://seq.kr/converter/hanja/%EB%9E%91 : 검색 본문에서 朗 10획, 月; 원획 계산 기준 확인 불가, 이용 조건 미확인.
- https://www.cheonmyeongjae.life/guide/eum-rang : 검색 본문에서 朗 **원획 11획**; 2026-10-25 갱신이라고 표시. 독립 원천 여부 미확인.
- https://wordbook.daum.net/open/wordbook.do?id=491699 : 검색 본문에 天 地 玄 黃 宇 宙 데이터; 편집·재게시 자료로 독립적 검증 취급하지 않음.

## 벡터·획순 자료 출처

| ID | 제공자 / 문서 | 원문 URL | 열람 / 확인 내용 | 조건 |
|---|---|---|---|---|
| S11 | FM&SH / AnimCJK README | https://github.com/parsimonhi/animCJK | 원문 직접 열람. `svgsKo` 한국용, 글자별 SVG 경로·CSS 애니메이션, 파일명은 십진 유니코드. 535개 수록이라고 소개 | L2 |
| S12 | FM&SH / AnimCJK 개별 SVG 파일 항목 | 아래 10자 검사 표 | GitHub HTML 개별 경로 직접 열람. 5개는 파일 메타데이터 존재; 5개는 404. SVG 원본 바이트/획 경로는 열람 불가 | L2 |
| S13 | Shaunak Kishore / Make Me a Hanzi README | https://github.com/skishore/makemeahanzi/blob/master/README.md?plain=1 | 원문 직접 열람. `graphics.txt`의 `strokes`(SVG path)·`medians`(중심선) 구조; 중국 간·번체 혼재. 10자 개별 항목은 미확인 | L3 |
| S14 | David Chanin / Hanzi Writer docs | https://hanziwriter.org/docs.html | 원문 직접 열람. 사용자 정의 데이터 로더, 로컬 번들 가능; 기본 CDN jsDelivr 로드 | L4, 데이터는 L3 계통 |
| S15 | Ulrich Apel / KanjiVG | https://github.com/KanjiVG/kanjivg | 원문 직접 열람. 일본 학교글꼴 기준 SVG, 획별 경로; 이번 10자 파일 검사는 미실행 | L5 |

### AnimCJK `svgsKo` 실제 경로 검사
- 존재 확인(HTML 파일 항목): [天 22825.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/22825.svg), [地 22320.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/22320.svg), [朗 26391.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/26391.svg), [曜 26332.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/26332.svg), [黃 40643.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/40643.svg).
- 404 확인(해당 Ko 경로 한정): [義 32681.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/32681.svg), [暉 26249.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/26249.svg), [玄 29572.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/29572.svg), [宇 23431.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/23431.svg), [宙 23449.svg](https://github.com/parsimonhi/animCJK/blob/master/svgsKo/23449.svg).
- 주의: 성공 항목은 **GitHub 파일 항목 존재**를 검증한 것이고, SVG 콘텐츠의 유효성·정확한 획순·애니메이션 재생을 검증한 것은 아닙니다. Raw SVG는 웹 도구에서 `image/svg+xml` 콘텐츠 형식 제한으로 원문 확인 불가. 이 테스트에서 404는 검색 결과 누락과 달리 특정 URL의 접근 실패 기록이며, 다른 지역 폴더에 없는 것을 증명하지는 않습니다.

## 이용 조건 / 원본 제공자

**L1 국립국어원 한국어기초사전 저작권 정책**
- https://krdict.korean.go.kr/kor/kboardPolicy/copyRightTermsInfo (원문 직접 열람)
- 원문 근거: `누구나 상업적 용도까지 포함하여 자유롭게 이용` / `저작자 표시` / `동일조건변경허락`.
- 명시 라이선스 **CC BY-SA 2.0 대한민국**. 텍스트의 복제·가공·상업 앱 번들은 라이선스 조건 충족을 전제로 허용된다고 해석 가능. 출처 표시와 동일조건 공유가 필요하며, 앱 코드 전체에 대한 적용 범위는 별도 법률 검토 필요.
- 멀티미디어는 개별 조건(텍스트와 동일시 금지). API 요청량, 일괄 다운로드 정책, 사전 전체 복제의 기술적 제약은 미확인.

**L2 AnimCJK SVG 데이터 라이선스**
- https://github.com/parsimonhi/animCJK/blob/master/licenses/COPYING.txt (원문 직접 열람)
- 원문 근거: `You can redistribute and/or modify ... SVG files ... under the terms of the Arphic Public License`.
- 원본 그래픽: Arphic Technology 폰트와 Make Me a Hanzi, 애니메이션 SVG 가공: FM&SH(AnimCJK). Arphic Public License(APL) 적용. 상업적 사용을 금지하는 문구는 확인되지 않았으나 **APL 전문의 세부 공지·변경 표시·번들 재배포 의무 확인은 미완료**. 원본 COPYING과 해당 APL 전문을 함께 패키징할지 법률 검토 필요. 접근 시도한 전문 URL https://ftp.gnu.org/non-gnu/chinese-fonts-truetype/LICENSE 는 웹 도구에서 열리지 않았음.
- AnimCJK의 `graphics*`와 한자 SVG는 APL; **기타 프로그램 파일은 LGPL v3 이상**이라고 구분함. 프로그램과 데이터 혼동 금지.

**L3 Make Me a Hanzi 데이터**
- https://github.com/skishore/makemeahanzi/blob/master/COPYING (원문 직접 열람)
- `graphics.txt`와 애니메이션 SVG는 APL, `dictionary.txt`는 LGPL v3 이상; 각각 다른 원천. 변경·재배포 허용을 명시하지만 APL 전문 의무사항 검토 미완료. 중국 자료이므로 한국 표준 정합성은 미확인.

**L4 Hanzi Writer 엔진 / 별도 데이터**
- https://hanziwriter.org/license.html , https://github.com/chanind/hanzi-writer-data (원문 직접 열람)
- **엔진 MIT**: 상업적 사용 가능, 저작권 헤더 유지. **글자 데이터 APL**: 엔진 MIT로 데이터 재라이선스 불가. `hanzi-writer-data`는 각 글자 JSON을 로컬 저장 가능하다고 문서화하지만 대상 10자 파일의 실존은 미검증. 네트워크 없이 앱에 탑재하는 구성 가능; CDN 기본 동작은 네트워크 필요. 오픈 데이터 자체에 서비스 사용료가 있다는 근거는 확인되지 않았으며 CDN/서버 비용은 운영 방식에 좌우됨.

**L5 KanjiVG**
- https://github.com/KanjiVG/kanjivg 와 https://creativecommons.org/licenses/by-sa/3.0/deed.ko (양쪽 직접 열람)
- **CC BY-SA 3.0**: 상업적 복제·가공·배포 가능. 출처 및 라이선스 링크·변경 알림 필요, 변형물을 공유하면 동일조건 유지, 추가 제한 금지. 일본용 데이터라 한국 교재와 자형·획순 비교 필요. 파일 내부 SVG 벡터를 앱에 포함해 오프라인 구동 가능하나 이번 10자 존재는 미검증.

## 조건이 아직 불명확한 텍스트 소스
NAMEChart / 모야랜드 / seq.kr / cheonmyeongjae.life / 다음 단어장: 상업적 복제·가공·앱 번들·재배포·표시의무에 관한 원본 약관 직접 확인 미완료. 수치 검토용 조회 기록은 남기되 **앱용 복제 라이선스의 근거로 사용하지 않음**.
