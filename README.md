# 사자성어 학습 모노레포

사자성어 학습 앱과 695개 한자숙어의 4컷 만화 이미지 자동 생성 시스템을 위한 pnpm 모노레포입니다.
웹 앱은 한자915개(기존666개·천자문 신규249개)와 영어3839개의 이음 퀴즈·단어장·PWA를 제공합니다.
한자 선택 → 후보의 한자·뜻 읽기 → 한글 독음 입력 → 정답 성어에서 다음 연결 순서로 학습합니다.
프로덕션 빌드에서 최초 온라인 준비 후 텍스트 학습을 오프라인으로 진행할 수 있습니다.
자세한 지원 범위와 검증 한계는 [웹 운영 안내](apps/web/README.md)를 참고합니다.
CSV 검증과 이미지 자동 생성 엔진은 구현되어 있으며, 실제 API 호출은 기본 설정에서 차단됩니다.

## 프로젝트 구조

```text
apps/
  web/                     React + TypeScript + Vite 초기 앱
  mobile/                  Ionic + React + Vite + Capacitor 준비 폴더
  toss/                    TDS + React + Vite 토스 미니앱 준비 폴더
packages/
  shared/                  공통 타입 및 데이터 모델 패키지
tools/
  image-generator/         CSV 검증 및 4컷 만화 생성 엔진
data/                      원본 CSV 및 제작 관리 데이터
assets/
  idioms/                  최종 WebP 이미지
.env.example               API 키 환경변수 이름만 제공
pnpm-workspace.yaml        워크스페이스 패키지 경로
```

## 웹 앱 실행

Node.js24.x와 pnpm10.34.7을 사용합니다. 데이터 준비·테스트에서 TypeScript 직접 실행을 사용합니다.
저장소 루트에서 실행합니다.

```powershell
pnpm install
pnpm dev
```

터미널에 표시되는 Vite 주소로 접속합니다. 기본 주소는 `http://localhost:5173`입니다.
PowerShell 실행 정책으로 `pnpm.ps1`이 차단되면 `pnpm.cmd`를 사용합니다.

```powershell
pnpm typecheck
pnpm test
pnpm build
pnpm preview
```

빌드 결과는 `apps/web/dist/`에 생성됩니다.
Vercel 배포 설정은 루트 `vercel.json`, 사용자 연결·설정 절차는 [Vercel 배포 안내](docs/deploy-vercel.md)를 참고합니다. Git 작업과 실제 배포는 사용자가 진행합니다.
모바일 및 토스 앱은 README만 존재하며 패키지 설치와 실행 설정은 보류했습니다.
공통 패키지 `@idioms/shared`는 순수 TypeScript 데이터 검증·후보 선정·답안 판정을 제공합니다.
학습 기준 데이터는 루트 `sajaseongeo_image_working.csv`입니다. 시작·빌드·타입 검사 전에 필요한 필드만 JSON으로 추출하며 제작 관리 메모는 번들에 넣지 않습니다.
요구사항은 [기획 문서](docs/requirements.md), 검증 결과는 [진행 기록](progress.md)에서 관리합니다.

## 이미지 제작 도구 및 데이터

Python 도구의 환경 준비 방법은 [도구 README](tools/image-generator/README.md)를 참고합니다.
[데이터 검증](tools/image-generator/DATA_VALIDATION.md)과 [생성 엔진 실행 안내](tools/image-generator/ENGINE.md)를 제공합니다.
원본 CSV와 manifest는 `data/`, 최종 WebP의 운영 저장 위치는 `assets/idioms/`입니다.
현재 검증은 API 호출 없이 dry-run과 mock으로만 수행하며 mock 이미지는 도구의 `tmp/mock-run/`에 분리합니다.

별도 API 결제 없이 사용자가 ChatGPT에서 만든 그림을 가져오는 [오프라인 제작 경로](tools/image-generator/MANUAL_WORKFLOW.md)도 제공합니다.
검증된 의미·대본으로 프롬프트를 내보낸 뒤 `assets/imports/0001.png`처럼 저장한 그림을 로컬 Pillow로 합성·검수합니다.
제작 상태는 별도 manifest에 관리합니다. 과거 695개 제작 manifest에서는 ID 1 승인·나머지 694개 대기로 기록되어 있습니다. 현재 학습용 최종 CSV 666개와는 별도 자료이며 자동 병합하지 않습니다.
이미지 생성 금지 단계의 테스트는 `tools/image-generator/run_no_image_tests.py`로 실행합니다.

## 환경변수와 비밀 정보

`.env.example`은 `OPENAI_API_KEY=`만 포함하며 실제 키가 없습니다.
필요한 시점에 로컬 `.env`를 만들고 실제 키를 보관합니다.
API 키를 `VITE_` 환경변수나 웹 소스에 넣지 않습니다.
`.env`, `.env.local`, Python 가상환경, 의존성, 빌드 결과 및 생성 중 임시 파일은 Git에서 제외됩니다.
`assets/idioms/`의 최종 이미지는 제외하지 않습니다.
