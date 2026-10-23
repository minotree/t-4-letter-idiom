# 4컷 만화 자동 생성 엔진

## 6-3단계 비용 보호

`--max-cost-usd`, `--confirm-live`, `--cost-report`와 누적 사용량 원장을 구현했습니다.
예약 정책·가격 유효기간·미확정 요청 처리·안전 조건은 [비용 보호 안내](COST_SAFETY.md)를 참고합니다.
과거 단계 보고서의 “금액 옵션 미구현”은 당시 상태이며 현재는 위 옵션이 구현되어 있습니다.
이 기능은 실제 결제 상한을 보장하지 않습니다. `allow_live=false`는 유지합니다.

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/generate.py --cost-report --limit 3 --max-cost-usd 2.40
```

## 6-2단계 변경

현재 기본 모델은 `gpt-image-2.5-flare-2026-09-08`이며 `allow_live=false`를 유지합니다.
지원 크기·품질·단가 및 생성 방식 비교는 [모델 검토 보고서](MODEL_REVIEW_6_2.md)를 참고합니다.
모델별 설정 검증에서 검토되지 않은 모델, deprecated 모델, 잘못된 크기·품질을 요청 전에 차단합니다.

실제 한 장 4컷 그림은 `work/ID/panel_bounds.json`의 해시와 검수된 수평 경계가 있어야 합성합니다.
그림 저장 후 이 파일이 없으면 `needs_review/layout_pending`으로 대기하며 최종 WebP를 만들지 않습니다.
사람이 경계를 확인한 뒤 `--resume-layout --ids ID`로 기존 대본·그림을 재사용해 합성합니다.
이 단계도 실제 실행 승인과 live 설정이 필요합니다. Mock의 등분 방식은 유지합니다.
이전 설정의 Mock 체크포인트는 보존하며 새 설정을 검증할 때에는 별도의 `--sandbox` 경로를 사용합니다.

이미지 생성 금지 상황에서의 테스트 명령:

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/run_no_image_tests.py
```

이 실행기는 이미지 관련 12개를 건너뛰며, 일반 unittest 전체 실행은 임시 이미지를 생성하므로 현재 단계에서 실행하지 않습니다.

## 현재 단계의 비용 보호

이번 단계에서는 OpenAI API를 호출하지 않습니다. 기본 실행은 읽기 전용 dry-run이고,
`config.toml`의 `allow_live = false`는 실제 실행을 차단합니다. Mock은 로컬 Pillow 도형과
고정 대본으로 배치·파일·상태 관리만 검증합니다. **숙어별 의미를 설명하는 완성 만화가 아닙니다.**

Mock 실행은 키를 읽거나 SDK 클라이언트를 만들지 않습니다. 기본 mock 경로는
`tools/image-generator/tmp/mock-run/`이며 그 안에 manifest 복사본, assets, work를 둡니다.
실제 `data/image_manifest.csv`와 `assets/idioms/`에는 mock 결과를 쓰지 않습니다.

## 설치와 실행 (저장소 루트, PowerShell)

```powershell
python -m venv tools/image-generator/.venv
tools/image-generator/.venv/Scripts/python.exe -m pip install -r tools/image-generator/requirements.txt

# 전체 데이터 검증은 기존 명령을 그대로 사용
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/validate_data.py

# API·이미지 생성·파일 변경 없이 계획 확인 (옵션 생략도 dry-run)
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/generate.py --dry-run --limit 3

# 전체 manifest의 한자와 현대 한글 음절, 독음, 고지문, 컷 번호 글리프 확인
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/generate.py --check-fonts

# 비용 없는 로컬 샘플 1개 (원본 상태 보존)
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/generate.py --mock --ids 1 --limit 1

# 같은 sandbox를 재사용하면 완료·검수 대기 항목은 건너뜀
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/generate.py --mock --limit 3

# 실패 항목의 명시적 재시도
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/generate.py --mock --ids 1 --retry-failed

# 사람이 mock 배치를 확인한 뒤, 복사본에서만 완료로 표시
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/generate.py --mock --approve 1

# 네트워크 연결이 차단된 자동 테스트
tools/image-generator/.venv/Scripts/python.exe -m unittest discover -s tools/image-generator -p "test_*.py" -v
```

`--sandbox`로 mock 작업 폴더, `--ids`로 고유 순번, `--limit`로 처리 개수(기본 1)를 지정합니다.
`--font-report 경로`는 `--check-fonts`와 함께 새 파일에만 저장할 수 있습니다.
`--dry-run`에서는 보고서 쓰기도 금지됩니다.

## 모듈과 처리 순서

- `story.py`: Responses API의 JSON Schema로 의미·4개 장면·한국어 대사를 생성하고 구조를 검사합니다.
- `artwork.py`: 대사와 한자 답을 보내지 않고 장면 설명으로 글자 없는 세로 4컷 그림 한 장을 요청합니다.
  장면 설명에 한글·한자가 포함되면 대본 검증에서 차단하여 그림 API로 전달하지 않습니다.
- `fonts.py`: fonttools cmap과 Pillow 로딩으로 설정된 글꼴을 검증합니다. 조용한 대체는 없습니다.
- `render.py`: 확인된 경계를 따라 각 컷을 분리해 종횡비를 유지해 배치하고, ①~④·말풍선·대사를 합성합니다.
  마지막 컷에는 원본 한자 문자열을 그대로 합성하고 독음은 표시하지 않으며 AI 제작 고지문을 넣습니다.
