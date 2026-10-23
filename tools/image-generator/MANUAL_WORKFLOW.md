# 7단계: ChatGPT Plus 수동 제작·가져오기

## V2 전용 최종 승인 (구현됨, 운영 실행은 별도 지시)

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/manual_workflow.py approve-v2 --id 1 --preview assets/previews/0001_layout_v2_centered.webp --layout tools/image-generator/layouts/0001_v2.json --reviewer "사용자" --confirm-review
```

V2 보고서와 현재 원본·승인된 대본·배치 설정·정식 파일을 검증합니다. 정식 파일과 미리보기의 바이트 및 해시가 일치해야 합니다. V1 체크포인트는 읽지 않고 `approvals_v2/<ID>/<출력해시>.json`에 별도 증빙을 저장합니다. 기존 V1 `approve`는 그대로 유지됩니다. 이 명령은 이미 반영된 정식 파일을 승인하며 이미지를 교체하거나 생성하지 않습니다.

수동 상태는 `needs_review → completed/approved`, 운영 상태는 수동 검수 결과를 받아 `pending 또는 needs_review → needs_review → completed/approved`로 동기화합니다. 중간 상태는 트랜잭션 안에서 준비하며 최종 상태만 게시합니다. 기존 completed는 동일 결과의 복구·중복 요청에 사용할 수 있습니다.

원본 CSV와 두 manifest의 잠금을 모두 획득하고, 임시 경로에서 CSV 기록 및 manifest 최종 내용을 준비합니다. CSV 저장 검증 실패 시 운영 파일은 바뀌지 않습니다. 원본 CSV 백업과 `v2_approval_transaction.json`에 이전·이후 바이트를 기록한 뒤 CSV → 수동 manifest → 운영 manifest → V2 승인 증빙 → 트랜잭션 확정 순으로 게시합니다. 예외 시 세 파일을 롤백합니다. 프로세스가 종료되면 다음 동일 명령에서 미확정 트랜잭션을 먼저 롤백하고 검증부터 재시도합니다. 외부 변경이 발견되면 복구를 중단합니다.

여러 파일을 하나의 파일시스템 연산으로 원자적으로 바꾸는 것은 아닙니다. 파일별 원자적 교체와 잠금·복구 기록을 사용하므로 잠금을 사용하지 않는 외부 독자는 잠깐 중간 상태를 볼 수 있습니다. 복구 실패 시 같은 명령을 재시도하고, 외부 변경 오류가 있으면 임의로 journal을 지우지 말고 확인해야 합니다. 실제 승인 시에는 CSV도 갱신됩니다.

## 최종 승인 후 원본 CSV 파일명 기록

수동 `approve`가 결과물·검수 기록·해시를 확인하고 manifest를 `completed/approved`로 저장한 뒤, 실제 유효한 512×1536 WebP의 파일명을 원본 CSV에 기록합니다. `prepare`, `import`, 미리보기는 기록하지 않습니다. API 엔진의 최종 승인에도 연결되며 mock 승인은 기록하지 않습니다.

기존 원본은 헤더 없는 UTF-8 BOM 2열 `한자,독음`입니다. 첫 기록 시 `hanja,reading,image_filename` 헤더와 파일명 열을 추가합니다. 이후에는 기존 `image_filename` 열을 재사용하고 다른 열·값·행 순서를 보존합니다. ID는 헤더를 제외한 1부터 시작하는 데이터 행 순번으로 유지합니다. BOM 유무와 줄바꿈 형식도 보존합니다. 다른 행에는 빈 파일명만 추가되며 기존 한자·독음은 바꾸지 않습니다.

원본 파일 잠금 아래 원본 바이트를 `<CSV파일명>.<원본 SHA-256>.bak`에 먼저 저장·flush한 뒤 임시 파일의 원자적 교체로 갱신합니다. 같은 파일명은 다시 쓰지 않으며 다른 파일명이 이미 있으면 중단합니다. CSV 저장이 실패한 경우 승인 기록은 유지됩니다. 같은 최종 승인 명령을 재실행하면 결과물·해시를 다시 확인하고 CSV 기록을 재시도합니다. 이미지 재생성은 없습니다. 미리보기 레이아웃의 운영 승인은 이 기능으로 자동 수행되지 않습니다.

이 경로는 API 키 없이 동작하는 로컬 Python 도구입니다. ChatGPT나 Codex의 이미지 생성 기능,
API, 브라우저 자동화, 다운로드 자동화를 호출하지 않습니다. 기존 API 엔진과 비용 보호는 유지하며
`config.toml`의 `allow_live=false`도 유지합니다.

## 현재 준비 결과

원본에는 한자·독음만 있고 검증된 의미·대본은 없으므로 **695개 모두 meaning_pending**입니다.
의미를 임의로 채우지 않았고 그림 프롬프트는 **0개**입니다.
`data/manual_workflow/catalog.json`에 695개를 원본 순서와 고유 ID 그대로 등록했습니다.
제작 상태는 `data/manual_workflow/image_manifest.csv`에서 관리하며 운영 `data/image_manifest.csv`를 수정하지 않습니다.
준비 결과는 `data/manual_workflow/preparation_report.json`에 있습니다.

## 1. 검증된 의미와 대본 준비

저장소 루트 PowerShell에서 실행합니다.

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/manual_workflow.py prepare
```

