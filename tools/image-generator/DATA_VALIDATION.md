# 원본 CSV 연결 및 검증

Python 3.11 이상과 표준 라이브러리만 사용합니다. Pillow 설치나 API 키가 필요하지 않습니다.
저장소 루트에서 실행합니다. 기본 경로는 스크립트 위치를 기준으로 하므로 다른 작업 폴더에서도 실행할 수 있습니다.

```powershell
python tools/image-generator/validate_data.py
python -m unittest discover -s tools/image-generator -p "test_*.py" -v
```

- 입력: `data/sajaseongeo_final_quiz_v3.csv` (헤더 없는 한자·독음 2열, UTF-8 또는 UTF-8 BOM)
- 출력: `data/image_manifest.csv` (한글 호환 UTF-8 BOM), `data/validation_report.json` (UTF-8)
- 원본 순서대로 1부터 순번을 부여하고 원본 문자열을 그대로 보존합니다.
- 파일명은 `0001_가가호호.webp` 형식입니다. 독음의 Windows 금지 문자·공백은 `_`로 대체하고 길이를 제한합니다. 실제 이미지 파일은 만들지 않습니다.
- 최초 `status`, `review_status`는 모두 `pending`, `error_message`는 빈 값입니다.
- 기존 manifest의 순번·한자·독음·파일명이 일치하면 파일 전체를 수정 없이 보존합니다. 열 구성, 개수, 고유 순번 또는 데이터가 불일치하면 오류로 중단하고 기존 출력은 보존합니다. 원본 변경 시 자동으로 상태를 재배정하지 않습니다.
- JSON 보고서는 재실행마다 갱신합니다. 원본 SHA-256도 기록합니다.
- 중복은 앞뒤 공백을 제거한 값 기준입니다. 그룹 수, 해당 행 수, 첫 행을 제외한 추가 중복 수와 순번을 각각 보고합니다. 삭제나 병합은 하지 않습니다.
- 모든 공백과 빈 값을 보고합니다. 한자 글자 수는 원본 문자열의 Unicode 코드 포인트 수이며 4글자가 아닌 항목도 모두 보존합니다.
- 데이터 수가 695와 다르거나 빈 값이 있으면 결과 파일을 저장한 뒤 종료 코드 1을 반환합니다. 중복·공백·4글자가 아닌 항목은 보고 대상으로 유지합니다. 파싱 오류나 기존 manifest 불일치는 출력을 변경하기 전에 중단합니다.

다른 파일로 검사하려면 `--source`, `--manifest`, `--report`, `--expected-count`를 지정합니다.
테스트는 임시 디렉터리만 사용하며 실제 manifest의 제작 상태를 변경하지 않습니다.
