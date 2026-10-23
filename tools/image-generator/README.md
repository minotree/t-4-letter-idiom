# 이미지 제작 도구

695개 한자숙어의 CSV 검증과 4컷 만화 제작을 위한 Python + Pillow 도구입니다.
대본·그림 API 어댑터와 글자 합성·WebP 변환·작업 관리 엔진을 구현했습니다.
실제 API 호출은 기본 설정에서 차단되며, 현재 검증은 dry-run과 로컬 mock으로만 수행합니다.

ChatGPT Plus에서 사용자가 만든 그림을 가져오는 [오프라인 제작 경로](MANUAL_WORKFLOW.md)를 추가했습니다.
`manual_workflow.py prepare`로 검수 데이터를 준비하고, 검증된 의미·대본이 있는 항목만 프롬프트를 내보냅니다.
API 키가 필요 없으며 기존 API 코드·비용 보호는 별도로 유지합니다.
운영 manifest를 보존하기 위해 오프라인 상태는 `data/manual_workflow/image_manifest.csv`에서 관리합니다.
현재 의미 검수 대기는 695개, 그림 프롬프트는 0개입니다.

## 개발 환경 준비

Python 3.11 이상을 사용합니다. 아래 명령은 저장소 루트에서 PowerShell로 실행합니다.
CSV 검증은 표준 라이브러리만 사용하며 생성 엔진에는 아래 의존성이 필요합니다.

```powershell
python -m venv tools/image-generator/.venv
tools/image-generator/.venv/Scripts/python.exe -m pip install -r tools/image-generator/requirements.txt
```

- 원본 CSV 및 제작 관리 데이터: `data/`
- 최종 WebP 이미지: `assets/idioms/`
- 체크포인트와 mock 이미지·manifest: `tools/image-generator/tmp/`

## 실행 안내

- [원본 CSV 검증](DATA_VALIDATION.md): `validate_data.py`
- [생성 엔진과 비용 보호](ENGINE.md): `generate.py`, `config.toml`, `comic_engine/`
- [ChatGPT 수동 제작·가져오기](MANUAL_WORKFLOW.md): `manual_workflow.py`

현재 이미지 생성 금지 단계에서는 아래의 비이미지 검증만 실행합니다.

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/manual_workflow.py prepare
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/run_no_image_tests.py
```

아래 mock 및 전체 unittest 명령은 임시 이미지를 만들므로 이미지 생성이 허용된 단계에만 사용합니다.

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/generate.py --dry-run
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/generate.py --mock --limit 1
tools/image-generator/.venv/Scripts/python.exe -m unittest discover -s tools/image-generator -p "test_*.py" -v
```

루트 `.env.example`에는 `OPENAI_API_KEY` 이름만 준비되어 있습니다.
실제 키는 버전 관리에 포함하지 않으며 웹 클라이언트에 전달하지 않습니다.
