"""Create-only local preview; never imports, approves, or calls an API."""
import argparse
import json
from pathlib import Path
from PIL import Image
from comic_engine.common import ROOT, config_from, EngineError
from comic_engine.fonts import Fonts
from comic_engine.manual import FileStore, packed, sha, production_packet, read_catalog, verify_overlays
from comic_engine.manifest import read_manifest
from comic_engine.layout import verified_regions
from comic_engine.layout_v2 import compose_preview
from comic_engine.render import encode_webp


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True)
    parser.add_argument('--layout',type=Path,required=True)
    parser.add_argument('--preview-name', help='Create-only WebP filename within assets/previews')
    args=parser.parse_args()
    config=config_from()
    if config['allow_live']:
        raise EngineError('Preview requires allow_live=false')
    rows=read_manifest(ROOT/'data/image_manifest.csv',ROOT/'data/sajaseongeo_final_quiz_v3.csv')
    row=next(r for r in rows if r['id']==args.id)
    catalog=read_catalog(ROOT/'data/manual_workflow/catalog.json',rows)
    packet,prompt=production_packet(catalog['items'][int(args.id)-1],row)
    revision=sha(packed(packet))
    exported=ROOT/'data/manual_workflow/prompts'/f'{int(args.id):04d}'/revision
    if (exported/'production.json').read_bytes()!=packed(packet) or (exported/'image_prompt.txt').read_bytes()!=prompt.encode('utf-8'):
        raise EngineError('Prompt packet mismatch')
    path=ROOT/'assets/imports'/f'{int(args.id):04d}.png'
    raw=path.read_bytes()
    side=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if (any(side[k]!=row[k] for k in ('id','hanja','reading')) or side['identity_confirmed'] is not True
            or not side['reviewer'].strip() or side['image_prompt_sha256']!=packet['image_prompt_sha256']):
        raise EngineError('Input approval mismatch')
    settings=json.loads(args.layout.read_text(encoding='utf-8'))
    if settings['id']!=row['id']:
        raise EngineError('Layout ID mismatch')
    from comic_engine.manual import PillowProcessor
    dimensions=object.__new__(PillowProcessor).inspect(raw)
    regions=verified_regions(*dimensions,side,sha(raw))
    destination=ROOT/'assets/previews'/f'{int(args.id):04d}_layout_v2.webp'
    if args.preview_name:
        if Path(args.preview_name).name != args.preview_name or not args.preview_name.endswith('.webp') or any(c in args.preview_name for c in '/\\:'):
            raise EngineError('Invalid preview filename')
        destination=destination.with_name(args.preview_name)
    report_path=destination.with_suffix('.json')
    if destination.exists() or report_path.exists():
        raise EngineError('Preview already exists; refusing overwrite')
    with Image.open(path) as artwork:
        canvas,report=compose_preview(artwork,packet['story'],row,Fonts(config),regions,settings)
    verify_overlays(report['overlays'],row,packet['story'],layout_settings=settings)
    encoded,compression=encode_webp(canvas,config)
    report.update(compression=compression,dimensions=[512,1536],id=row['id'],input_sha256=sha(raw),
                  layout_sha256=sha(packed(settings)),packet_sha256=revision,output_sha256=sha(encoded))
    FileStore().put(report_path,packed(report))
    FileStore().put(destination,encoded)
    print(json.dumps({'output':str(destination),'bytes':len(encoded),'state':'needs_review'}))


if __name__=='__main__':
    main()
