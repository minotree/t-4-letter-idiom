# Vercel 배포 인수인계

## 변경 파일에 따른 자동 빌드 조건 (2026-10-29)

루트 `vercel.json`의 `ignoreCommand`가 `node scripts/ignore-vercel-build.mjs`를 실행한다. Vercel에서는 종료 코드 0이 빌드 건너뛰기, 1이 빌드 진행이다. 저장소 루트 `.` 설정을 유지한다.

- 빌드 진행: `apps/web/`, `packages/`, `data/`의 문서 외 파일, 루트 학습 CSV, `scripts/prepare-data.mjs`, 이 판정 스크립트, 루트 package/lock/workspace/TypeScript/Vercel/Node/pnpm/Git 줄바꿈 설정 변경. 공유 lockfile 변경은 토스 의존성만 바뀌었더라도 보수적으로 빌드한다.
- 건너뛰기: 토스 전용 파일·토스 검사 스크립트·진행 기록·Markdown 문서 등 PWA 빌드 입력 외 파일만 변경한 경우.
- 비교 범위: `VERCEL_GIT_PREVIOUS_SHA`(해당 프로젝트/브랜치의 마지막 성공 배포)부터 `VERCEL_GIT_COMMIT_SHA`까지. 직전 커밋 하나만 비교하지 않으므로 여러 커밋 push·실패 후 재시도에도 누적 변경을 반영한다. 삭제·이동 전 경로도 확인한다.
- 예외: 첫 배포·시스템 환경변수 없음·이전 커밋이 shallow clone에 없음·Git 오류 시 건너뛰지 않고 빌드한다. Vercel의 Automatically expose System Environment Variables가 활성화되어야 한다. 설정 도입 커밋은 `vercel.json` 변경 때문에 빌드 대상이다.
- 환경변수만 바꿔 수동 재배포할 때는 Vercel 재배포 화면의 Ignored Build Step 건너뛰기 옵션을 사용한다. 이 조건은 로컬 `pnpm.cmd build:vercel` 실행에는 영향을 주지 않는다.

로컬 검사: `node --test scripts/ignore-vercel-build.test.mjs`. 종료 코드 분기·토스/문서 제외·PWA/공유/데이터/설정 포함·이동·비교 실패를 검사한다. Vercel의 실제 실행 로그는 사용자 push 후 확인 대기다.

