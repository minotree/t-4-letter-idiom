"""Model migration/geometry checks without any image creation or API requests."""
import copy
import inspect
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from openai.resources.images import Images

from comic_engine.artwork import ArtworkGenerator
from comic_engine.common import DEFAULT_CONFIG, EngineError, config_from
from comic_engine.layout import LAYOUT_PENDING, fit_inside, verified_regions
from comic_engine.model_specs import EARLIER, MODERN, image_request, validate_image_settings
from comic_engine.pipeline import process_rows, select_rows
from comic_engine.render import compose


class ModelSettingsTests(unittest.TestCase):
    def setUp(self):
        self.config = config_from()

    def test_default_model_is_pinned_and_live_is_disabled(self):
        self.assertEqual(self.config['image_model'], 'gpt-image-2.5-flare-2026-09-08')
        self.assertFalse(self.config['allow_live'])
        self.assertEqual(validate_image_settings(self.config), (1024, 1536))

    def test_reviewed_model_ids_are_supported(self):
        for model in MODERN | EARLIER:
            self.assertEqual(validate_image_settings(dict(self.config, image_model=model)), (1024, 1536))

    def test_quality_is_model_specific(self):
        for quality in ('low', 'medium', 'high', 'xhigh', 'max', 'auto'):
            validate_image_settings(dict(self.config, image_quality=quality))
        for quality in ('xhigh', 'max', 'standard', 'hd'):
            with self.assertRaises(EngineError):
                validate_image_settings(dict(self.config, image_model='gpt-image-2', image_quality=quality))

    def test_unknown_and_deprecated_models_fail_closed(self):
        for model in ('unreviewed-model', 'gpt-image-1', 'gpt-image-1.5', 'gpt-image-1-mini', 'dall-e-3'):
            with self.assertRaises(EngineError):
                validate_image_settings(dict(self.config, image_model=model))

    def test_supported_custom_sizes_including_final_canvas_ratio(self):
        for size in ('512x1536', '1024x3072', '1536x640', '3840x2160'):
            validate_image_settings(dict(self.config, image_size=size))

    def test_invalid_size_syntax_and_auto_are_rejected(self):
        for size in ('auto', '1024X1536', '1024x1536x4', '0x1536', '-1024x1536', None):
            with self.assertRaises(EngineError):
                validate_image_settings(dict(self.config, image_size=size))

    def test_pixel_edge_and_aspect_constraints(self):
        for size in ('512x512', '4096x2048', '3840x3840', '513x1536', '512x2048'):
            with self.assertRaises(EngineError):
                validate_image_settings(dict(self.config, image_size=size))

    def test_toml_validation_happens_before_any_client(self):
        text = DEFAULT_CONFIG.read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / 'invalid.toml'
            config_path.write_text(text.replace('image_size = "1024x1536"', 'image_size = "511x1536"'), encoding='utf-8')
            with patch('openai.OpenAI', side_effect=AssertionError('No client allowed')):
                with self.assertRaises(EngineError):
                    config_from(config_path)

    def test_adapter_rejects_invalid_model_without_gateway_call(self):
        gateway = Mock()
        with self.assertRaises(EngineError):
            ArtworkGenerator(dict(self.config, image_model='unreviewed'), gateway)
        gateway.call.assert_not_called()

    def test_mutated_settings_are_rechecked_before_request(self):
        config = copy.deepcopy(self.config)
        gateway = Mock()
        adapter = ArtworkGenerator(config, gateway)
        config['image_quality'] = 'hd'
        with self.assertRaises(EngineError):
            adapter.generate({'panels': []})
        gateway.call.assert_not_called()

    def test_request_kwargs_bind_to_installed_sdk_without_calling_it(self):
        request = image_request(self.config, 'text-free illustration')
        inspect.signature(Images.generate).bind(None, **request)
        self.assertEqual(set(request), {'model', 'quality', 'size', 'n', 'output_format', 'prompt'})
        self.assertEqual(request['n'], 1)
        self.assertEqual(request['output_format'], 'png')
        self.assertNotIn('response_format', request)
        self.assertNotIn('input_fidelity', request)

    def test_adapter_passes_documented_kwargs_to_fake_client_only(self):
        fake_create = Mock(return_value=SimpleNamespace(data=[]))
        client = SimpleNamespace(images=SimpleNamespace(generate=fake_create))
        gateway = SimpleNamespace(call=lambda operation, **metadata: operation(client))
        with self.assertRaisesRegex(EngineError, 'invalid image data'):
            ArtworkGenerator(self.config, gateway).generate({'panels': [{'scene': 'Children in a village.'}] * 4})
        kwargs = fake_create.call_args.kwargs
        self.assertEqual(kwargs['model'], self.config['image_model'])
        self.assertEqual(kwargs['size'], '1024x1536')
        self.assertEqual(kwargs['quality'], 'medium')

    def test_verified_regions_cover_whole_sheet_without_discarding_pixels(self):
        doc = {'verified': True, 'artwork_sha256': 'test-hash', 'cut_lines': [0, 310, 750, 1160, 1536]}
        bounds = verified_regions(1024, 1536, doc, 'test-hash')
        self.assertEqual(len(bounds), 4)
        self.assertEqual(sum((r - l) * (b - t) for l, t, r, b in bounds), 1024 * 1536)
        for previous, following in zip(bounds, bounds[1:]):
            self.assertEqual(previous[3], following[1])

    def test_bounds_require_matching_hash_and_human_confirmation(self):
        base = {'verified': True, 'artwork_sha256': 'hash', 'cut_lines': [0, 384, 768, 1152, 1536]}
        for document in (dict(base, verified=False), dict(base, artwork_sha256='other'),
                         dict(base, cut_lines=[1, 384, 768, 1152, 1536]),
                         dict(base, cut_lines=[0, 384, 384, 1152, 1536]),
                         dict(base, cut_lines=[0, 384, 768, 1152]),
                         dict(base, cut_lines=[0, True, 768, 1152, 1536])):
            with self.assertRaises(EngineError):
                verified_regions(1024, 1536, document, 'hash')

    def test_contain_geometry_never_stretches_or_exceeds_target(self):
        for source in ((1024, 384), (1536, 640), (512, 1536), (1024, 100)):
            width, height = fit_inside(source, (508, 202))
            self.assertLessEqual(width, 508)
            self.assertLessEqual(height, 202)
            self.assertLessEqual(abs(width / source[0] - height / source[1]), 1 / min(source))

    def test_resume_selects_only_layout_pending_reviews(self):
        rows = [dict(id='1', status='needs_review', error_message=LAYOUT_PENDING),
                dict(id='2', status='needs_review', error_message=''),
                dict(id='3', status='completed', error_message=''),
                dict(id='4', status='pending', error_message='')]
        self.assertEqual([row['id'] for row in select_rows(rows, 4)], ['4'])
        self.assertEqual([row['id'] for row in select_rows(rows, 4, resume_layout=True)], ['1'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = dict(rows[0], hanja='家家戶戶', reading='가가호호', filename='0001_가가호호.webp', review_status='layout_pending')
            story, art = Mock(), Mock()
            result = process_rows([row], [row], root / 'manifest.csv', root / 'assets', root / 'work',
                                  self.config, None, mock=True, story_generator=story,
                                  artwork_generator=art, resume_layout=True)
            self.assertEqual(result['failed'], 1)
            story.generate.assert_not_called()
            art.generate.assert_not_called()

    def test_live_composition_stops_before_image_allocation_without_bounds(self):
        with patch('comic_engine.render.preflight'), patch('PIL.Image.new', side_effect=AssertionError('No images')) as allocation:
            with self.assertRaisesRegex(EngineError, 'verified panel boundaries'):
                compose(SimpleNamespace(width=1024, height=1536), {}, {}, None, mock=False)
            allocation.assert_not_called()


if __name__ == '__main__':
    unittest.main()
