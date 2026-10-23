"""Offline-safe CLI for comic planning, mock rendering and future opt-in production."""
import argparse
import json
from pathlib import Path

from comic_engine.common import DEFAULT_CONFIG, ROOT, EngineError, atomic_json, config_from
from comic_engine.fonts import Fonts
from comic_engine.manifest import manifest_lock, read_manifest, save_manifest
from comic_engine.pipeline import approve, process_rows, select_rows
from comic_engine.costs import DEFAULT_PRICES, Prices, CostBlocked, money
from comic_engine.ledger import Ledger


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--dry-run', action='store_true', help='Read-only plan; no clients, keys, files or API calls')
    modes.add_argument('--mock', action='store_true', help='Local fixtures in an isolated sandbox directory')
    modes.add_argument('--live', action='store_true', help='Future paid mode; disabled in default config')
    modes.add_argument('--cost-report', action='store_true', help='Read cumulative costs without any API call or image')
    modes.add_argument('--resolve-request', help='Manually reconcile an uncertain request after billing verification')
    parser.add_argument('--confirm-live', action='store_true')
    parser.add_argument('--max-cost-usd', help='Cumulative estimated/reserved USD budget, not a billing limit')
    parser.add_argument('--prices', type=Path, default=DEFAULT_PRICES)
    parser.add_argument('--confirm-resolution', action='store_true')
    parser.add_argument('--resolved-cost-usd')
    parser.add_argument('--resolution-source', choices=['billing-dashboard', 'provider-support'])
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--source', type=Path, default=ROOT / 'data/sajaseongeo_final_quiz_v3.csv')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/image_manifest.csv')
    parser.add_argument('--sandbox', type=Path, default=ROOT / 'tools/image-generator/tmp/mock-run')
    parser.add_argument('--output', type=Path, help='Live output only; mock always uses sandbox/assets')
    parser.add_argument('--work', type=Path, help='Live checkpoints only; mock always uses sandbox/work')
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--ids', help='Comma-separated unique source IDs')
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--resume-layout', action='store_true', help='Resume only sheets waiting for verified panel boundaries')
    parser.add_argument('--max-api-calls', type=int, help='Hard cap shared by script, image and retry attempts')
    parser.add_argument('--check-fonts', action='store_true', help='Read-only coverage check for entire manifest')
    parser.add_argument('--font-report', type=Path, help='Optional report output; forbidden in dry-run')
    parser.add_argument('--approve', help='Human-reviewed ID to mark completed; never calls APIs')
    args = parser.parse_args(argv)
    try:
        if args.limit < 1:
            raise EngineError('--limit must be positive')
        if args.font_report and (args.dry_run or not args.check_fonts):
            raise EngineError('--font-report requires --check-fonts without --dry-run')
        config = config_from(args.config)
        budget = money(args.max_cost_usd, positive=True) if args.max_cost_usd is not None else None
        rows = read_manifest(args.manifest, args.source)
        ids = set(args.ids.split(',')) if args.ids else None
        if ids is not None and not ids <= {row['id'] for row in rows}:
            raise EngineError('Unknown ID in --ids')
        if args.resolve_request:
            if not args.confirm_resolution or args.resolved_cost_usd is None or args.resolution_source is None:
                raise CostBlocked('Resolution needs --confirm-resolution, --resolved-cost-usd and --resolution-source')
            with Ledger().session() as ledger:
                ledger.resolve(args.resolve_request, args.resolved_cost_usd, args.resolution_source)
                print(json.dumps(ledger.summary(budget)))
            return 0
        if args.cost_report:
            with Ledger().session() as ledger:
                report = ledger.summary(budget)
            try:
                estimates = Prices(args.prices).validate_models(config)
            except CostBlocked as exc:
                report.update(prices_valid=False, total_estimated_cost_usd=None,
                              estimate_error=str(exc), api_calls=0)
                print(json.dumps(report))
                return 1
            selected = select_rows(rows, args.limit, ids, args.retry_failed, args.resume_layout)
            pair = sum(estimates.values())
            report.update(total_items=len(rows), script_reservation_usd=str(estimates['script']),
                          prices_valid=True,
                          image_reservation_usd=str(estimates['image']),
                          total_estimated_cost_usd=str(pair * len(rows)),
                          selected_estimated_cost_usd=str(pair * len(selected)),
                          selected_max_attempts_estimate_usd=str(pair * len(selected) * config['max_attempts']),
                          estimate_basis='Configured conservative token reservations; not actual billing caps',
                          api_calls=0)
            print(json.dumps(report))
            return 0
        fonts = Fonts(config)
        coverage = fonts.check_manifest(rows)
        if args.check_fonts:
            if args.font_report:
                protected = {args.source.resolve(), args.manifest.resolve(), args.config.resolve()}
                if args.font_report.resolve() in protected or args.font_report.exists():
                    raise EngineError('Font report would overwrite an existing/protected file')
                atomic_json(args.font_report, coverage)
            print(json.dumps(coverage, ensure_ascii=True))
            return 0
        selected = select_rows(rows, args.limit, ids, args.retry_failed, args.resume_layout)
        if args.dry_run or (not args.mock and not args.live):
            if args.approve:
                raise EngineError('--approve requires --mock or --live, and cannot use --dry-run')
            print(json.dumps({
                'mode': 'dry-run', 'total': len(rows), 'selected_ids': [row['id'] for row in selected],
                'skipped_completed': sum(row['status'] == 'completed' for row in rows),
                'skipped_needs_review': sum(row['status'] == 'needs_review' for row in rows),
                'script_model': config['script_model'], 'image_model': config['image_model'],
                'image_quality': config['image_quality'], 'api_calls': 0,
                'maximum_uncached_requests_before_retries': len(selected) * 2,
                'live_enabled_in_config': config['allow_live'],
            }, ensure_ascii=True))
            return 0
        if args.mock:
            if args.output or args.work:
                raise EngineError('Mock output/work are fixed beneath --sandbox')
            sandbox = args.sandbox.resolve()
            # Never allow mock files under production assets or data.
            if any(sandbox == parent or parent in sandbox.parents
                   for parent in ((ROOT / 'data').resolve(), (ROOT / 'assets').resolve())):
                raise EngineError('Mock sandbox cannot be inside production data/assets')
            manifest = sandbox / 'image_manifest.csv'
            output, work = sandbox / 'assets', sandbox / 'work'
            if manifest.resolve() in (args.source.resolve(), args.manifest.resolve()):
                raise EngineError('Mock manifest must be separate from production inputs')
            with manifest_lock(manifest):
                if not manifest.exists():
                    save_manifest(manifest, rows)
                mock_rows = read_manifest(manifest, args.source)
                if args.approve:
                    approve(mock_rows, args.approve, manifest, output, work, config, mock=True)
                    print(json.dumps({'mock_approved_id': args.approve}))
                    return 0
                selected = select_rows(mock_rows, args.limit, ids, args.retry_failed, args.resume_layout)
                counts = process_rows(mock_rows, selected, manifest, output, work, config, fonts,
                                      mock=True, resume_layout=args.resume_layout)
                print(json.dumps(dict(mode='mock', api_calls=0, **counts)))
                return 1 if counts['failed'] else 0
        # No live client is ever constructed before these authorization gates.
        if config['allow_live'] is not True:
            raise EngineError('Live API is disabled in config.toml')
        output = args.output or ROOT / 'assets/idioms'
        work = args.work or ROOT / 'tools/image-generator/tmp/live-run'
        protected = {args.manifest.resolve(), args.source.resolve(), args.config.resolve()}
        if output.resolve() == work.resolve() or output.resolve() in protected or work.resolve() in protected:
            raise EngineError('Invalid live output/checkpoint paths')
        with manifest_lock(args.manifest):
            rows = read_manifest(args.manifest, args.source)
            if args.approve:
                approve(rows, args.approve, args.manifest, output, work, config, mock=False, source=args.source)
                print(json.dumps({'approved_id': args.approve}))
                return 0
            selected = select_rows(rows, args.limit, ids, args.retry_failed, args.resume_layout)
            if not selected:
                print(json.dumps({'selected': 0, 'api_calls': 0}))
                return 0
            from comic_engine.api import APIGateway
            with Ledger().session() as ledger:
                gateway = APIGateway(config, args.max_api_calls, authorized=args.live,
                                     confirm_live=args.confirm_live, budget=budget,
                                     ledger=ledger, prices=Prices(args.prices))
                counts = process_rows(rows, selected, args.manifest, output, work, config, fonts,
                                      mock=False, gateway=gateway, resume_layout=args.resume_layout)
                print(json.dumps(dict(mode='live', api_calls=gateway.calls, **counts)))
            return 1 if counts['failed'] else 0
    except KeyboardInterrupt:
        print('Interrupted; generating items can resume from checkpoints.')
        return 130
    except Exception as exc:
        from comic_engine.pipeline import safe_error
        print('Error: ' + safe_error(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
