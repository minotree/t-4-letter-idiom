"""No-raster tests use byte labels and in-memory stores, not encoded images."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from comic_engine.common import EngineError, NOTICE, NUMBERS, ROOT, config_from
from comic_engine.manual import (FileStore, PillowProcessor, approve_item, approved_story, import_item,
                                 packed, prepare, production_packet, read_catalog, seoul_today, sha, verify_overlays)
from comic_engine.manifest import read_manifest
from comic_engine.story import MockStoryGenerator
from validate_data import load_source
import manual_workflow


class PillowInspectionTests(unittest.TestCase):
    def inspect_with(self, metadata, verification_error=None):
        processor = object.__new__(PillowProcessor)
        untouched = MagicMock()
        untouched.__enter__.return_value = untouched
        untouched.verify.side_effect = verification_error
        metadata.__enter__.return_value = metadata
        with patch('comic_engine.manual.Image.open', side_effect=[untouched, metadata]) as opened:
            result = processor.inspect(b'opaque-image-label')
        self.assertEqual(opened.call_count, 2)
        untouched.verify.assert_called_once_with()
        untouched.getexif.assert_not_called()
        metadata.verify.assert_not_called()
        return result

    def metadata(self, **overrides):
        image = MagicMock()
        image.format, image.n_frames = 'PNG', 1
        image.size, image.width, image.height = (724, 2172), 724, 2172
        image.getexif.return_value = {}
        for key, value in overrides.items():
            setattr(image, key, value)
        return image

    def test_verification_precedes_metadata_on_separate_objects(self):
        image = self.metadata()
        # Emulate PNG getexif invalidating verify on the metadata object.
        image.getexif.side_effect = lambda: setattr(image.verify, 'side_effect',
            RuntimeError('verify must be called directly after open')) or {}
        self.assertEqual(self.inspect_with(image), (724, 2172))

    def test_existing_metadata_rejections_remain(self):
        for fields in ({'format': 'JPEG'}, {'format': 'WEBP'}, {'format': 'GIF'},
                       {'n_frames': 2}, {'size': (511, 2172)},
                       {'width': 4000, 'height': 4000}):
            with self.subTest(fields=fields), self.assertRaises(EngineError):
                self.inspect_with(self.metadata(**fields))
        image = self.metadata()
        image.getexif.return_value = {274: 6}
        with self.assertRaises(EngineError):
            self.inspect_with(image)

    def test_corrupt_input_stops_before_metadata_open(self):
        first = self.metadata()
        first.__enter__.return_value = first
        first.verify.side_effect = SyntaxError('broken PNG checksum')
        with patch('comic_engine.manual.Image.open', return_value=first) as opened:
            with self.assertRaisesRegex(SyntaxError, 'broken PNG checksum'):
                object.__new__(PillowProcessor).inspect(b'corrupt-label')
        self.assertEqual(opened.call_count, 1)
        first.getexif.assert_not_called()

    def test_oversize_input_is_rejected_before_open(self):
        with patch('comic_engine.manual.Image.open') as opened:
            with self.assertRaisesRegex(EngineError, '30 MB'):
                object.__new__(PillowProcessor).inspect(b'x' * 30_000_001)
        opened.assert_not_called()


class LayoutV2Tests(unittest.TestCase):
    def test_answer_ink_width_and_center_with_font_bearing(self):
        from comic_engine.layout_v2 import centered_answer
        checked = MagicMock()
        checked.at.return_value.getbbox.return_value = (3, 1, 128, 34)
        result = centered_answer('家家戶戶', checked, [150,100,370,150])
        self.assertEqual(result['surface'][2]-result['surface'][0], 125+24)
        self.assertEqual(sum(result['surface'][::2])/2, 256)
        self.assertEqual((result['box'][0]+result['box'][2])/2, 256)
        self.assertEqual(result['box'][0]-result['surface'][0], 12)
        self.assertEqual(result['surface'][2]-result['box'][2], 12)
        self.assertEqual(result['draw_position'][0]+3,result['box'][0])

    def test_answer_does_not_shrink_below_28(self):
        from comic_engine.layout_v2 import centered_answer
        checked = MagicMock()
        checked.at.return_value.getbbox.return_value = (0,0,600,32)
        with self.assertRaises(EngineError):
            centered_answer('長答案', checked, [0,100,512,150])
        self.assertEqual([call.args[0] for call in checked.at.call_args_list], [32,31,30,29,28])

    def setUp(self):
        self.row = {'hanja': '家家戶戶'}
        self.story = {'panels': [{'dialogue': '대사' + str(i)} for i in range(4)]}
        self.settings = {'layout_version': 2, 'panels': [
            {'protected_regions': [[300, 150, 450, 300]]} for _ in range(4)]}
        self.overlays = []
        for i in range(4):
            self.overlays.extend([
                {'panel': i, 'role': 'number', 'text': NUMBERS[i], 'font_size': 28,
                 'box': [14, 13, 46, 46], 'surface': [10, 10, 50, 50]},
                {'panel': i, 'role': 'dialogue', 'text': self.story['panels'][i]['dialogue'],
                 'font_size': 20, 'box': [110, 20, 250, 60],
                 'surface': [100, 10, 260, 70], 'tail_box': [120, 70, 140, 80]}])
        self.overlays.extend([
            {'panel': 3, 'role': 'answer', 'text': '家家戶戶', 'font_size': 32,
             'box': [110, 104, 250, 140], 'surface': [100, 100, 260, 145]},
            {'panel': 3, 'role': 'notice', 'text': NOTICE, 'font_size': 17,
             'box': [70, 358, 445, 377], 'surface': [62, 354, 453, 381]}])

    def check(self):
        verify_overlays(self.overlays, self.row, self.story, layout_settings=self.settings)

    def test_valid_inside_artwork_layout(self):
        self.check()

    def test_body_and_tail_protected_collisions(self):
        for box in ([105, 15, 120, 25], [125, 74, 135, 79]):
            with self.subTest(box=box):
                self.settings['panels'][0]['protected_regions'] = [box]
                with self.assertRaisesRegex(EngineError, 'protected region'):
                    self.check()

    def test_text_must_fit_bubble_and_panel(self):
        for box in ([90, 20, 250, 60], [110, 20, 250, 400]):
            with self.subTest(box=box):
                self.overlays[1]['box'] = box
                with self.assertRaises(EngineError):
                    self.check()

    def test_exact_answer_and_minimum_dialogue_size(self):
        self.overlays[-2]['text'] = '家家户户'
        with self.assertRaises(EngineError):
            self.check()
        self.overlays[-2]['text'] = '家家戶戶'
        self.overlays[1]['font_size'] = 19
        with self.assertRaises(EngineError):
            self.check()

    def test_layout_version_and_source_splits(self):
        from comic_engine.layout import verified_regions
        regions = verified_regions(724, 2172, {'verified': True, 'artwork_sha256': 'test',
                                   'cut_lines': [0, 541, 1072, 1548, 2172]}, 'test')
        self.assertEqual([b[3]-b[1] for b in regions], [541, 531, 476, 624])
        self.assertEqual(sum(b[3]-b[1] for b in regions), 2172)
        self.settings['layout_version'] = 1
        with self.assertRaises(EngineError):
            self.check()


class MemoryStore(FileStore):
    def __init__(self):
        self.data = {}

    def key(self, path):
        return str(Path(path).resolve())

    def exists(self, path):
        return self.key(path) in self.data or Path(path).is_file()

    def read(self, path):
        if self.key(path) in self.data:
            return self.data[self.key(path)]
        return Path(path).read_bytes()

    def put(self, path, data):
        if self.exists(path) and self.read(path) != data:
            raise EngineError('Existing artifact differs; refusing to overwrite')
        self.data[self.key(path)] = data


class MetadataOnlyProcessor:
    def __init__(self):
        self.render_count = 0
        self.bad_answer = False
        self.overlap = False

    def inspect(self, raw):
        if raw != b'opaque-input-label':
            raise EngineError('Unexpected test input label')
        return (1024, 1536)

    def render(self, raw, story, row, regions):
        self.render_count += 1
        overlays = []
        for index, panel in enumerate(story['panels']):
            top = index * 384
            overlays.extend([{'text': NUMBERS[index], 'box': [10, top + 24, 53, top + 65], 'font_size': 32},
                             {'text': panel['dialogue'], 'box': [76, top + 23, 482, top + 99], 'font_size': 22}])
        overlays.extend([{'text': '錯誤' if self.bad_answer else row['hanja'], 'box': [100, 1464, 400, 1508], 'font_size': 32, 'role': 'answer'},
                         {'text': NOTICE, 'box': [115, 1514, 500, 1534], 'font_size': 17}])
        if self.overlap:
            overlays[1]['box'] = [76, 120, 482, 180]
        return b'opaque-output-label', {'overlays': overlays, 'dimensions': [512, 1536], 'format': 'WEBP',
                                       'compression': {'within_target': False, 'bytes': 0, 'quality': 100}}

    def validate(self, raw):
        if raw != b'opaque-output-label':
            raise EngineError('Modified test output label')


class ManualWorkflowTests(unittest.TestCase):
    def setUp(self):
        # Metadata-only workflow fixtures do not contain real WebP files.
        recorder = patch('comic_engine.source_images.record_approved_image')
        self.record_approved = recorder.start()
        self.addCleanup(recorder.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / 'source.csv'
        with self.source.open('w', encoding='utf-8-sig', newline='') as stream:
            csv.writer(stream).writerows([['家家戶戶', '가가호호'], ['一石二鳥', '일석이조']])
        self.rows, _ = load_source(self.source)
        self.workspace, self.imports, self.output = (self.root / name for name in ('manual', 'imports', 'output'))
        self.config = config_from()
        prepare(self.workspace, self.rows)
        self.store = MemoryStore()
        self.processor = MetadataOnlyProcessor()

    def ready(self):
        path = self.workspace / 'catalog.json'
        catalog = read_catalog(path, self.rows)
        entry = catalog['items'][0]
        # Explicitly fictitious test evidence. Never written to production data.
        entry.update(meaning_status='verified', meaning='테스트용 정의이며 실제 사전 정보가 아닙니다.',
                     meaning_sources=['TEST FIXTURE ONLY'], meaning_reviewer='Test reviewer',
                     meaning_reviewed_on=seoul_today().isoformat(), story_status='verified',
                     story_reviewer='Test reviewer', story_reviewed_on=seoul_today().isoformat())
        entry['story'] = MockStoryGenerator().generate(self.rows[0])
        entry['story']['meaning'] = entry['meaning']
        path.write_bytes(packed(catalog))
        report = prepare(self.workspace, self.rows)
        self.assertEqual(report['ready'], 1)
        packet, _ = production_packet(entry, self.rows[0])
        raw = b'opaque-input-label'
        metadata = {'id': '1', 'hanja': self.rows[0]['hanja'], 'reading': self.rows[0]['reading'],
                    'identity_confirmed': True, 'reviewer': 'Test reviewer', 'verified': True,
                    'artwork_sha256': sha(raw), 'image_prompt_sha256': packet['image_prompt_sha256'],
                    'cut_lines': [0, 384, 768, 1152, 1536]}
        self.store.put(self.imports / '0001.png', raw)
        self.store.put(self.imports / '0001.json', packed(metadata))
        return entry, metadata

    def run_import(self):
        return import_item(self.workspace, self.rows, self.source, '1', self.imports, self.output,
                           self.config, store=self.store, processor=self.processor)

    def approve(self):
        return approve_item(self.workspace, self.rows, self.source, '1', self.imports, self.output,
                            self.config, 'Human reviewer', store=self.store, processor=self.processor)

    def local(self):
        return read_manifest(self.workspace / 'image_manifest.csv', self.source)[0]

    def test_all_695_without_meanings_are_retained_and_prompts_blocked(self):
        rows, _ = load_source(ROOT / 'data/sajaseongeo_final_quiz_v3.csv')
        report = prepare(self.root / 'full-catalog', rows)
        self.assertEqual((report['total'], report['meaning_pending'], report['ready']), (695, 695, 0))
        self.assertEqual(len(read_catalog(self.root / 'full-catalog/catalog.json', rows)['items']), 695)
        self.assertFalse(list((self.root / 'full-catalog').rglob('image_prompt.txt')))

    def test_prepare_is_idempotent_and_preserves_editorial_work(self):
        self.ready()
        before = (self.workspace / 'catalog.json').read_bytes()
        prepare(self.workspace, self.rows)
        self.assertEqual((self.workspace / 'catalog.json').read_bytes(), before)

    def test_verified_meaning_requires_source_reviewer_and_date(self):
        entry, _ = self.ready()
        for changes in ({'meaning_sources': []}, {'meaning_reviewer': ''}, {'meaning_reviewed_on': '2999-01-01'}, {'meaning': ''}):
            with self.assertRaises(EngineError):
                approved_story(dict(entry, **changes), self.rows[0])

    def test_verified_meaning_without_story_waits_without_guessing(self):
        entry, _ = self.ready()
        with self.assertRaisesRegex(EngineError, 'story_pending'):
            approved_story(dict(entry, story_status='pending'), self.rows[0])

    def test_story_meaning_must_equal_approved_meaning(self):
        entry, _ = self.ready()
        entry['story']['meaning'] = '다른 설명'
        with self.assertRaises(EngineError):
            approved_story(entry, self.rows[0])

    def test_packet_contains_required_data_but_art_prompt_excludes_answers(self):
        entry, _ = self.ready()
        packet, prompt = production_packet(entry, self.rows[0])
        for key in ('id', 'hanja', 'reading', 'meaning', 'story'):
            self.assertIn(key, packet)
        self.assertEqual(len(packet['story']['panels']), 4)
        for secret in (packet['hanja'], packet['reading'], packet['story']['panels'][0]['dialogue']):
            self.assertNotIn(secret, prompt)
        self.assertIn('No writing', prompt)
        self.assertIn('no speech bubbles', prompt)

    def test_catalog_source_identity_cannot_be_changed(self):
        path = self.workspace / 'catalog.json'
        catalog = read_catalog(path, self.rows)
        catalog['items'][0]['hanja'] = '修改'
        path.write_bytes(packed(catalog))
        with self.assertRaises(EngineError):
            prepare(self.workspace, self.rows)

    def test_import_and_human_approval_use_only_separate_manifest(self):
        self.ready()
        source_before = self.source.read_bytes()
        result = self.run_import()
        self.assertEqual(result['state'], 'needs_review')
        self.assertEqual(self.local()['status'], 'needs_review')
        self.assertEqual(self.approve()['state'], 'completed')
        self.assertEqual(self.local()['review_status'], 'approved')
        self.assertEqual(self.source.read_bytes(), source_before)
        self.assertEqual(self.rows[0]['status'], 'pending')
        self.assertFalse(list(self.root.rglob('*.webp')))

    def test_no_api_key_or_api_client_needed_for_prepare(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': ''}), patch('openai.OpenAI', side_effect=AssertionError('API forbidden')), patch('builtins.print'):
            result = manual_workflow.main(['prepare', '--workspace', str(self.root / 'cli'), '--source', str(self.source),
                                          '--manifest', str(self.workspace / 'image_manifest.csv')])
        self.assertEqual(result, 0)

    def test_unknown_import_id_rejected(self):
        with self.assertRaises(EngineError):
            import_item(self.workspace, self.rows, self.source, '9', self.imports, self.output,
                        self.config, store=self.store, processor=self.processor)

    def test_meaning_pending_cannot_be_imported(self):
        with self.assertRaisesRegex(EngineError, 'meaning_pending'):
            self.run_import()
        self.assertEqual(self.local()['status'], 'failed')

    def test_wrong_id_reading_or_hanja_confirmation_rejected(self):
        _, metadata = self.ready()
        for key, value in (('id', '2'), ('hanja', '別字'), ('reading', '다른독음'), ('identity_confirmed', False)):
            self.store.data[self.store.key(self.imports / '0001.json')] = packed(dict(metadata, **{key: value}))
            with self.assertRaisesRegex(EngineError, 'identity'):
                self.run_import()
        self.assertIn('identity', self.local()['error_message'])

    def test_unverified_cuts_or_wrong_hash_are_rejected(self):
        _, metadata = self.ready()
        for changes in ({'verified': False}, {'artwork_sha256': 'wrong'}, {'cut_lines': [0, 0, 768, 1152, 1536]}):
            self.store.data[self.store.key(self.imports / '0001.json')] = packed(dict(metadata, **changes))
            with self.assertRaises(EngineError):
                self.run_import()

    def test_stale_prompt_confirmation_rejected(self):
        _, metadata = self.ready()
        metadata['image_prompt_sha256'] = 'wrong'
        self.store.data[self.store.key(self.imports / '0001.json')] = packed(metadata)
        with self.assertRaises(EngineError):
            self.run_import()

    def test_approval_requires_needs_review(self):
        self.ready()
        with self.assertRaises(EngineError):
            self.approve()

    def test_completed_items_are_skipped_without_overwrite(self):
        self.ready()
        self.run_import()
        self.approve()
        before = copy.deepcopy(self.store.data)
        self.assertTrue(self.run_import()['skipped'])
        self.assertEqual(before, self.store.data)

    def test_output_tampering_blocks_approval_and_records_reason(self):
        self.ready()
        self.run_import()
        self.store.data[self.store.key(self.output / self.rows[0]['filename'])] = b'modified-label'
        with self.assertRaises(EngineError):
            self.approve()
        self.assertEqual(self.local()['status'], 'needs_review')
        self.assertTrue(self.local()['error_message'])

    def test_reimport_reuses_checkpoint_without_rendering_again(self):
        self.ready()
        self.run_import()
        self.run_import()
        self.assertEqual(self.processor.render_count, 1)

    def test_crash_after_checkpoint_resumes_without_rendering_again(self):
        self.ready()
        original_put = self.store.put
        target = self.output / self.rows[0]['filename']
        def interrupted(path, data):
            if Path(path) == target:
                raise KeyboardInterrupt()
            original_put(path, data)
        with patch.object(self.store, 'put', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.run_import()
        self.assertEqual(self.local()['status'], 'generating')
        self.assertEqual(self.run_import()['state'], 'needs_review')
        self.assertEqual(self.processor.render_count, 1)

    def test_untracked_output_is_not_overwritten(self):
        self.ready()
        target = self.output / self.rows[0]['filename']
        self.store.put(target, b'pre-existing-label')
        with self.assertRaises(EngineError):
            self.run_import()
        self.assertEqual(self.store.read(target), b'pre-existing-label')

    def test_wrong_answer_or_overlapping_overlay_prevents_publishing(self):
        self.ready()
        self.processor.bad_answer = True
        with self.assertRaises(EngineError):
            self.run_import()
        self.processor.bad_answer, self.processor.overlap = False, True
        with self.assertRaises(EngineError):
            self.run_import()
        self.assertFalse(self.store.exists(self.output / self.rows[0]['filename']))

    def test_atomic_file_store_does_not_replace_existing_text_file(self):
        path = self.root / 'text-fixture.txt'
        FileStore().put(path, b'original')
        FileStore().put(path, b'original')
        with self.assertRaises(EngineError):
            FileStore().put(path, b'changed')
        self.assertEqual(path.read_bytes(), b'original')

    def test_cli_rejects_operational_manifest_as_manual_workspace(self):
        with patch('builtins.print'):
            self.assertEqual(manual_workflow.main(['prepare', '--workspace', str(ROOT / 'data')]), 1)

    def test_approval_cli_requires_explicit_human_confirmation(self):
        with patch('builtins.print'):
            self.assertEqual(manual_workflow.main(['approve', '--id', '1', '--workspace', str(self.workspace),
                                                  '--source', str(self.source), '--manifest', str(self.workspace / 'image_manifest.csv')]), 1)

    def test_real_pillow_import_composition_and_approval(self):
        # Executed only when image creation is authorized; strict runner skips it.
        from comic_engine.artwork import MockArtworkGenerator
        import io
        entry, metadata = self.ready()
        image = MockArtworkGenerator().generate(entry['story'])
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        self.imports.mkdir()
        (self.imports / '0001.png').write_bytes(buffer.getvalue())
        metadata['artwork_sha256'] = sha(buffer.getvalue())
        (self.imports / '0001.json').write_bytes(packed(metadata))
        processor, store = PillowProcessor(self.config), FileStore()
        result = import_item(self.workspace, self.rows, self.source, '1', self.imports, self.output,
                             self.config, store=store, processor=processor)
        self.assertEqual(result['state'], 'needs_review')
        approve_item(self.workspace, self.rows, self.source, '1', self.imports, self.output,
                     self.config, 'Human test reviewer', store=store, processor=processor)
        self.assertEqual(self.local()['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
