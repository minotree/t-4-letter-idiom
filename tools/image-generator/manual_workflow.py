"""ChatGPT manual workflow: local metadata and Pillow only; never invokes image generation."""
import argparse
import json
from pathlib import Path

from comic_engine.common import ROOT, EngineError, config_from
from comic_engine.manual import DEFAULT_WORKSPACE, FileStore, PillowProcessor, approve_item, import_item, prepare, sha
from comic_engine.manifest import read_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'inspect-import', 'import', 'approve', 'approve-v2', 'status'])
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--layout', type=Path)
    parser.add_argument('--id')
    parser.add_argument('--source', type=Path, default=ROOT / 'data/sajaseongeo_final_quiz_v3.csv')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/image_manifest.csv')
    parser.add_argument('--workspace', type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument('--imports', type=Path, default=ROOT / 'assets/imports')
    parser.add_argument('--output', type=Path, default=ROOT / 'assets/idioms')
    parser.add_argument('--reviewer')
    parser.add_argument('--confirm-review', action='store_true')
    args = parser.parse_args(argv)
    try:
        config = config_from()
        protected = {args.source.resolve(), args.manifest.resolve()}
        workspace, imports, output = args.workspace.resolve(), args.imports.resolve(), args.output.resolve()
        if (workspace / 'image_manifest.csv').resolve() in protected:
            raise EngineError('Manual manifest must be separate from original inputs')
        for first, second in ((workspace, imports), (workspace, output), (imports, output)):
            if first == second or first in second.parents or second in first.parents:
                raise EngineError('Workspace, imports and output must be separate directories')
        if args.command == 'approve-v2':
            if not args.id or not args.preview or not args.layout:
                raise EngineError('V2 approval requires --id, --preview and --layout')
            from comic_engine.approval_v2 import approve_v2
            result = approve_v2(workspace,args.manifest,args.source,args.id,imports,output,
                                args.preview,args.layout,config,args.reviewer,confirm=args.confirm_review)
            print(json.dumps(result,ensure_ascii=True))
            return 0
        rows = read_manifest(args.manifest, args.source)
        if args.command == 'prepare':
            report = prepare(workspace, rows)
            print(json.dumps({key: value for key, value in report.items() if key != 'items'}))
            return 0
        if args.command == 'status':
            local = read_manifest(workspace / 'image_manifest.csv', args.source)
            print(json.dumps({state: sum(row['status'] == state for row in local)
                              for state in ('pending', 'generating', 'needs_review', 'completed', 'failed')}))
            return 0
        row = next((row for row in rows if row['id'] == args.id), None)
        if row is None:
            raise EngineError('A valid --id is required')
        if args.command == 'inspect-import':
            path = imports / f'{int(args.id):04d}.png'
            raw = FileStore().read(path)
            size = PillowProcessor(config).inspect(raw)
            print(json.dumps({'id': args.id, 'dimensions': size, 'artwork_sha256': sha(raw)}))
            return 0
        if args.command == 'approve':
            if not args.confirm_review:
                raise EngineError('Human review requires --confirm-review and --reviewer')
            result = approve_item(workspace, rows, args.source, args.id, imports, output, config, args.reviewer)
        else:
            result = import_item(workspace, rows, args.source, args.id, imports, output, config)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except Exception as exc:
        print('Error: ' + (str(exc) if isinstance(exc, EngineError) else type(exc).__name__ + ': local workflow failure'))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
