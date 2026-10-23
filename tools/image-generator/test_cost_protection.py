from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx
from openai import APITimeoutError, RateLimitError

import generate
from comic_engine.api import APIGateway
from comic_engine.common import DEFAULT_CONFIG, EngineError, config_from
from comic_engine.costs import DEFAULT_PRICES, CostBlocked, Prices, money
from comic_engine.ledger import Ledger


class CostProtectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = dict(config_from(), allow_live=True, retry_base_seconds=0)
        self.price_file = self.root / 'prices.json'
        self.price_file.write_bytes(DEFAULT_PRICES.read_bytes())
        self.prices = Prices(self.price_file, today=date(2026, 10, 20))
        self.ledger = Ledger.initialize(self.root / 'ledger.jsonl')
        self.enterContext(patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-secret-not-for-ledger'}))

    def gateway(self, budget='1', max_calls=10, **kwargs):
        if not self.ledger.locked:
            self.enterContext(self.ledger.session())
        params = dict(authorized=True, confirm_live=True, budget=budget, ledger=self.ledger,
                      prices=self.prices, client=SimpleNamespace(), sleep=lambda _: None)
        params.update(kwargs)
        return APIGateway(self.config, max_calls, **params)

    def call(self, gateway, operation=None, identifier='1', kind='script', text='private-prompt-not-for-ledger'):
        model = self.config['script_model' if kind == 'script' else 'image_model']
        payload = {'model': model, 'input': text, 'max_output_tokens': 2200}
        if kind == 'image':
            payload = {'model': model, 'prompt': text, 'quality': 'medium', 'size': '1024x1536', 'n': 1}
        return gateway.call(operation or (lambda _: self.response(kind)), idiom_id=identifier,
                            request_type=kind, model=model, payload=payload)

    def response(self, kind='script'):
        usage = {'input_tokens': 100, 'output_tokens': 100}
        if kind == 'image':
            usage['input_tokens_details'] = {'text_tokens': 100, 'image_tokens': 0}
        return SimpleNamespace(usage=usage, _request_id='req_test')

    def known_failure(self):
        request = httpx.Request('POST', 'https://api.openai.com/v1/responses')
        return RateLimitError('secret-error-body', response=httpx.Response(429, request=request),
                              body={'usage': {'input_tokens': 0, 'output_tokens': 0}})

    def test_insufficient_budget_blocks_before_reservation_and_operation(self):
        gateway = self.gateway('.001')
        operation = Mock()
        with self.assertRaisesRegex(CostBlocked, 'budget exceeded'):
            self.call(gateway, operation)
        operation.assert_not_called()
        self.assertEqual(self.ledger.summary()['request_count'], 0)

    def test_missing_key_blocks_even_injected_client(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            with self.assertRaisesRegex(CostBlocked, 'OPENAI_API_KEY'):
                self.gateway()
        gateway = self.gateway()
        operation = Mock()
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
            with self.assertRaises(CostBlocked):
                self.call(gateway, operation)
        operation.assert_not_called()

    def test_confirm_live_and_each_other_gate_are_mandatory(self):
        for options in ({'authorized': False}, {'confirm_live': False}, {'budget': None},
                        {'budget': 'NaN'}, {'budget': '-1'}, {'ledger': None}, {'prices': None}):
            with self.subTest(options=list(options)):
                with self.assertRaises(EngineError):
                    self.gateway(**options)
        for cap in (None, 0, -1, True):
            with self.assertRaises(EngineError):
                self.gateway(max_calls=cap)
        self.config['allow_live'] = False
        with self.assertRaises(EngineError):
            self.gateway()

    def test_missing_cli_confirm_live_never_constructs_sdk_or_mutates_manifest(self):
        from comic_engine.manifest import save_manifest
        from validate_data import ROOT, load_source
        config_file = self.root / 'config.toml'
        config_file.write_text(DEFAULT_CONFIG.read_text(encoding='utf-8').replace('allow_live = false', 'allow_live = true'), encoding='utf-8')
        rows, _ = load_source(ROOT / 'data/sajaseongeo_final_quiz_v3.csv')
        manifest = self.root / 'manifest.csv'
        save_manifest(manifest, rows)
        before = manifest.read_bytes()
        with patch('openai.OpenAI', side_effect=AssertionError('SDK forbidden')) as constructor, patch('builtins.print'):
            code = generate.main(['--live', '--config', str(config_file), '--manifest', str(manifest),
                                  '--max-api-calls', '6', '--max-cost-usd', '1'])
        self.assertEqual(code, 1)
        constructor.assert_not_called()
        self.assertEqual(before, manifest.read_bytes())

    def test_stale_future_mismatched_or_invalid_prices_block(self):
        original = json.loads(DEFAULT_PRICES.read_text(encoding='utf-8'))
        for stamp in ('2026-01-01', '2026-10-21', 'bad-date'):
            self.price_file.write_text(json.dumps(dict(original, verified_on=stamp)), encoding='utf-8')
            with self.assertRaises(CostBlocked):
                Prices(self.price_file, today=date(2026, 10, 20))
        self.price_file.write_bytes(DEFAULT_PRICES.read_bytes())
        with self.assertRaises(CostBlocked):
            self.prices.validate_models(dict(self.config, image_model='gpt-image-2'))
        changed = json.loads(DEFAULT_PRICES.read_text(encoding='utf-8'))
        changed['models']['gpt-4.1-mini']['input_per_million'] = 'NaN'
        self.price_file.write_text(json.dumps(changed), encoding='utf-8')
        with self.assertRaises(CostBlocked):
            Prices(self.price_file, today=date(2026, 10, 20)).validate_models(self.config)

    def test_unknown_size_quality_cost_and_oversized_input_block(self):
        with self.assertRaises(CostBlocked):
            self.prices.validate_models(dict(self.config, image_quality='high'))
        operation = Mock()
        with self.assertRaises(CostBlocked):
            self.call(self.gateway(), operation, text='가' * 5000)
        operation.assert_not_called()

    def test_timeout_is_uncertain_and_blocks_retry_and_restart(self):
        gateway = self.gateway()
        operation = Mock(side_effect=APITimeoutError(request=httpx.Request('POST', 'https://api.openai.com/v1/responses')))
        with self.assertRaisesRegex(CostBlocked, 'uncertain cost'):
            self.call(gateway, operation)
        self.assertEqual(operation.call_count, 1)
        summary = self.ledger.summary()
        self.assertEqual(summary['uncertain_reserved_usd'], '0.00512')
        with self.assertRaises(CostBlocked):
            self.gateway()

    def test_success_without_usage_keeps_reservation_and_blocks_next_request(self):
        gateway = self.gateway()
        self.call(gateway, lambda _: SimpleNamespace(usage=None))
        with self.assertRaises(CostBlocked):
            self.call(gateway, identifier='2')
        self.assertEqual(gateway.calls, 1)
        self.assertEqual(self.ledger.summary()['success_count'], 1)

    def test_retry_budget_exceeded_after_known_failure(self):
        gateway = self.gateway('.007')
        operation = Mock(side_effect=self.known_failure())
        with self.assertRaisesRegex(CostBlocked, 'budget exceeded'):
            self.call(gateway, operation)
        self.assertEqual(operation.call_count, 1)
        self.assertEqual(self.ledger.summary()['failure_count'], 1)

    def test_known_cost_retries_each_have_separate_reservation_and_id(self):
        gateway = self.gateway('.02')
        operation = Mock(side_effect=[self.known_failure(), self.known_failure(), self.response()])
        self.call(gateway, operation)
        events, requests = self.ledger.read()
        self.assertEqual(len(events), 6)
        self.assertEqual(len(requests), 3)
        self.assertEqual([r['retry_count'] for r in requests.values()], [0, 1, 2])
        self.assertEqual(self.ledger.summary()['reserved_total_usd'], '0.01536')

    def test_script_and_image_share_same_cumulative_budget(self):
        gateway = self.gateway('.26')
        self.call(gateway)
        operation = Mock()
        with self.assertRaises(CostBlocked):
            self.call(gateway, operation, kind='image')
        operation.assert_not_called()

    def test_duplicate_logical_request_is_blocked_after_success(self):
        gateway = self.gateway()
        self.call(gateway)
        operation = Mock()
        with self.assertRaisesRegex(CostBlocked, 'Duplicate logical'):
            self.call(gateway, operation)
        operation.assert_not_called()

    def test_restart_does_not_reset_consumed_budget(self):
        with self.ledger.session():
            reservation = self.ledger.reserve(logical_id='a' * 64, idiom_id='1', model=self.config['script_model'],
                                              kind='script', estimate=money('.8'), budget=money('1'),
                                              retry_count=0, price_date='2026-10-20')
            self.ledger.finish(reservation, usage={'input_tokens': 1, 'output_tokens': 1},
                               actual_cost=money('.2'), outcome='succeeded')
        with Ledger(self.ledger.path).session() as reopened:
            self.assertEqual(reopened.summary()['budget_consumed_usd'], '0.8')
            with self.assertRaises(CostBlocked):
                reopened.ensure_ready(money('1'), money('.3'))

    def test_process_exit_after_reservation_is_not_free(self):
        with self.ledger.session():
            self.ledger.reserve(logical_id='a' * 64, idiom_id='1', model='model', kind='script',
                                estimate=money('.1'), budget=money('1'), retry_count=0, price_date='2026-10-20')
        with Ledger(self.ledger.path).session() as reopened:
            with self.assertRaises(CostBlocked):
                reopened.ensure_ready(money('1'))
            self.assertEqual(reopened.summary()['uncertain_reserved_usd'], '0.1')

    def test_duplicate_request_id_is_rejected(self):
        with self.ledger.session():
            args = dict(logical_id='b' * 64, idiom_id='1', model='model', kind='script', estimate=money('.1'),
                        budget=money('1'), retry_count=0, price_date='2026-10-20')
            reserved = self.ledger.reserve(**args)
            self.ledger.finish(reserved, usage={}, actual_cost=money(0), outcome='failed')
            with self.assertRaises(CostBlocked):
                self.ledger.reserve(**args)

    def test_real_second_process_cannot_consume_same_ledger(self):
        code = ('import sys; sys.path.insert(0,sys.argv[1]); from comic_engine.ledger import Ledger; '
                'ctx=Ledger(sys.argv[2]).session(); ctx.__enter__()')
        with self.ledger.session():
            child = subprocess.run([sys.executable, '-c', code, str(DEFAULT_CONFIG.parent), str(self.ledger.path)],
                                   capture_output=True, timeout=10)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn(b'manifest lock', child.stderr)

    def test_truncated_json_and_missing_ledger_never_auto_reset(self):
        self.ledger.path.write_bytes(b'{"partial":')
        with self.assertRaises(CostBlocked):
            with self.ledger.session():
                pass
        self.ledger.path.unlink()
        with self.assertRaises(CostBlocked):
            with self.ledger.session():
                pass
        with self.assertRaises(CostBlocked):
            Ledger.initialize(self.ledger.path)

    def test_head_mismatch_after_interrupted_atomic_save_blocks(self):
        with self.ledger.session():
            with patch('comic_engine.ledger.atomic_json', side_effect=OSError('simulated crash')):
                with self.assertRaises(OSError):
                    self.ledger.reserve(logical_id='c' * 64, idiom_id='1', model='model', kind='script',
                                        estimate=money('.1'), budget=money('1'), retry_count=0, price_date='2026-10-20')
        with self.assertRaises(CostBlocked):
            with self.ledger.session():
                pass

    def test_hash_edit_and_tail_deletion_are_detected(self):
        gateway = self.gateway()
        self.call(gateway)
        before = self.ledger.path.read_bytes()
        self.ledger.path.write_bytes(before.replace(b'"idiom_id": "1"', b'"idiom_id": "9"', 1))
        with self.assertRaises(CostBlocked):
            self.ledger.read()
        self.ledger.path.write_bytes(before.splitlines(keepends=True)[0])
        with self.assertRaises(CostBlocked):
            self.ledger.read()

    def test_cost_report_is_offline_and_does_not_change_ledger(self):
        before = self.ledger.path.read_bytes()
        with patch('generate.Ledger', return_value=self.ledger), patch('openai.OpenAI', side_effect=AssertionError('API forbidden')), patch('builtins.print') as output:
            result = generate.main(['--cost-report', '--limit', '3', '--max-cost-usd', '2.40'])
        self.assertEqual(result, 0)
        report = json.loads(output.call_args.args[0])
        self.assertEqual(report['selected_estimated_cost_usd'], '0.79536')
        self.assertEqual(report['selected_max_attempts_estimate_usd'], '2.38608')
        self.assertEqual(before, self.ledger.path.read_bytes())
        self.price_file.write_text('{}', encoding='utf-8')
        with patch('generate.Ledger', return_value=self.ledger), patch('builtins.print') as output:
            result = generate.main(['--cost-report', '--prices', str(self.price_file)])
        self.assertEqual(result, 1)
        report = json.loads(output.call_args.args[0])
        self.assertFalse(report['prices_valid'])
        self.assertEqual(report['request_count'], 0)

    def test_mock_routes_without_sdk_or_usage_ledger(self):
        with (patch('comic_engine.api.APIGateway', side_effect=AssertionError('API forbidden')) as gateway,
             patch('generate.Ledger', side_effect=AssertionError('Production ledger forbidden')),
             patch('generate.process_rows', return_value={'failed': 0, 'needs_review': 0}) as pipeline,
             patch('builtins.print')):
            result = generate.main(['--mock', '--sandbox', str(self.root / 'sandbox')])
        self.assertEqual(result, 0)
        gateway.assert_not_called()
        self.assertTrue(pipeline.call_args.kwargs['mock'])

    def test_ledger_excludes_keys_prompts_and_error_bodies(self):
        gateway = self.gateway()
        operation = Mock(side_effect=self.known_failure())
        with self.assertRaises(EngineError):
            self.call(gateway, operation)
        raw = self.ledger.path.read_text(encoding='utf-8')
        for secret in ('fake-secret-not-for-ledger', 'private-prompt-not-for-ledger', 'secret-error-body'):
            self.assertNotIn(secret, raw)

    def test_manual_resolution_retains_original_reservation_and_audit_trail(self):
        gateway = self.gateway()
        self.call(gateway, lambda _: SimpleNamespace(usage=None))
        identifier = self.ledger.summary()['uncertain_request_ids'][0]
        self.ledger.resolve(identifier, '0', 'billing-dashboard')
        self.ledger.ensure_ready(money(1))
        self.assertEqual(self.ledger.summary()['budget_consumed_usd'], '0.00512')
        self.assertEqual(len(self.ledger.read()[0]), 3)

    def test_usage_costs_text_cache_and_image_breakdown(self):
        self.assertEqual(self.prices.actual(self.config['script_model'], 'script',
                         {'input_tokens': 1000, 'output_tokens': 1000, 'input_tokens_details': {'cached_tokens': 500}}), money('.00185'))
        self.assertEqual(self.prices.actual(self.config['image_model'], 'image',
                         {'input_tokens': 1000, 'output_tokens': 2000, 'input_tokens_details': {'text_tokens': 1000, 'image_tokens': 0}}), money('.065'))
        with self.assertRaises(CostBlocked):
            self.prices.actual(self.config['image_model'], 'image', {'input_tokens': 1000, 'output_tokens': 2000})

    def test_changed_price_file_blocks_request_before_sending(self):
        gateway = self.gateway()
        self.price_file.write_text('{}', encoding='utf-8')
        operation = Mock()
        with self.assertRaises(CostBlocked):
            self.call(gateway, operation)
        operation.assert_not_called()

    def test_actual_cost_over_reservation_is_not_hidden_by_budget(self):
        gateway = self.gateway('.01')
        self.call(gateway, lambda _: SimpleNamespace(usage={'input_tokens': 1000000, 'output_tokens': 1000000}))
        self.assertEqual(self.ledger.summary()['budget_consumed_usd'], '2.00')
        with self.assertRaises(CostBlocked):
            self.call(gateway, identifier='2')


if __name__ == '__main__':
    unittest.main()
