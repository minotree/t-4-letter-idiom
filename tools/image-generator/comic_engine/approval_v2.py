"""Offline V2 approval with a recoverable three-file publication transaction."""
import base64
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile

from .common import EngineError, atomic_bytes, atomic_json
from .manual import (FileStore, packed, sha, read_catalog, production_packet,
                     PillowProcessor, verify_overlays, seoul_today)
from .manifest import manifest_lock, read_manifest, save_manifest
from .layout import verified_regions
from .layout_v2 import VERSION, RENDER_REVISION
from .render import validate_webp
from .source_images import record_approved_image


def validate_v2(workspace, rows, identifier, imports, output, preview, layout):
    row = next((r for r in rows if r['id'] == identifier), None)
    if row is None:
        raise EngineError('Unknown V2 approval ID')
    catalog = read_catalog(Path(workspace)/'catalog.json', rows)
    packet, prompt = production_packet(catalog['items'][int(identifier)-1], row)
    report = json.loads(Path(preview).with_suffix('.json').read_text(encoding='utf-8'))
    settings = json.loads(Path(layout).read_text(encoding='utf-8'))
    if (report.get('layout_version') != VERSION or settings.get('layout_version') != VERSION
            or report.get('render_revision') != RENDER_REVISION
            or report.get('id') != identifier or settings.get('id') != identifier
            or report.get('layout_sha256') != sha(packed(settings))
            or report.get('packet_sha256') != sha(packed(packet))):
        raise EngineError('V2 report/layout/packet mismatch; V1 checkpoints are not supported')
    exported = Path(workspace)/'prompts'/f'{int(identifier):04d}'/sha(packed(packet))
    if ((exported/'production.json').read_bytes() != packed(packet)
            or (exported/'image_prompt.txt').read_bytes() != prompt.encode('utf-8')):
        raise EngineError('Exported packet changed')
    png = Path(imports)/f'{int(identifier):04d}.png'
    raw = png.read_bytes()
    side = json.loads(png.with_suffix('.json').read_text(encoding='utf-8'))
    if (any(side.get(k) != row[k] for k in ('id','hanja','reading'))
            or side.get('identity_confirmed') is not True or side.get('verified') is not True
            or not isinstance(side.get('reviewer'), str) or not side['reviewer'].strip()
            or side.get('image_prompt_sha256') != packet['image_prompt_sha256']
            or side.get('artwork_sha256') != sha(raw) or report.get('input_sha256') != sha(raw)):
        raise EngineError('Original image/approval mismatch')
    dimensions = object.__new__(PillowProcessor).inspect(raw)
    regions = verified_regions(*dimensions, side, sha(raw))
    placements = report.get('placements', [])
    if len(placements) != 4 or any(p.get('panel') != i or p.get('source_region') != list(regions[i])
                                   for i,p in enumerate(placements)):
        raise EngineError('V2 source panel boundaries mismatch')
    verify_overlays(report['overlays'], row, packet['story'], layout_settings=settings)
    image = Path(preview).read_bytes()
    final = (Path(output)/row['filename']).read_bytes()
    validate_webp(image)
    validate_webp(final)
    if (image != final or sha(image) != report.get('output_sha256')
            or report.get('dimensions') != [512,1536]
            or report.get('compression',{}).get('bytes') != len(image)):
        raise EngineError('Final image differs from approved V2 preview')
    return row, {'output_sha256':sha(final), 'report_sha256':sha(Path(preview).with_suffix('.json').read_bytes()),
                 'layout_sha256':sha(packed(settings)), 'input_sha256':sha(raw),
                 'packet_sha256':sha(packed(packet)), 'layout_version':VERSION,'render_revision':RENDER_REVISION}


