# 모두의 이음 · 토스 미니앱

아이콘 교체용 사용자 원본은 `assets/app-icon.PNG`, 축소 PNG는 `apps/web/public/icon-512.png`다(2026-10-28). 콘솔에 표시되는 실제 이미지 규격을 확인한 후 사용자가 등록한다. 로컬 PWA 아이콘 교체가 토스 콘솔 아이콘을 자동 변경하지 않으며 콘솔 등록은 아직 수행하지 않았다.

React 18·Vite·Apps in Toss SDK 3.9.0·TDS 2.5.1 기반 독립 앱이다. PWA 소스·화면·Hook은 가져오지 않고 `@idioms/shared`의 학습 규칙과 검수 원본 데이터만 재사용한다. TDS 이용 범위는 토스 앱 개발로 한정한다.

## 광고 설정 (2026-10-28)

- 사용자 제공 광고 그룹 ID: `ait.v2.live.e2aee41b54214449`.
- 홈·한자·영어 화면의 하단 메뉴 바로 위에 `TossAds.initialize` → `attachBanner`로 배너를 연결한다. `expanded` 원본 크기를 유지하며 하단 영역 실측 높이만큼 본문 여백을 확보한다. 답안·검색 입력 포커스 중에는 배너와 하단 메뉴를 숨긴다.
- 광고 없음·미지원·초기화/렌더링 실패 시 광고 영역을 접고, 컴포넌트 해제 시 배너를 제거한다. 운영 ID의 콘솔 광고 유형 일치·실제 송출·클릭 후 복귀는 토스 실기기 검증 대기다. 자동 검사는 모의 SDK를 사용하며 실제 광고 요청·노출 검증과 구분한다.
- 근거: [공식 TossAds API](https://developers-apps-in-toss.toss.im/documentation/sdk/domains-api/ads/tossads), 설치 SDK 3.9.0 타입·구현 확인(2026-10-28).

배너 회귀 검사에는 프로덕션 빌드와 별도 preview(5175), 전용 Chromium CDP(9223)가 필요하다. 개발 서버의 AIT Devtools가 SDK를 덮어쓰므로 아래 검사는 preview에서 모의 SDK를 주입한다.

```powershell
pnpm.cmd --filter @idioms/toss exec vite preview --host 127.0.0.1 --port 5175 --strictPort
# 별도 터미널
node scripts/check-toss-banner.mjs
```

## 로컬 실행

프로젝트 루트에서 Node 24·pnpm 10으로 실행한다.

```powershell
pnpm.cmd --filter @idioms/toss dev
```

접속: http://127.0.0.1:5174/ (중지: Ctrl+C). SDK 3.x는 별도 샌드박스 앱 대신 브라우저 오른쪽 아래 AIT Devtools로 개발한다. Devtools 모사는 토스 실기기 검증을 대신하지 않는다. PWA 서버 5173과 구분하며 service worker·설치·오프라인 캐시는 제공하지 않는다.

## 구현 범위

- 한자·영어 10문제 완주 순간 `t-crossword-app/apps/toss`의 색종이 효과를 이식한72개 조각이 하단 세 지점에서 솟았다 내려오는 효과를 한 번 재생하고4.5초 후 정리한다. React/CSS만 사용하며 원본 프로젝트를 import하지 않는다. 광고·하단 메뉴 위쪽으로 영역을 제한하고 클릭을 가로막지 않는다. 화면/탭 이동·새 이음 시 중단하고 동작 줄이기 설정에서는 숨긴다. 전용 CDP 9223과 프로덕션 preview 5175를 준비한 뒤 `node scripts/check-toss-celebration.mjs`로 회귀 검사한다(테스트 Origin 저장소 초기화). 실제 토스 기기의 애니메이션 성능은 확인 대기다.

- 홈·한자 915개·영어 3,839개 학습. 글자 → 후보 선택 → 선택 후보 답 입력 → 최대 10개 정답 연결. 세션 중복 제외·미출제 우선·선택 후보 오답 힌트.
- 한글 독음/영어 단어장 검색·즐겨찾기·학습완료·오답 복습, 40개씩 표시. 한자 검색은 두음 변이를 허용한다.
- 메뉴를 바꿔도 세션 유지, 새로고침하면 세션 초기화. 완주 횟수는 10개 정답 때만 적립한다.
- localStorage `idioms:toss:hanja:v1` / `idioms:toss:english:v1`. 저장값 검증 및 읽기·쓰기 실패 안내. PWA 이력을 자동 이전하지 않는다. 현재 저장은 브라우저 어댑터이며 토스 앱 내 유지·프로세스 종료·업데이트 검증 대기.
- UI는 PWA 기준 홈 소개·두 학습 카드·하단 홈/한자/영어 메뉴·학습 패널·퀴즈/단어장 탭으로 구성한다. 초록 문제 카드·뜻 접기·글자 버튼·번호 있는 후보·단어장 분류/검색/별표와 학습 배지를 제공한다. TDS 버튼은 토스 전용으로 사용하며 브랜드 색은 `#2d6050`이다.
- 이음 기록은 항상 펼쳐진 2열 지그재그 카드·글자/방향 화살표·단계별 색·10개 완성 강조다. 10/100회 단위 크기의 누적 완주 별을 표시한다. 한자·영어 입력창은 가시 영역 하단(키보드 위, iOS 도구막대56px 여백)에 배치하며 선택한 후보와 뜻을 입력창 안에 함께 표시한다. 영어 정답 단어/예문은 공개하지 않는다. 후보를 따라 목록/페이지를 강제 스크롤하지 않으며 가시 영역 변화에 맞춰 위치만 보정한다. 사용자의 후보 목록 스크롤/휠/터치 이동·닫기·Escape·메뉴 이동 시 닫고 포커스를 해제한다. 정답 후 현재 카드로 이동한다.
- 영어 현재 카드의 동의어·예문 및 해석 보기/접기, 단어장 예문·해석을 제공한다. 단어장 예문 듣기·느리게(0.75배)·정지를 제공하며 메뉴·분류·검색 변경 및 백그라운드 전환 시 정지한다. 기기 음성을 사용하는 브라우저 TTS로 미지원·실패·시작 지연을 안내한다. 실제 토스 WebView의 재생 및 오프라인 음성 지원은 기기 검증 대기다. 토스 자체 상단바·뒤로가기·키보드와 실제 기기 검증도 대기다.
- 영어 단어장 검색은 단어·뜻·품사를 포함한다. 영어 퀴즈 후보는 40개씩 더 보기로 표시하며 글자 변경·정답·새 이음 때 초기화한다. PWA 설치·service worker·오프라인 캐시·업데이트 안내는 이식하지 않는다.

## 검사·번들

```powershell
pnpm.cmd typecheck
pnpm.cmd test
pnpm.cmd --filter @idioms/toss build
node scripts/check-toss-browser.mjs
```

브라우저 검사는 5174 개발 서버와 **전용 임시 프로필**의 Chromium CDP 9223이 필요하다. 테스트 Origin의 저장소를 지우므로 개인 브라우저에 연결하지 않는다. 홈·320/390px·가로844px·데스크톱1280px 넘침·한자 오답/정답·후보 플로팅 위치/재선택/스크롤 닫기·입력 포커스 중 하단 메뉴 숨김·상태 유지·사슬/화살표·단어장·즐겨찾기·영어 10문제 완주/사슬/별 적립·런타임 오류를 검사한다. 스크린샷은 `tmp/browser-checks/toss-home.png`, `toss-quiz.png`, `toss-chain.png` 및 `tmp/toss-mobile.png`.

`.ait` 생성에는 앱인토스 콘솔에서 등록한 실제 `appName`을 제공해야 한다. 임의 앱 ID는 운영 설정으로 사용하지 않는다.

```powershell
$env:TOSS_APP_NAME = '<콘솔에 등록한 실제 appName>'
pnpm.cmd --filter @idioms/toss bundle
```

`build`는 웹 빌드이며 `bundle`이 웹 빌드 후 `ait build`를 실행한다. 콘솔 ID가 미확정인 현재 `.ait` 생성은 미검증이다. 아이콘·표시 이름은 SDK 3.x 기준 콘솔에서 관리한다. 업로드·검토·출시는 사용자가 별도로 수행한다. 토큰을 소스·문서에 넣지 않는다.

SDK 3.9.0 테스트 Origin은 `https://<appName>.private-apps.tossmini.com`, 공개 Origin은 `https://<appName>.apps.tossmini.com`. 실제 appName 확정 후 각각 실기기에서 확인한다. 현재 서버·인증·광고·CORS 변경은 없다.

## 확인 근거 (2026-10-26)

- [공식 WebView 시작 안내](https://developers-apps-in-toss.toss.im/ai-vibe-coding/tutorials/webview)
- [SDK 3.x 설정·Devtools·Origin](https://developers-apps-in-toss.toss.im/documentation/integration/sdk-3.x)
- [TDS 사용 범위](https://developers-apps-in-toss.toss.im/design/components)

npm 실조회와 설치 타입으로 SDK 3.9.0·TDS 2.5.1·React 18 peer 호환을 확인했다. SDK는 Apache-2.0이며 TDS는 위 토스 이용 범위를 따른다. 초기 토스 청크 약 2.44MB(gzip 735KB) 경고가 있어 배포 전 영어 자료 지연 로딩과 번들 크기를 개선할 여지가 있다. pnpm은 esbuild 0.28.2·protobufjs 설치 스크립트를 차단했으며 현재 타입·웹 빌드·개발 서버는 통과했다. `.ait` 생성 단계에서의 영향은 미검증이다.
