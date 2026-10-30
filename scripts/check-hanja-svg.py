"""Validate the downloaded pilot SVGs and build an isolated local preview."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / 'data/hanja-research/pilot/svg-local'
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8-sig'))
ns = {'s': 'http://www.w3.org/2000/svg'}
results = []
for entry in manifest['files']:
    if not entry['path'].endswith('.svg'):
        continue
    name = Path(entry['path']).name
    raw = (root / name).read_bytes()
    tree = ET.fromstring(raw)
    number = int(Path(name).stem)
    paths = tree.findall('.//s:path', ns)
    outlines = [p for p in paths if p.get('id')]
    animated = [p for p in paths if p.get('clip-path')]
    ids = [node.get('id') for node in tree.iter() if node.get('id')]
    delays = [float(p.get('style').split('--d:')[1].split('s')[0]) for p in animated]
    checks = {
        'sha256MatchesManifest': hashlib.sha256(raw).hexdigest().upper() == entry['sha256'],
        'svgRoot': tree.tag == '{http://www.w3.org/2000/svg}svg',
        'characterId': tree.get('id') == f'z{number}',
        'uniqueIds': len(ids) == len(set(ids)),
        'nonEmptyPaths': all(p.get('d', '').strip() for p in paths),
        'sequentialStrokeIds': [p.get('id') for p in outlines] == [f'z{number}d{i+1}' for i in range(len(outlines))],
        'matchingStrokeCounts': len(outlines) == len(animated) > 0,
        'increasingDelays': all(a < b for a, b in zip(delays, delays[1:])),
        'clipReferencesResolve': all(p.get('clip-path', '')[5:-1] in ids for p in animated),
        'noScriptsOrForeignObjects': not any(node.tag.split('}')[-1] in ('script', 'foreignObject') for node in tree.iter()),
        'noExternalReferences': not any(value.startswith(('http:', 'https:', '//', 'javascript:')) for node in tree.iter() for key, value in node.attrib.items() if key.split('}')[-1] == 'href'),
    }
    results.append({'character': chr(number), 'file': name, 'outlineCount': len(outlines), 'animatedPathCount': len(animated), 'delaysSeconds': delays, 'checks': checks, 'passed': all(checks.values()), 'koreanLearningStandardCompared': False})
(root / 'structure-results.json').write_text(json.dumps({'commit': manifest['commit'], 'results': results}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
cards = '\n'.join(f'<article><h2>{r["character"]} <small>{r["animatedPathCount"]}개 획 경로</small></h2><object aria-label="{r["character"]} 획순 후보" type="image/svg+xml" data="{r["file"]}"></object></article>' for r in results)
html = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>한자 획순 후보 검사</title>
<style>body{font-family:system-ui;margin:24px;background:#f5f7f4;color:#183c30}main{display:flex;flex-wrap:wrap;gap:16px}article{background:white;border:1px solid #ccd5cf;border-radius:12px;padding:16px}object{width:240px;height:240px}small{font-size:14px}button{padding:10px;margin:0 8px 16px 0}</style>
<h1>한자 획순 후보 미리보기</h1><p>구조·재생 검사 전용. 한국 학습 기준과의 일치 여부는 미검증입니다.</p>
<button onclick="control('running')">재생</button><button onclick="control('paused')">일시정지</button><button onclick="location.reload()">다시 보기</button><main>''' + cards + '''</main><p>원본: AnimCJK / Arphic Public License. <a href="COPYING.txt">출처 고지</a> · <a href="ARPHICPL.TXT">라이선스 전문</a></p>
<script>function control(state){document.querySelectorAll('object').forEach(o=>o.contentDocument?.querySelectorAll('path[clip-path]').forEach(p=>p.style.animationPlayState=state))}</script></html>'''
(root / 'preview.html').write_text(html, encoding='utf-8')
print(json.dumps(results, ensure_ascii=True, indent=2))
if not all(r['passed'] for r in results):
    raise SystemExit(1)