처음에는 카탈로그와 별도 manifest를 만들고, 재실행하면 기존 검수 내용과 상태를 보존합니다.
원본 ID·한자·독음·파일명·순서는 변경하면 안 됩니다. 중복 한자·독음 및 4글자가 아닌 항목도 유지합니다.

사람이 `catalog.json`의 해당 항목에 다음 값을 채웁니다.

- `meaning`: 사전 등 출처로 확인한 정의.
- `meaning_sources`: URL, 서명·쪽수 등 확인 가능한 출처 문자열 목록.
- `meaning_reviewer`, `meaning_reviewed_on`: 검수자와 `YYYY-MM-DD` 검수일.
- `meaning_status`: 사람이 의미를 확인한 뒤에만 `verified`.
- `story`: 아래 구조의 4컷 대본. 직접 작성하거나 ChatGPT에서 **텍스트 초안만** 받아 사람이 검수합니다.
- `story_reviewer`, `story_reviewed_on`, `story_status=verified`: 의미에 맞는 대본과 어린이 적합성을 확인한 뒤 입력.

```json
{
  "meaning": "여기에 검증한 정의를 그대로 넣습니다",
  "panels": [
    {"scene": "English visual description of setup and characters.", "dialogue": "한국어 대사"},
    {"scene": "English visual description of a concrete problem and characters.", "dialogue": "한국어 대사"},
    {"scene": "English visual description of a solution and characters.", "dialogue": "한국어 대사"},
    {"scene": "English visual description of the story ending and characters.", "dialogue": "한국어 대사"}
  ]
}
```

위 JSON은 형식 설명이며 검증된 숙어 대본이 아닙니다. `story.meaning`은 검증한 `meaning`과 정확히 같아야 합니다.
각 대사는 46자 이하, 한국어를 포함해야 하며 마지막 대사에는 정답 한자·한글 독음을 넣지 않습니다.
각 장면 설명은 한글·한자 답이 그림 프롬프트로 유출되지 않도록 영어로 작성합니다.
장면마다 인물과 사건을 묘사하고, 4컷이 해당 의미를 설명하는 하나의 이야기인지 검수합니다.

프로그램은 출처와 검수 기록의 형식·일치 여부를 검사하며 **출처의 진실성이나 의미의 정확성을 자동 판정하지 않습니다**.
의미가 미검수이면 이미지 프롬프트를 보류하고, 의미만 검수되었으면 `story_pending`으로 대본 검수를 기다립니다.

## 2. 개별 프롬프트 내보내기

검수를 마친 후 `prepare`를 다시 실행합니다. 준비된 항목만 다음 제작 패키지를 만듭니다.

```text
data/manual_workflow/prompts/0001/<검수 내용 해시>/
  production.json       순번·원본 한자·독음·검증된 의미·출처·4컷 장면·대사·검수 정보
  image_prompt.txt      그림 설명과 스타일·금지사항만 담은 이미지 생성용 프롬프트
```

요구한 정보는 항목별 제작 패키지에 모두 포함합니다. **ChatGPT 그림 생성에는 image_prompt.txt만 복사합니다.**
한자·독음·대사가 있는 `production.json`을 그림 생성 지시로 통째로 붙이지 않습니다.
프롬프트에는 귀엽고 밝은 파스텔톤 전통 마을, 한복 SD 캐릭터, 위에서 아래로 독립된 4컷,
모든 컷의 장면·인물, 글자·한자·말풍선·컷 번호·워터마크를 그리지 말라는 지시가 들어갑니다.
실제 글자는 가져오기 후 Pillow로 합성합니다.

내용이 변경되면 새 해시 경로로 내보내며 이전 패키지를 덮어쓰지 않습니다.

## 3. 사용자가 ChatGPT에서 생성하고 저장 (이번 단계에서는 하지 않음)

