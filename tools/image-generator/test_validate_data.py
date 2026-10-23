import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from validate_data import FIELDS, ROOT, filename_for, run


class SourceImageRecordingTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from unittest.mock import patch
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'source.csv'
        self.original = '家家戶戶,가가호호\r\n一石二鳥,일석이조\r\n'.encode('utf-8-sig')
        self.source.write_bytes(self.original)
        self.output = self.root / 'final'
        self.output.mkdir()
        self.image = self.output / '0001_가가호호.webp'
        # Opaque fixture; real decoder exercised separately with existing final WebP.
        self.image.write_bytes(b'opaque-final')
        import hashlib
        self.digest = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.row = dict(id='1', hanja='家家戶戶', reading='가가호호', filename=self.image.name,
                        status='completed', review_status='approved')
        validator = patch('comic_engine.source_images.validate_webp')
        self.validator = validator.start()
        self.addCleanup(validator.stop)

    def record(self):
        from comic_engine.source_images import record_approved_image
        return record_approved_image(self.source, self.row, self.output, self.digest)

    def test_record_backup_idempotency_and_loader(self):
        self.assertTrue(self.record())
        from validate_data import source_table, load_source
        header, rows = source_table(self.source.read_bytes())
        self.assertEqual(header, ['hanja','reading','image_filename'])
        self.assertEqual(rows, [['家家戶戶','가가호호',self.image.name],['一石二鳥','일석이조','']])
        self.assertEqual(list(self.root.glob('*.bak'))[0].read_bytes(), self.original)
        self.assertEqual([r['id'] for r in load_source(self.source)[0]], ['1','2'])
        after = self.source.read_bytes()
        self.assertFalse(self.record())
        self.assertEqual(self.source.read_bytes(), after)
        self.assertEqual(len(list(self.root.glob('*.bak'))), 1)

    def test_existing_column_and_extra_values_preserved(self):
        self.source.write_text('hanja,reading,note,image_filename\n家家戶戶,가가호호,메모,\n一石二鳥,일석이조,다른값,\n',encoding='utf-8')
        self.record()
        from validate_data import source_table
        header, rows = source_table(self.source.read_bytes())
        self.assertEqual(header,['hanja','reading','note','image_filename'])
        self.assertEqual(rows[1],['一石二鳥','일석이조','다른값',''])
        self.assertFalse(self.source.read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_unapproved_missing_invalid_hash_and_wrong_identity_block(self):
        from comic_engine.common import EngineError
        for changes in ({'status':'needs_review'}, {'review_status':'pending'}, {'id':'2'}):
            old = dict(self.row)
            self.row.update(changes)
            with self.assertRaises(EngineError):
                self.record()
            self.row = old
            self.assertEqual(self.source.read_bytes(),self.original)
        self.digest = 'wrong'
        with self.assertRaises(EngineError):
            self.record()
        self.image.unlink()
        with self.assertRaises(FileNotFoundError):
            self.record()
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_invalid_webp_and_atomic_failure_preserve_source(self):
        from unittest.mock import patch
        from comic_engine.common import EngineError
        self.validator.side_effect = EngineError('invalid WebP')
        with self.assertRaises(EngineError):
            self.record()
        self.validator.side_effect = None
        with patch('comic_engine.source_images.atomic_bytes', side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):
                self.record()
        self.assertEqual(self.source.read_bytes(),self.original)
        self.assertEqual(list(self.root.glob('*.bak'))[0].read_bytes(),self.original)


    def test_conflicting_filename_and_concurrent_writer_block(self):
        from comic_engine.common import EngineError
        from comic_engine.manifest import manifest_lock
        self.source.write_text('hanja,reading,image_filename\n家家戶戶,가가호호,other.webp\n',encoding='utf-8')
        before = self.source.read_bytes()
        with self.assertRaises(EngineError):
            self.record()
        self.assertEqual(self.source.read_bytes(),before)
        self.source.write_bytes(self.original)
        with manifest_lock(self.source):
            with self.assertRaises(EngineError):
                self.record()
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_preview_directory_is_blocked(self):
        from comic_engine.common import EngineError
        self.output = self.root / 'previews'
        self.output.mkdir()
        with self.assertRaises(EngineError):
            self.record()
        self.assertEqual(self.source.read_bytes(),self.original)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / '원본.csv'
        self.manifest = self.root / '제작상태.csv'
        self.report = self.root / '검사.json'

    def write_source(self, rows, encoding='utf-8'):
        with self.source.open('w', encoding=encoding, newline='') as stream:
            csv.writer(stream).writerows(rows)

    def execute(self, count=2):
        return run(self.source, self.manifest, self.report, count)

    def read_manifest(self):
        with self.manifest.open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))

    def test_utf8_and_bom_csv_quoting_and_source_unchanged(self):
        for encoding in ('utf-8', 'utf-8-sig'):
            with self.subTest(encoding=encoding):
                self.manifest.unlink(missing_ok=True)
                self.write_source([['家家戶戶', '가가호호'], ['一石二鳥', '쉼표,독음\n줄바꿈']], encoding)
                original = self.source.read_bytes()
                self.execute()
                rows = self.read_manifest()
                self.assertEqual(rows[1]['reading'], '쉼표,독음\n줄바꿈')
                self.assertEqual(rows[0]['filename'], '0001_가가호호.webp')
                self.assertEqual(self.source.read_bytes(), original)

    def test_duplicates_and_non_four_are_retained(self):
        self.write_source([['家家戶戶', '가가호호'], ['家家戶戶', '가가호호'], ['一石', '일석']])
        report = self.execute(3)
        self.assertEqual(len(self.read_manifest()), 3)
        for field in ('hanja', 'reading'):
            self.assertEqual(report['duplicates'][field]['group_count'], 1)
            self.assertEqual(report['duplicates'][field]['extra_record_count'], 1)
        self.assertEqual(report['non_four_character_count'], 1)
        self.assertEqual([row['id'] for row in self.read_manifest()], ['1', '2', '3'])
        self.assertEqual(len({row['filename'] for row in self.read_manifest()}), 3)

    def test_whitespace_and_empty_are_reported_without_normalizing(self):
        self.write_source([[' 家家戶戶 ', '가 가호호'], ['', '  ']])
        report = self.execute()
        self.assertEqual(report['whitespace_count'], 3)
        self.assertEqual(report['empty_value_count'], 2)
        self.assertEqual(self.read_manifest()[0]['hanja'], ' 家家戶戶 ')

    def test_initial_states_and_rerun_preserves_all_states_and_bytes(self):
        self.write_source([['家家戶戶', '가가호호'], ['一石二鳥', '일석이조']])
        self.execute()
        rows = self.read_manifest()
        self.assertTrue(all(row['status'] == row['review_status'] == 'pending' for row in rows))
        rows[0].update(status='completed', review_status='approved', error_message='기존 기록, 보존')
        rows[1].update(status='failed', review_status='rejected', error_message='실패 기록')
        with self.manifest.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        before = self.manifest.read_bytes()
        self.assertTrue(self.execute()['existing_manifest_preserved'])
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_changed_source_does_not_overwrite_existing_outputs(self):
        self.write_source([['家家戶戶', '가가호호']])
        self.execute(1)
        before = (self.manifest.read_bytes(), self.report.read_bytes())
        self.write_source([['一石二鳥', '일석이조']])
        with self.assertRaises(ValueError):
            self.execute(1)
        self.assertEqual((self.manifest.read_bytes(), self.report.read_bytes()), before)

    def test_invalid_source_columns_and_quoting_fail_without_outputs(self):
        for content in ('한열\n', '가,나,다\n', '"닫히지않음,독음\n'):
            self.source.write_text(content, encoding='utf-8')
            with self.assertRaises((ValueError, csv.Error)):
                self.execute()
            self.assertFalse(self.manifest.exists())
            self.assertFalse(self.report.exists())

    def test_invalid_manifest_is_not_overwritten(self):
        self.write_source([['家家戶戶', '가가호호']])
        for content in ('wrong,header\n', ','.join(FIELDS) + '\n',
                        ','.join(FIELDS) + '\n1,家家戶戶\n'):
            self.manifest.write_text(content, encoding='utf-8')
            with self.assertRaises(ValueError):
                self.execute(1)
            self.assertEqual(self.manifest.read_text(encoding='utf-8'), content)

    def test_windows_filename_characters(self):
        result = filename_for(1, '가<>:"/\\|?*\t. ')
        self.assertEqual(result[:5], '0001_')
        self.assertFalse(any(char in result for char in '<>:"/\\|?*\t'))
        self.assertLess(len(filename_for(1, '가' * 300)), 255)

    def test_count_mismatch_is_reported_and_rows_retained(self):
        self.write_source([['一石二鳥', '일석이조']])
        self.assertFalse(self.execute()['count_matches'])
        self.assertEqual(len(self.read_manifest()), 1)

    def test_output_cannot_replace_source(self):
        self.write_source([['一石二鳥', '일석이조']])
        before = self.source.read_bytes()
        with self.assertRaises(ValueError):
            run(self.source, self.source, self.report)
        self.assertEqual(self.source.read_bytes(), before)

    def test_real_source_695_in_original_order_and_no_images(self):
        self.source = ROOT / 'data/sajaseongeo_final_quiz_v3.csv'
        before = self.source.read_bytes()
        report = self.execute(695)
        self.assertTrue(report['count_matches'])
        self.assertEqual(report['total_count'], 695)
        with self.source.open(encoding='utf-8-sig', newline='') as stream:
            original = list(csv.reader(stream))
        if original and original[0][:2] == ['hanja', 'reading']:
            original = original[1:]
        original = [row[:2] for row in original]
        self.assertEqual([[row['hanja'], row['reading']] for row in self.read_manifest()], original)
        self.assertEqual(json.loads(self.report.read_text(encoding='utf-8'))['total_count'], 695)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertFalse(list(self.root.rglob('*.webp')))


if __name__ == '__main__':
    unittest.main()
