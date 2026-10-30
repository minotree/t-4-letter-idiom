# 羲·暉 지역별 획순 후보 (2026-10-30)

- AnimCJK 커밋 `36d0007b05a22377392738f0fa2d0a067d03d788`에서 일본 暉·일본 羲·중국 간체 폴더 羲 원본을 다운로드했다. `manifest.json`에 정확한 원본 URL·SHA-256을 기록했다. 해당 파일들은 같은 코드포인트이나 한국 학습용 자형과 필순이 일치한다는 뜻은 아니다.
- XML 파싱, 다운로드 해시, 외곽과 애니메이션 경로 수, 애니메이션 지연 증가를 로컬 Python으로 확인: 暉 일본 13/13, 羲 일본 16/16, 羲 중국 16/16. 羲 일본·중국의 SVG 애니메이션 경로 문자열은 서로 달랐다. `structure-results.json` 참조. 차이가 획의 순서인지 좌표·서체 차이인지는 아직 판단하지 못했다.
- 원본 파일의 공통 저작권 고지와 라이선스 전문은 `../svg-local/COPYING.txt`, `../svg-local/ARPHICPL.TXT`에 보관했다. SVG는 변형하지 않았다. 앱 배포 조건과 한국식 필순은 별도 검토가 필요하다.
- 조사용 미리보기 실행: 저장소 루트에서 `python -m http.server 4187 --bind 127.0.0.1 --directory data/hanja-research/pilot` 실행 후 `http://127.0.0.1:4187/svg-regional-comparison/preview.html` 접속. 세 글자가 한 획씩 재생된다. 사용자 시제품·학습 앱에는 연결하지 않았다.
- 전용 Chromium에서 `node scripts/check-hanja-regional-preview.mjs` 실행: 세 SVG 로딩, 각 경로 수, 첫 획 애니메이션 진행 통과. 전체 획 완료와 재생 제어·오프라인은 이 검사에 포함하지 않았다.
- 한국 기준 자료·한 획씩의 정확한 방향·오프라인·기기 검증은 미실행이다.