나중에 이미지 생성이 승인되면 사용자가 Plus의 포함 사용량으로 그림을 만들고 다운로드합니다.
PNG 원본을 `assets/imports/0001.png`처럼 순번으로 저장합니다. 한 숙어당 한 장이며 여러 숙어를 한 그림에 넣지 않습니다.
정확한 최종 크기를 ChatGPT가 보장한다고 가정하지 않습니다. 도구가 별도로 512×1536 WebP를 만듭니다.

최소 각 변 512px, 최대 8,294,400픽셀, 30MB 이하의 단일 프레임 PNG를 받습니다.
회전 EXIF가 있는 파일은 경계 좌표 혼동을 막기 위해 거부합니다.

이미지가 준비된 뒤 아래 명령으로 해시와 크기를 확인합니다. 이 명령은 이미지를 생성하지 않지만 기존 PNG를 읽습니다.

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/manual_workflow.py inspect-import --id 1
```

## 4. 원본 ID와 컷 경계 확인

사람이 해당 그림이 올바른 숙어의 프롬프트 결과인지, 중요한 인물·장면이 컷 경계를 넘지 않는지 확인하고
`assets/imports/0001.json`을 작성합니다.

```json
{
  "id": "1",
  "hanja": "원본 CSV의 한자 문자열을 그대로 넣습니다",
  "reading": "원본 CSV의 독음을 그대로 넣습니다",
  "identity_confirmed": true,
  "reviewer": "확인한 사람",
  "image_prompt_sha256": "production.json에 기록된 프롬프트 해시",
  "artwork_sha256": "inspect-import에서 확인한 PNG 해시",
  "verified": true,
  "cut_lines": [0, 384, 768, 1152, 1536]
}
```

위 숫자는 높이가 1536인 균등 4컷의 **형식 예시**일 뿐입니다. 실제 그림에서 확인한 5개 절단 위치를 넣습니다.
0부터 원본 높이까지 엄격히 증가해야 하며, 프로그램은 전폭을 빠짐없이 연속 분할합니다.
2×2 배치나 절단선을 넘는 인물이 있는 그림은 승인하면 안 됩니다.

파일명·ID·한자·독음·프롬프트 해시·PNG 해시와 사람의 확인 표시를 모두 검사합니다.
**글자 없는 그림의 의미나 정체성을 파일명만으로 자동 확인하지는 못합니다.**

## 5. 가져오기와 Pillow 합성

다음은 구현된 명령이며 이번 단계에서는 실제 이미지로 실행하지 않았습니다.

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/manual_workflow.py import --id 1
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/manual_workflow.py status
```

검증된 패키지·동일한 PNG·sidecar만 받습니다. 글꼴의 실제 로딩과 한글·한자 cmap 지원을 검사하며 조용히 대체하지 않습니다.
확인된 각 영역을 `contain`으로 508×190 그림 영역 안에 비율 유지 배치합니다.
말풍선 꼬리 아래에 여백을 둬 그림을 가리지 않으며, 대사·번호·정답·고지는 별도 영역에 배치합니다.
텍스트 상자의 캔버스 이탈과 그림/다른 텍스트 상자 겹침, 필수 문구·번호 순서·원본 정답 일치를 검사합니다.
이는 합성 명령과 배치 기록의 검증이며 OCR이나 인물 검출에 의한 픽셀 의미 검증은 아닙니다.

최종 512×1536 WebP의 이름은 기존 `0001_가가호호.webp` 형식을 그대로 사용합니다.
마지막 컷 정답에는 원본 문자열의 공백·괄호·호환 한자까지 그대로 사용합니다.
마지막 컷에 독음은 합성하지 않고 `AI가 제작한 이미지입니다`를 넣습니다.
압축 목표는 100~200 KiB입니다. 글자 크기나 품질을 과도하게 낮추지 않으며 범위를 벗어나면 메타데이터에 기록합니다.

자동 검사 후에도 별도 manifest의 상태는 `needs_review/pending`입니다.
운영 `data/image_manifest.csv`와 비용 원장은 수정하지 않습니다.

## 6. 사람 검수와 완료 처리