공식 근거(2026-10-29 확인): [ignoreCommand](https://vercel.com/docs/project-configuration/vercel-json#ignorecommand), [Ignored Build Step](https://vercel.com/kb/guide/how-do-i-use-the-ignored-build-step-field-on-vercel), [시스템 환경변수](https://vercel.com/docs/environment-variables/system-environment-variables).

2026-10-24 기준. 사용자가 `vercel.json`의 `outputDirectory`를 `dist`로 변경한 뒤 Vercel 배포 성공을 보고했다. Git 커밋/푸시·Vercel 프로젝트 생성·업로드·배포는 사용자가 진행한다. 서비스 표시 이름은 ‘모두의 이음’(잠정)이다.

## 1. Git 반영 전

저장소 루트에서 실행한다. Node24.x, pnpm10.34.7을 사용한다.

```powershell
pnpm.cmd typecheck
pnpm.cmd test
pnpm.cmd build
pnpm.cmd build:vercel
git diff --check
git status --short
```

- 변경된 앱 코드·설정·문서·콘텐츠 검토본·추가 파일을 함께 검토해 사용자가 커밋/푸시한다. 특히 `LearningMilestones.tsx`, `vercel.json`, `data/cheonjamun/reviewed/six-followup-review.json` 등 신규 파일의 누락에 주의한다.
- `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `packages/shared`, 루트 `sajaseongeo_image_working.csv`, `data/cheonjamun/reviewed/cheonjamun.csv`와 `review.json`, `data/english/words.json`·`source.json`이 저장소에 포함되어야 한다.
- `apps/web/src/data/idioms.json`은 Git 제외가 정상이다. 빌드 전 스크립트가 위 원본을 읽어 생성한다. `dist`, `node_modules`, `tmp`, `.vercel`, 비공개 환경 파일은 커밋하지 않는다.
- `.gitattributes`를 함께 반영한다. 천자문 원본·검토본은 바이트 해시를 검사하므로 Git의 CRLF→LF 자동 변환을 막는다. 기존 인덱스는 LF, 현재 검토 CSV는 CRLF였으므로 속성 파일만 커밋하면 충분하지 않다. 사용자가 Git 반영 시 `.gitattributes`와 `data/cheonjamun/`의 변경 파일을 함께 스테이징하여 원본 바이트가 들어가게 한다. 자동 변환으로 나타난 이 디렉터리의 차이를 임의로 버리지 않는다.
- 배포 빌드는 기존 검토 CSV를 사용한다. Python·Ollama·이미지 생성·외부 콘텐츠 수집·과거 영어 프로젝트 경로는 필요 없다.

## 2. Vercel 프로젝트 연결

사용자가 Vercel에서 Add New → Project로 Git 저장소를 가져온다. 프로젝트 이름은 사용 가능한 영문 이름을 사용하며, 이 문서는 특정 도메인을 확정하지 않는다.

| 항목 | 설정 |
| --- | --- |
| Root Directory | 저장소 루트 `.` (기본값 유지, `apps/web` 선택 금지) |
| Framework Preset | Vite |
| Node.js Version | 24.x (`package.json`에도 고정) |
| Install Command | `pnpm install --frozen-lockfile` |
| Build Command | `pnpm run build:vercel` |
| Output Directory | `dist` (사용자 배포 성공 설정) |
| Environment Variables | `ENABLE_EXPERIMENTAL_COREPACK` = `1` (Production·Preview) |

명령·출력 경로는 루트 `vercel.json`에 들어 있다. Corepack 환경 변수는 Vercel 화면에서 추가해야 하며, 루트 `packageManager: pnpm@10.34.7`을 사용하게 한다. Install Command만 덮어쓰고 Corepack을 활성화하지 않으면 예상과 다른 pnpm 버전이 선택될 수 있다.

앱 실행에 API 키나 서버 환경 변수는 필요 없다. 이미지 제작용 `OPENAI_API_KEY`를 Vercel에 등록하지 않는다. `NODE_ENV=production`을 설치 전에 별도 지정하여 Vite·TypeScript 등 devDependencies를 빠뜨리지 않는다.

설정 확인 후 사용자가 Deploy를 누른다. 빌드 로그에서 Node24.x·pnpm10.34.7·한자915개 데이터 생성·저장소 루트 `dist` 출력을 확인한다. `build:vercel`은 Vite의 `vercel` 모드로 실행하여 `apps/web` 기준 `../../dist`에 출력한다. `outputDirectory: dist`와 실제 산출물 경로가 일치한다. 일반 `pnpm.cmd build`는 기존 `apps/web/dist`에 출력하여 브라우저 검사에 사용한다. 배포 전용 빌드는 루트 `dist`의 이전 산출물을 정리하므로 해당 폴더에 수동 파일을 두지 않는다. 기존 영어 청크 약1.04MB 경고는 빌드 실패가 아니며 별도 최적화 대상이다.

Git 연결 후에는 설정한 Production Branch의 push가 배포를 유발할 수 있다. 해당 브랜치와 Preview/Production 구분을 사용자가 확인한다.

## 3. 배포 후 확인

1. 발급된 HTTPS 주소의 `/`에서 홈이 열리는지, `/#main`·`/#english` 직접 진입과 새로고침이 동작하는지 확인한다. 해시 탐색이므로 전체 경로를 index.html로 바꾸는 rewrite는 추가하지 않았다.
2. 한자915개·영어3339개, 선택 후보 판정·플로팅 입력·이음 기록·별 등급 저장을 확인한다. 자료 개수는 현재 콘텐츠 기준이다.
3. `/sw.js`, `/manifest.webmanifest`, `/icon-192.png`, `/icon-512.png`가 실제 파일로 응답하는지 확인한다. `/sw.js`와 HTML·manifest의 HTTP Cache-Control이 재검증 정책인지 확인한다. 이 헤더는 앱 자체 Cache Storage를 지우지 않는다.
4. 최초 온라인 접속 후 서비스워커 설치를 기다리고 다시 접속한 뒤 오프라인 학습을 확인한다. 최초 다운로드 전 오프라인 실행은 지원하지 않는다.
5. 휴대폰 홈 화면 설치·단독 실행·가상 키보드·회전·다음 버전 갱신을 실제 기기에서 확인한다. 업데이트 안내의 적용 버튼은 현재 세션을 종료하고 다시 로드한다.
6. 고정된 운영 주소를 정한다. localhost·배포마다 달라지는 Preview 주소·운영 도메인은 서로 다른 Origin이므로 학습 기록과 별이 자동 이전되지 않는다. Preview 보호 설정으로 PWA 설치·오프라인이 제한되면 접근 가능한 운영 주소에서 다시 확인한다.

Vercel에서 이전 배포로 되돌려도 이미 설치된 PWA 캐시가 즉시 되돌아간다고 가정하지 않는다. 온라인 재접속·업데이트 안내·사용자 적용 후 화면을 다시 확인한다.

2026-10-24 사용자 보고로 이전 배포 성공을 확인했다. 이후 배포 준비에서 `build:vercel`을 추가하여 저장소 루트의 `dist`를 실제로 생성하도록 일치시켰다. Vercel의 Root Directory는 저장소 루트 `.`, Build Command는 `pnpm run build:vercel`, Output Directory는 `dist`로 사용한다. 기존 Vercel 프로젝트의 실제 Root Directory는 직접 확인하지 못했으므로 사용자가 배포 전에 확인한다. 현재 수정본은 미배포이며 실제 iPhone 키보드·설치·갱신 검증은 대기다. 배포 주소는 사용자 화면의 `https://web-one-black-41.vercel.app`, 커밋·deployment 식별자는 미제공이다. 후속 확인 결과를 `progress.md`에 기록한다.

## 공식 설정 근거

2026-10-24 확인: [정적 프로젝트 설정](https://vercel.com/docs/project-configuration/vercel-json), [빌드·Corepack·루트 경로](https://vercel.com/docs/builds/configure-a-build), [패키지 관리자](https://vercel.com/docs/package-managers), [Node 버전](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions).