- `api.py`: 공식 OpenAI SDK를 지연 초기화하고 타임아웃·연결 오류·429·408·409·5xx를 제한적으로 재시도합니다.
- `manifest.py`, `pipeline.py`: 원본과 manifest의 ID·값·순서·파일명 일치 검사, 프로세스 잠금,
  원자적 파일 교체, 체크포인트, 재개, 실패 원인 기록, 검수 완료 처리를 담당합니다.

설정은 `config.toml`에 있습니다. 대본 모델, 이미지 모델·품질·요청 크기, 타임아웃·시도 횟수,
WebP 품질 하한·목표 용량, 한국어·한자 글꼴 경로와 TTC face index를 변경할 수 있습니다.
Windows의 맑은 고딕과 바탕을 명시적으로 설정했습니다. 다른 환경에서는 설치한 글꼴 경로를 설정해야 합니다.
글꼴을 프로젝트에 복사하거나 재배포하지 않습니다.

원본의 후행 공백·괄호·호환 한자도 답에서 정규화하거나 삭제하지 않습니다.
대본에 새로 나온 문자도 그림 API 호출 전에 지원 여부와 말풍선 배치를 검사합니다.
원본 문자열 보존은 합성 기록에서 확인하며 OCR로 픽셀을 재인식하는 검증은 아닙니다.

최종 파일은 512×1536 정적 WebP이며 원본 순번+독음 파일명을 유지합니다.
용량 목표는 100~200 KiB입니다. 품질 100부터 설정 하한(기본 82)까지 시도하고
가독성 때문에 더 낮추지 않습니다. 작은 그림을 무의미하게 100 KiB까지 부풀리지 않으며,
목표 범위 밖이면 결과 메타데이터의 `compression.within_target`과 `size_note`에 기록합니다.

## 상태와 재개

`pending → generating → needs_review → completed` 흐름이며 예외는 `failed`로 기록합니다.
`completed`와 `needs_review`는 다시 생성하지 않습니다. 실패는 `--retry-failed`로만 재선택합니다.
중단된 `generating`은 다음 실행에서 선택하며 저장된 대본·원본 그림·완성 결과 체크포인트를 재사용합니다.
동일 한자·독음도 ID별 별도 작업 디렉터리와 파일명으로 구분합니다.

`work/0001/`에는 `identity.json`, `story.json`, `artwork.png`, `result.json`을 저장합니다.
실제 그림의 `panel_bounds.json`이 없으면 `result.json`과 최종 이미지는 아직 생성하지 않고 경계 검수를 기다립니다.
결과 기록에는 원본 답·합성 문구·글자 크기·위치·용량·품질·SHA-256과 검수 체크리스트가 있습니다.
다른 입력·설정의 체크포인트나 출처를 확인할 수 없는 기존 결과를 덮어쓰지 않습니다.
설정을 바꿔 재제작하려면 기존 결과를 검토한 뒤 별도 작업·출력 폴더를 지정해야 합니다.

OS 파일 잠금은 중복 실행을 막고 비정상 종료 시 운영체제가 해제합니다. `.lock.tmp` 표시는 재사용됩니다.
원자적 교체는 개별 파일 단위이며 이미지와 manifest의 동시 트랜잭션은 아닙니다.
이미지가 저장된 직후 중단되어도 결과 해시를 확인해 추가 API 호출 없이 복구합니다.
API 응답 수신과 로컬 체크포인트 저장 사이에 중단되면 재요청이 필요할 수 있으므로,
유료 실행의 정확히 한 번 처리나 비용 상한 금액을 보장하지 않습니다.

## 사람의 검수

형식·크기·디코딩·빈 컷·글리프·배치·원본 답 일치는 기계 검사합니다.
숙어 의미의 정확성, 자연스러운 대사, 모든 컷의 인물·서사, AI가 그린 글자 유무,
어린이 적합성 및 실제 가독성은 사람이 확인해야 합니다. 따라서 자동 완료 처리하지 않습니다.
검수한 결과만 `--approve ID`로 `review_status=approved`, `status=completed`로 변경합니다.
Mock 승인도 mock manifest 안에서만 적용됩니다.

## 향후 실제 API 사용 경로 (이번 단계에서는 실행 금지)

실제 실행에는 `allow_live=true`, `--live`, `--confirm-live`, 양의 `--max-api-calls`, 양의 `--max-cost-usd`,
환경변수 키, 유효한 모델·가격·잠긴 원장이 모두 필요합니다.
`--max-api-calls`는 한 번의 실행에서 대본·이미지·재시도 요청을 합한 하드 제한입니다.
`--max-cost-usd`는 원장 전체의 보수적 예약/계산 비용 한도이며 실제 청구액의 상한은 아닙니다.
SDK 내부 재시도는 0으로 설정하여 중복 재시도 경로를 차단합니다. ID별 기본 요청은 대본 1회와 그림 1회입니다.
API 키는 프로세스 환경의 `OPENAI_API_KEY`만 사용하며 `.env`를 자동으로 읽지 않습니다.
SDK 오류 본문·요청 객체·키·스택 추적은 로그나 manifest에 기록하지 않습니다.
기본 출력은 `assets/idioms`, 체크포인트는 `tools/image-generator/tmp/live-run`입니다.
실제 모델 접근 권한·응답 품질·요금은 이번 offline 검증에서 확인하지 않았습니다.

공식 문서: [Images API](https://developers.openai.com/api/reference/python/resources/images/methods/generate),
[Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