def recover(journal, paths):
    if not journal.exists():
        return
    transaction = json.loads(journal.read_text(encoding='utf-8'))
    if transaction['state'] in ('committed','rolled_back'):
        return
    entries = transaction['files']
    if [e['path'] for e in entries] != [str(p.resolve()) for p in paths]:
        raise EngineError('V2 recovery paths differ')
    decoded = [(base64.b64decode(e['before'], validate=True), base64.b64decode(e['after'], validate=True)) for e in entries]
    for path,(before,after) in zip(paths,decoded):
        if path.read_bytes() not in (before,after):
            raise EngineError('V2 recovery found external changes; manual recovery required')
    for path,(before,after) in zip(paths,decoded):
        atomic_bytes(path,before)
    transaction['state'] = 'rolled_back'
    atomic_json(journal, transaction)


def approve_v2(workspace, operational, source, identifier, imports, output, preview, layout,
               config, reviewer, *, confirm=False):
    if not confirm or not isinstance(reviewer,str) or not reviewer.strip():
        raise EngineError('V2 approval requires --confirm-review and --reviewer')
    if config['allow_live']:
        raise EngineError('V2 approval requires allow_live=false')
    workspace, operational, source = Path(workspace), Path(operational), Path(source)
    local = workspace/'image_manifest.csv'
    paths = [source, local, operational]
    if len({p.resolve() for p in paths}) != 3:
        raise EngineError('V2 transaction paths must be distinct')
    journal = workspace/'v2_approval_transaction.json'
    with ExitStack() as locks:
        for path in sorted(paths,key=lambda p:str(p.resolve()).casefold()):
            locks.enter_context(manifest_lock(path))
        recover(journal, paths)
        rows = read_manifest(operational,source)
        local_rows = read_manifest(local,source)
        row, evidence = validate_v2(workspace,rows,identifier,imports,output,preview,layout)
        local_row = next(r for r in local_rows if r['id']==identifier)
        original_operational_status = row['status']
        approval_path = workspace/'approvals_v2'/f'{int(identifier):04d}'/(evidence['output_sha256']+'.json')
        if local_row['status'] not in ('needs_review','completed'):
            raise EngineError('V2 approval requires manual needs_review state')
        if row['status'] not in ('pending','needs_review','completed'):
            raise EngineError('Operational item is not ready for V2 publication')
        if approval_path.exists():
            previous = json.loads(approval_path.read_text(encoding='utf-8'))
            if previous['evidence'] != evidence:
                raise EngineError('Existing V2 approval differs')
        # Staging is isolated: no production manifest or CSV is changed here.
        before = [p.read_bytes() for p in paths]
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory)
            csv_path = staged/'source.csv'
            csv_path.write_bytes(before[0])
            approved = dict(row,status='completed',review_status='approved',error_message='')
            record_approved_image(csv_path,approved,output,evidence['output_sha256'])
            # Synchronize via needs_review before final approval; no generating shortcut.
            row.update(status='needs_review',review_status='pending',error_message='')
            for item in (row,local_row):
                item.update(status='completed',review_status='approved',error_message='')
            save_manifest(staged/'local.csv',local_rows)
            save_manifest(staged/'operational.csv',rows)
            after = [csv_path.read_bytes(),(staged/'local.csv').read_bytes(),(staged/'operational.csv').read_bytes()]
        if before == after and approval_path.exists():
            return {'id':identifier,'state':'completed','skipped':True}
        transaction = {'state':'prepared','id':identifier,'evidence':evidence,
                       'transitions':{'manual':['needs_review','completed'],
                                      'operational':[original_operational_status,'needs_review','completed']},'files':[
            {'path':str(path.resolve()),'before':base64.b64encode(b).decode(),
             'after':base64.b64encode(a).decode()} for path,b,a in zip(paths,before,after)]}
        atomic_json(journal,transaction)
        FileStore().put(source.with_name(source.name+'.'+sha(before[0])+'.bak'),before[0])
        try:
            for path,content in zip(paths,after):
                atomic_bytes(path,content)
            if not approval_path.exists():
                FileStore().put(approval_path,packed({'id':identifier,'reviewer':reviewer,
                    'reviewed_on':seoul_today().isoformat(),'evidence':evidence,'workflow':'manual-v2'}))
            transaction['state']='committed'
            atomic_json(journal,transaction)
        except BaseException:
            recover(journal,paths)
            raise
        return {'id':identifier,'state':'completed','csv_recorded':True}