의미·장면·인물 일치, 한국어 대사, 정확한 한자, 마지막 컷의 독음 부재, 고지문과 가독성,
어린이 적합성을 사람이 확인한 뒤에만 실행합니다.

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/manual_workflow.py approve --id 1 --reviewer "검수자" --confirm-review
```

원본·패키지·그림·sidecar·최종 파일의 해시가 바뀌었으면 완료 처리하지 않습니다.
승인 기록을 저장한 뒤 별도 manifest에서만 `completed/approved`로 변경합니다.
완료 항목은 다시 가져와도 건너뛰고 파일을 덮어쓰지 않습니다.

상태·오류는 별도 manifest에, 원본 연결·합성 기록·압축 정보·해시·승인은 `work/0001/`에 보관합니다.
완성 전 단계 결과와 결과 기록을 저장하고 최종 파일을 원자적으로 새로 게시합니다.
최종 파일 게시 직전/직후 중단되어도 체크포인트를 재사용하며, 다른 내용의 기존 파일은 덮어쓰지 않습니다.
기존 미추적 최종 파일도 덮어쓰지 않고 오류를 기록합니다.

`--workspace`, `--imports`, `--output`으로 별도 경로를 지정할 수 있으나 서로 포함되는 경로는 거부합니다.
원본 운영 manifest를 작업용 manifest 경로로 지정하는 것도 거부합니다.

## Codex 이미지 생성 공식 문서 조사

확인일: 2026-10-20. [공식 이미지 생성 안내](https://learn.chatgpt.com/docs/image-generation)는
IDE 확장 채팅에서 이미지를 요청할 수 있고, CLI의 상호작용 세션과 `$imagegen` 호출도 안내합니다.
내장 생성은 Codex 일반 사용량에 포함되며 별도 API 키 경로와 구분됩니다.
따라서 **ChatGPT 계정으로 로그인한 Plus 포함 사용량 내에서는 별도 API 호출 결제 없이 이용 가능한 공식 경로가 있습니다**.
이 설치 버전·계정의 실제 도구 권한과 잔여량은 생성 없이 확인하지 못했습니다.

[공식 사용량 안내](https://learn.chatgpt.com/docs/pricing)에 따르면 이미지 생성은 같은 일반 사용량을 소비하며
비슷한 비이미지 요청보다 평균 3~5배 빠르게 포함 한도를 소모할 수 있습니다.
한도 이후 추가 크레딧을 사용하거나, API 키 인증 경로에서는 API 요금이 적용됩니다.
고정된 “Plus로 695장 보장” 수치는 확인되지 않았습니다. 실제 한도는 사용량 대시보드/CLI `/status`에서 확인합니다.
이 프로젝트는 크레딧 구매나 API 키 fallback을 자동 실행하지 않습니다.

공식 문서에서 확인한 생성 흐름은 대화형 요청이며, 일반적인 프로그래밍 방식 이미지 생성은 API로 안내합니다.
Plus를 무료 무제한 배치 API처럼 사용하는 공개 계약은 확인하지 못했습니다.
따라서 여기서 자동화하는 범위는 검수 데이터 관리·프롬프트 파일 생성·로컬 가져오기·합성·상태 관리입니다.
실제 생성 요청과 다운로드는 사용자가 진행하며, ChatGPT 웹 UI 우회나 대량 자동 요청은 구현하지 않았습니다.

## 테스트와 이번 단계 변경

이미지 생성 금지 조건에서의 테스트 명령:

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/run_no_image_tests.py --report data/step7_tests.json
```

기존 71개와 신규 비이미지 테스트 24개: **95개 통과**.
기존 이미지 테스트 12개와 새 실제 Pillow 통합 테스트 1개는 건너뛰며, 전체 108개를 확인합니다.
실제 PNG 디코딩·픽셀 합성·실이미지 가독성은 이번 단계에서 검증하지 않았습니다.
가져오기·합성 결과의 검수 흐름은 메모리 저장소와 비이미지 바이트 표식/테스트 대역으로 검증했습니다.
이 표식은 실제 PNG/WebP 파일이나 비트맵이 아니며 디스크에 이미지 파일을 쓰지 않습니다.

추가:

- `manual_workflow.py`, `comic_engine/manual.py`, `test_manual_workflow.py`
- `MANUAL_WORKFLOW.md`, `assets/imports/README.md`
- `data/manual_workflow/catalog.json`, `image_manifest.csv`, `preparation_report.json`
- `data/step7_tests.json`

수정:

- `comic_engine/render.py`: 오프라인 경로의 그림-말풍선 여백 조절 인자 추가. 기존 호출의 기본 배치는 유지.
- `run_no_image_tests.py`: 신규 테스트 등록과 실제 Pillow 통합 테스트 skip.
- 루트 `README.md`, 도구 `README.md`: 오프라인 경로 안내 추가.

운영 CSV·운영 manifest·기존 API 코드·가격 파일·비용 원장·`allow_live=false`는 보존했습니다.
실제 이미지 생성, 이미지 가져오기·합성 명령, 유료 API 요청은 실행하지 않았습니다.
