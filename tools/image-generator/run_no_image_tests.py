"""Run existing tests without network access or image creation, even in memory.

Image-dependent tests are explicitly skipped, never replaced with passing stubs.
The original test files and production code are not modified.
"""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image
import httpx


# These tests create real temporary images, or write image-named fixtures.
IMAGE_TESTS = {
    'test_final_webp_decode_read_only',  # Decoder test run separately; this runner forbids Image.open.
    'test_blank_panel_and_invalid_webp_are_errors',
    'test_config_changed_checkpoint_fails_without_overwriting_output',
    'test_crash_after_publish_recovers_without_generation',
    'test_existing_untracked_file_is_not_overwritten',
    'test_failure_reason_is_redacted_and_retry_is_explicit',
    'test_interruption_and_resume_reuses_story_checkpoint',
    'test_mock_isolates_manifest_and_output_without_client',
    'test_mock_pipeline_composition_unicode_states_and_approval',
    'test_official_sdk_adapters_with_fake_client_only',
    'test_review_rejects_modified_output',
    'test_size_target_never_forces_unreadable_quality',
    'test_untracked_output_with_identity_prevents_paid_generation',
    'test_real_pillow_import_composition_and_approval',
}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error('Refusing to overwrite an existing report')
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent), pattern='test_*.py')
    tests = list(flatten(suite))
    original = [test for test in tests if test.__class__.__module__ in ('test_engine', 'test_validate_data')
                and test.__class__.__name__ != 'SourceImageRecordingTests']
    additional = [test for test in tests if test.__class__.__module__ in ('test_model_settings', 'test_cost_protection', 'test_manual_workflow', 'test_approval_v2', 'test_id1_preservation', 'test_layout_settings')
                  or (test.__class__.__module__ == 'test_validate_data' and test.__class__.__name__ == 'SourceImageRecordingTests')]
    if len(original) != 40 or len(tests) != len(original) + len(additional):
        parser.error('Test catalog changed: review image-dependency classification before running')
    for test in tests:
        if test._testMethodName in IMAGE_TESTS:
            method = getattr(test, test._testMethodName)
            setattr(test, test._testMethodName, unittest.skip(
                'User prohibited all image creation, including temporary mock images/fixtures')(method))
    violations = []

    def forbidden(operation):
        def guard(*unused_args, **unused_kwargs):
            violations.append(operation)
            raise RuntimeError(f'Forbidden during no-image audit: {operation}')
        return guard

    with ExitStack() as stack:
        for name in ('new', 'open', 'fromarray', 'frombytes', 'frombuffer'):
            stack.enter_context(patch.object(Image, name, side_effect=forbidden('PIL.Image.' + name)))
        stack.enter_context(patch.object(Image.Image, 'save', side_effect=forbidden('PIL.Image.save')))
        stack.enter_context(patch('socket.socket.connect', side_effect=forbidden('socket.connect')))
        stack.enter_context(patch('socket.create_connection', side_effect=forbidden('socket.create_connection')))
        stack.enter_context(patch.object(httpx.Client, 'send', side_effect=forbidden('httpx.send')))
        stack.enter_context(patch.object(httpx.AsyncClient, 'send', side_effect=forbidden('httpx.async_send')))
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))
    report = {
        'original_discovered': len(original), 'additional_discovered': len(additional),
        'discovered': len(tests), 'executed': result.testsRun - len(result.skipped),
        'passed': result.testsRun - len(result.skipped) - len(result.failures) - len(result.errors),
        'skipped_count': len(result.skipped), 'failures': len(result.failures), 'errors': len(result.errors),
        'skipped_tests': [{'id': test.id(), 'reason': reason} for test, reason in result.skipped],
        'forbidden_operation_attempts': violations,
        'all_40_passed': result.wasSuccessful() and not result.skipped,
        'note': 'No image generation, decoding or saving allowed; no API/network calls allowed. Skipped tests are not passes.',
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'skipped_tests'}))
    return 0 if result.wasSuccessful() and not violations else 1


if __name__ == '__main__':
    raise SystemExit(main())
