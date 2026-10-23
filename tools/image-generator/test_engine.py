import base64
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from functools import partial
from datetime import date
from unittest.mock import Mock, patch

import httpx
from openai import APITimeoutError, AuthenticationError, InternalServerError, RateLimitError
from PIL import Image

import generate
from comic_engine.api import APIGateway
from comic_engine.artwork import ArtworkGenerator, MockArtworkGenerator, artwork_prompt
from comic_engine.common import ROOT, EngineError, atomic_bytes, config_from
from comic_engine.fonts import CheckedFont, Fonts
from comic_engine.manifest import manifest_lock, read_manifest, save_manifest
from comic_engine.pipeline import approve, process_rows, select_rows
from comic_engine.render import compose, encode_webp, preflight, validate_webp
from comic_engine.story import MockStoryGenerator, StoryGenerator, validate_story
from validate_data import load_source
from comic_engine.costs import Prices, CostBlocked
from comic_engine.ledger import Ledger


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = config_from()
        cls.fonts = Fonts(cls.config)
        cls.source_rows, _ = load_source(ROOT / 'data/sajaseongeo_final_quiz_v3.csv')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest, self.work, self.output = self.root / 'manifest.csv', self.root / 'work', self.root / 'assets'
        self.rows = copy.deepcopy(self.source_rows)
        save_manifest(self.manifest, self.rows)
        # Any accidental real network call fails the test, regardless of an environment key.
        self.enterContext(patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden in tests')))

    def process(self, rows=None, **kwargs):
        return process_rows(self.rows, rows or [self.rows[0]], self.manifest, self.output,
                            self.work, self.config, self.fonts, mock=True, **kwargs)

    def gateway(self, max_calls=10, client=None):
        config = dict(self.config, allow_live=True, retry_base_seconds=0)
        self.gateway_count = getattr(self, 'gateway_count', 0) + 1
        ledger = Ledger.initialize(self.root / f'ledger-{self.gateway_count}.jsonl')
        self.enterContext(ledger.session())
        self.enterContext(patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-test-key'}))
        gateway = APIGateway(config, max_calls, authorized=True, confirm_live=True, budget='10',
                             ledger=ledger, prices=Prices(today=date(2026, 10, 20)),
                             client=client or SimpleNamespace(), sleep=lambda _: None)
        gateway.call = partial(gateway.call, idiom_id='1', request_type='script', model=config['script_model'],
                               payload={'model': config['script_model'], 'input': 'unit test', 'max_output_tokens': 2200})
        return gateway

    def test_all_source_glyphs_and_all_hangul_supported(self):
        report = self.fonts.check_manifest(self.rows)
        self.assertEqual(report['row_count'], 695)
        self.assertEqual(report['unique_source_characters'], 1066)
        self.assertEqual(report['missing_hanja'], [])
        self.assertEqual(report['missing_korean'], [])

    def test_missing_font_and_glyph_are_errors(self):
        with self.assertRaises(EngineError):
            CheckedFont({'path': str(self.root / 'absent.ttf'), 'index': 0})
        with self.assertRaisesRegex(EngineError, 'U\\+10FFFF'):
            self.fonts.hanja.require(chr(0x10FFFF))

    def test_dry_run_is_read_only_and_never_constructs_client(self):
        before = self.manifest.read_bytes()
        with patch('openai.OpenAI', side_effect=AssertionError('Client forbidden')), patch('builtins.print'):
            self.assertEqual(generate.main(['--dry-run', '--manifest', str(self.manifest), '--limit', '695']), 0)
        self.assertEqual(before, self.manifest.read_bytes())
        self.assertEqual(list(self.root.iterdir()), [self.manifest])

    def test_no_mode_defaults_to_dry_run(self):
        with patch('openai.OpenAI', side_effect=AssertionError('Client forbidden')), patch('builtins.print'):
            self.assertEqual(generate.main(['--manifest', str(self.manifest)]), 0)

    def test_live_is_disabled_before_client_or_manifest_mutation(self):
        before = self.manifest.read_bytes()
        with patch('openai.OpenAI', side_effect=AssertionError('Client forbidden')), patch('builtins.print'):
            self.assertEqual(generate.main(['--live', '--manifest', str(self.manifest), '--max-api-calls', '2']), 1)
        self.assertEqual(before, self.manifest.read_bytes())
        with self.assertRaises(EngineError):
            APIGateway(self.config, 5, authorized=True, client=SimpleNamespace())
        with self.assertRaises(EngineError):
            APIGateway(dict(self.config, allow_live=True), 5, client=SimpleNamespace())
        for count in (None, 0, -1):
            with self.assertRaises(EngineError):
                self.gateway(count)

    def test_mock_isolates_manifest_and_output_without_client(self):
        before = self.manifest.read_bytes()
        sandbox = self.root / 'mock'
        with patch('openai.OpenAI', side_effect=AssertionError('Client forbidden')), patch('builtins.print'):
            result = generate.main(['--mock', '--manifest', str(self.manifest), '--sandbox', str(sandbox)])
        self.assertEqual(result, 0)
        self.assertEqual(before, self.manifest.read_bytes())
        self.assertTrue((sandbox / 'assets' / self.rows[0]['filename']).exists())
        self.assertEqual(read_manifest(sandbox / 'image_manifest.csv', ROOT / 'data/sajaseongeo_final_quiz_v3.csv')[0]['status'], 'needs_review')

    def test_mock_rejects_production_sandbox_and_override(self):
        with patch('builtins.print'):
            self.assertEqual(generate.main(['--mock', '--sandbox', str(ROOT / 'data')]), 1)
            self.assertEqual(generate.main(['--mock', '--output', str(self.output)]), 1)

    def test_selection_skips_completed_review_and_failed_by_default(self):
        for row, status in zip(self.rows[:5], ['completed', 'needs_review', 'failed', 'generating', 'pending']):
            row['status'] = status
        self.assertEqual([row['id'] for row in select_rows(self.rows, 2)], ['4', '5'])
        self.assertEqual([row['id'] for row in select_rows(self.rows, 1, retry_failed=True)], ['3'])
        self.assertEqual([row['id'] for row in select_rows(self.rows, 2, {'5'})], ['5'])

    def test_mock_pipeline_composition_unicode_states_and_approval(self):
        before = (ROOT / 'data/sajaseongeo_final_quiz_v3.csv').read_bytes()
        chosen = [self.rows[index] for index in (0, 252, 683, 690)]
        counts = self.process(chosen)
        self.assertEqual(counts, {'needs_review': 4, 'failed': 0})
        for row in chosen:
            raw = (self.output / row['filename']).read_bytes()
            validate_webp(raw)
            metadata = json.loads((self.work / f'{int(row["id"]):04d}' / 'result.json').read_text(encoding='utf-8'))
            answers = [entry for entry in metadata['overlays'] if entry.get('role') == 'answer']
            self.assertEqual(answers[0]['text'], row['hanja'])
            self.assertGreaterEqual(answers[0]['font_size'], 28)
            fourth_texts = [entry['text'] for entry in metadata['overlays'] if entry['box'][1] >= 1152]
            self.assertFalse(any(row['reading'] in text for text in fourth_texts))
            self.assertIn('AI가 제작한 이미지입니다', fourth_texts)
            self.assertEqual(metadata['sha256'], hashlib.sha256(raw).hexdigest())
        approve(self.rows, '1', self.manifest, self.output, self.work, self.config, mock=True)
        self.assertEqual(self.rows[0]['status'], 'completed')
        self.assertEqual(self.rows[0]['review_status'], 'approved')
        self.assertNotIn('1', [row['id'] for row in select_rows(self.rows, 695)])
        self.assertEqual(before, (ROOT / 'data/sajaseongeo_final_quiz_v3.csv').read_bytes())

    def test_review_rejects_modified_output(self):
        self.process()
        (self.output / self.rows[0]['filename']).write_bytes(b'corrupt')
        with self.assertRaises(EngineError):
            approve(self.rows, '1', self.manifest, self.output, self.work, self.config, mock=True)
        self.assertEqual(self.rows[0]['status'], 'needs_review')

    def test_interruption_and_resume_reuses_story_checkpoint(self):
        story_generator = Mock(wraps=MockStoryGenerator())
        art = Mock()
        art.generate.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.process(story_generator=story_generator, artwork_generator=art)
        self.assertEqual(self.rows[0]['status'], 'generating')
        self.assertEqual(story_generator.generate.call_count, 1)
        blocked_story = Mock()
        blocked_story.generate.side_effect = AssertionError('Story should not be regenerated')
        self.assertEqual(self.process(story_generator=blocked_story)['needs_review'], 1)
        blocked_story.generate.assert_not_called()

    def test_crash_after_publish_recovers_without_generation(self):
        self.process()
        before = (self.output / self.rows[0]['filename']).read_bytes()
        self.rows[0]['status'] = 'generating'
        blocked = Mock()
        blocked.generate.side_effect = AssertionError('Generation forbidden on resume')
        self.assertEqual(self.process(story_generator=blocked, artwork_generator=blocked)['needs_review'], 1)
        self.assertEqual((self.output / self.rows[0]['filename']).read_bytes(), before)
        blocked.generate.assert_not_called()

    def test_failure_reason_is_redacted_and_retry_is_explicit(self):
        bad = Mock()
        bad.generate.side_effect = RuntimeError('sk-secret-must-not-leak')
        self.assertEqual(self.process(story_generator=bad)['failed'], 1)
        self.assertEqual(self.rows[0]['status'], 'failed')
        self.assertNotIn('sk-secret', self.rows[0]['error_message'])
        self.assertNotIn('1', [row['id'] for row in select_rows(self.rows, 695)])
        self.assertEqual(self.process()['needs_review'], 1)

    def test_config_changed_checkpoint_fails_without_overwriting_output(self):
        self.process()
        target = self.output / self.rows[0]['filename']
        before = target.read_bytes()
        config = dict(self.config, image_quality='high')
        counts = process_rows(self.rows, [self.rows[0]], self.manifest, self.output, self.work,
                              config, self.fonts, mock=True)
        self.assertEqual(counts['failed'], 1)
        self.assertEqual(target.read_bytes(), before)

    def test_existing_untracked_file_is_not_overwritten(self):
        target = self.output / self.rows[0]['filename']
        atomic_bytes(target, b'previous-file')
        self.assertEqual(self.process()['failed'], 1)
        self.assertEqual(target.read_bytes(), b'previous-file')

    def test_corrupt_source_identity_and_filename_rejected(self):
        for key, value in [('hanja', '修改'), ('filename', '../bad.webp'), ('id', '2'), ('status', 'unknown')]:
            rows = copy.deepcopy(self.source_rows)
            rows[0][key] = value
            save_manifest(self.manifest, rows)
            with self.assertRaises(EngineError):
                read_manifest(self.manifest, ROOT / 'data/sajaseongeo_final_quiz_v3.csv')

    def test_process_lock_releases_and_blocks_second_writer(self):
        with manifest_lock(self.manifest):
            with self.assertRaises(EngineError):
                with manifest_lock(self.manifest):
                    self.fail('Second writer acquired the lock')
        with manifest_lock(self.manifest):
            pass

    def test_timeout_cost_unknown_blocks_automatic_retry(self):
        request = httpx.Request('POST', 'https://api.openai.com/v1/images/generations')
        response = httpx.Response(429, request=request)
        failures = [APITimeoutError(request=request), RateLimitError('secret body', response=response, body=None)]
        operation = Mock(side_effect=failures + ['ok'])
        gateway = self.gateway(3)
        with self.assertRaisesRegex(CostBlocked, 'uncertain cost'):
            gateway.call(operation)
        self.assertEqual(gateway.calls, 1)
        self.assertEqual(operation.call_count, 1)

    def test_budget_includes_retry_and_is_shared_between_operations(self):
        gateway = self.gateway(2)
        usage = {'input_tokens': 0, 'output_tokens': 0}
        response = SimpleNamespace(usage=usage)
        self.assertIs(gateway.call(lambda _: response), response)
        request = httpx.Request('POST', 'https://api.openai.com/v1/images/generations')
        response_429 = httpx.Response(429, request=request)
        operation = Mock(side_effect=RateLimitError('private', response=response_429, body={'usage': usage}))
        with self.assertRaisesRegex(EngineError, 'budget exhausted'):
            gateway.call(operation, payload={'model': self.config['script_model'], 'input': 'different request', 'max_output_tokens': 2200})
        self.assertEqual(operation.call_count, 1)
        self.assertEqual(gateway.calls, 2)

    def test_authentication_errors_not_retried_or_leaked(self):
        request = httpx.Request('POST', 'https://api.openai.com/v1/responses')
        response = httpx.Response(401, request=request)
        operation = Mock(side_effect=AuthenticationError('sk-secret', response=response, body=None))
        with self.assertRaises(EngineError) as error:
            self.gateway().call(operation)
        self.assertNotIn('sk-secret', str(error.exception))
        self.assertEqual(operation.call_count, 1)

    def test_server_errors_stop_at_configured_attempt_limit(self):
        request = httpx.Request('POST', 'https://api.openai.com/v1/images/generations')
        response = httpx.Response(500, request=request)
        operation = Mock(side_effect=InternalServerError('private', response=response,
                                                       body={'usage': {'input_tokens': 0, 'output_tokens': 0}}))
        with self.assertRaisesRegex(EngineError, 'HTTP 500'):
            self.gateway(10).call(operation)
        self.assertEqual(operation.call_count, self.config['max_attempts'])

    def test_untracked_output_with_identity_prevents_paid_generation(self):
        # Simulate an unexpected output file after identity checkpoint creation.
        art = Mock()
        art.generate.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.process(artwork_generator=art)
        target = self.output / self.rows[0]['filename']
        atomic_bytes(target, b'foreign-file')
        blocked = Mock()
        blocked.generate.side_effect = AssertionError('Must fail before generation')
        self.assertEqual(self.process(artwork_generator=blocked)['failed'], 1)
        blocked.generate.assert_not_called()
        self.assertEqual(target.read_bytes(), b'foreign-file')

    def test_sdk_initialization_uses_env_disables_sdk_retries(self):
        ledger = Ledger.initialize(self.root / 'sdk-ledger.jsonl')
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'fake-test-key'}), patch('openai.OpenAI') as constructor:
            with ledger.session():
                APIGateway(dict(self.config, allow_live=True), 2, authorized=True, confirm_live=True,
                           budget='1', ledger=ledger, prices=Prices(today=date(2026, 10, 20)))
        self.assertEqual(constructor.call_args.kwargs['api_key'], 'fake-test-key')
        self.assertEqual(constructor.call_args.kwargs['max_retries'], 0)
        self.assertEqual(constructor.call_args.kwargs['base_url'], 'https://api.openai.com/v1')

    def test_official_sdk_adapters_with_fake_client_only(self):
        row = self.rows[0]
        story = MockStoryGenerator().generate(row)
        buffer = io.BytesIO()
        Image.new('RGB', (1024, 1536)).save(buffer, format='PNG')
        client = SimpleNamespace(responses=SimpleNamespace(create=Mock(return_value=SimpleNamespace(output_text=json.dumps(story), usage={'input_tokens': 100, 'output_tokens': 100}))),
                                 images=SimpleNamespace(generate=Mock(return_value=SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(buffer.getvalue()).decode())], usage={'input_tokens': 100, 'output_tokens': 100, 'input_tokens_details': {'text_tokens': 100, 'image_tokens': 0}}))))
        gateway = self.gateway(2, client)
        self.assertEqual(StoryGenerator(self.config, gateway).generate(row), story)
        self.assertEqual(ArtworkGenerator(self.config, gateway).generate(story, idiom_id='1').size, (1024, 1536))
        self.assertEqual(gateway.calls, 2)
        self.assertEqual(client.images.generate.call_args.kwargs['n'], 1)
        self.assertEqual(client.responses.create.call_args.kwargs['text']['format']['type'], 'json_schema')
        self.assertNotIn(row['hanja'], artwork_prompt(story))
        self.assertNotIn(row['reading'], artwork_prompt(story))

    def test_malformed_story_or_final_reading_is_rejected(self):
        story = MockStoryGenerator().generate(self.rows[0])
        for broken in ({'meaning': 'x', 'panels': []},
                       dict(story, panels=[{'scene': 'scene', 'dialogue': 'english'}] * 4)):
            with self.assertRaises(EngineError):
                validate_story(broken, self.rows[0])
        story['panels'][3]['dialogue'] = self.rows[0]['reading'] + '의 뜻을 알겠어!'
        with self.assertRaises(EngineError):
            validate_story(story, self.rows[0])

    def test_scene_cannot_leak_hanja_or_korean_to_image_api(self):
        for text in (self.rows[0]['hanja'], self.rows[0]['reading'], '文字'):
            story = MockStoryGenerator().generate(self.rows[0])
            story['panels'][0]['scene'] += ' The answer is ' + text
            with self.assertRaisesRegex(EngineError, 'refusing to send'):
                validate_story(story, self.rows[0])

    def test_overflow_and_generated_missing_glyph_prevent_art_call(self):
        for line in ('가' * 47, '함께' + chr(0x10FFFF)):
            story = MockStoryGenerator().generate(self.rows[0])
            story['panels'][0]['dialogue'] = line
            provider = Mock()
            provider.generate.return_value = story
            art = Mock()
            self.work = self.root / ('work' + str(len(line)))
            self.assertEqual(self.process(story_generator=provider, artwork_generator=art)['failed'], 1)
            art.generate.assert_not_called()

    def test_blank_panel_and_invalid_webp_are_errors(self):
        story = MockStoryGenerator().generate(self.rows[0])
        with self.assertRaises(EngineError):
            compose(Image.new('RGB', (512, 1536)), story, self.rows[0], self.fonts)
        with self.assertRaises(EngineError):
            validate_webp(b'not an image')
        buffer = io.BytesIO()
        Image.new('RGB', (512, 512)).save(buffer, format='WEBP')
        with self.assertRaises(EngineError):
            validate_webp(buffer.getvalue())

    def test_size_target_never_forces_unreadable_quality(self):
        story = MockStoryGenerator().generate(self.rows[0])
        image, _ = compose(MockArtworkGenerator().generate(story), story, self.rows[0], self.fonts, mock=True)
        raw, result = encode_webp(image, dict(self.config, target_max_bytes=1))
        self.assertFalse(result['within_target'])
        self.assertEqual(result['quality'], self.config['minimum_quality'])
        validate_webp(raw)


if __name__ == '__main__':
    unittest.main()
