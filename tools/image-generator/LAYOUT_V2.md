# 그림 내부 말풍선 미리보기

프로젝트 루트에서 실행합니다. API 키나 API 호출이 필요하지 않습니다.

```powershell
tools/image-generator/.venv/Scripts/python.exe tools/image-generator/preview_layout.py --id 1 --layout tools/image-generator/layouts/0001_v2.json
```

기존 미리보기 또는 보고서가 있으면 덮어쓰지 않고 중단합니다. 원본·운영 결과·manifest·승인 상태를 변경하지 않습니다.

`layout_v2.py`는 공통 합성 코드이며 `layouts/0001_v2.json`은 ID별 배치 제안입니다. 좌표는 각 출력 컷의 좌상단을 원점으로 하는 512×384 좌표입니다. `protected_regions`는 얼굴·손·중요 장면의 사각형 목록, `bubble_candidates`는 말풍선 좌상단 후보, `number_position`은 번호 위치입니다. 마지막 컷에는 `answer_box`, `notice_box`도 필요합니다. 그림은 원본 컷 전체를 contain으로 맞추며 자르거나 늘리지 않습니다.

말풍선 높이는 글꼴 측정과 줄바꿈으로 정합니다. 본체·꼬리·번호·정답·제작 문구는 보호 영역을 피해야 합니다. 보호 영역과 빈 공간의 의미는 자동으로 증명하지 못하므로 새 결과는 항상 `needs_review`입니다. 안전한 후보가 없으면 오류로 중단하며 승인하지 않습니다. 보호 영역에는 건물·축제 장식 등 보존할 요소도 추가할 수 있습니다.

기존 `manual_workflow.py import`는 기존 레이아웃을 계속 사용합니다. 새 레이아웃은 미리보기 전용이며, 운영 적용은 별도 검수 후 진행해야 합니다. 보고서에는 레이아웃 버전 2와 설정·입력·대본 패킷·출력 SHA-256을 저장합니다. 기존 import 체크포인트는 읽거나 재사용하지 않습니다.

가가호호 결과의 얼굴·손·중요 배경 가림, 말풍선 꼬리 방향, 한자·대사 가독성 및 원본 대비 축소를 사람이 확인해야 합니다. 현재 보호 영역은 자동 승인을 의미하지 않는 제안값입니다.
