"""Isolated metadata transaction tests; no API or image generation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from comic_engine.common import ROOT, EngineError, atomic_bytes
from comic_engine.manual import packed, sha, production_packet
from comic_engine.manifest import save_manifest, read_manifest
from comic_engine.approval_v2 import approve_v2
from validate_data import load_source


class ApprovalV2Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root/'source.csv'
        self.source.write_text('家家戶戶,가가호호\n',encoding='utf-8-sig')
        rows,_ = load_source(self.source)
        self.workspace=self.root/'workspace'
        self.workspace.mkdir()
        self.operational=self.root/'manifest.csv'
        save_manifest(self.operational,rows)
        local=copy.deepcopy(rows)
        local[0]['status']='needs_review'
        save_manifest(self.workspace/'image_manifest.csv',local)
        entry=json.loads((ROOT/'data/manual_workflow/catalog.json').read_text(encoding='utf-8'))['items'][0]
        (self.workspace/'catalog.json').write_bytes(packed({'schema_version':1,'items':[entry]}))
        packet,prompt=production_packet(entry,rows[0])
        destination=self.workspace/'prompts/0001'/sha(packed(packet))
        destination.mkdir(parents=True)
        (destination/'production.json').write_bytes(packed(packet))
        (destination/'image_prompt.txt').write_text(prompt,encoding='utf-8',newline='')
        self.imports=self.root/'imports'; self.imports.mkdir()
        (self.imports/'0001.png').write_bytes(b'opaque-original')
        side={'id':'1','hanja':'家家戶戶','reading':'가가호호','identity_confirmed':True,
              'verified':True,'reviewer':'Test reviewer','image_prompt_sha256':packet['image_prompt_sha256'],
              'artwork_sha256':sha(b'opaque-original'),'cut_lines':[0,541,1072,1548,2172]}
        (self.imports/'0001.json').write_bytes(packed(side))
        self.output=self.root/'final'; self.output.mkdir()
        (self.output/rows[0]['filename']).write_bytes(b'opaque-approved-webp')
        self.preview=self.root/'preview.webp'; self.preview.write_bytes(b'opaque-approved-webp')
        self.layout=self.root/'layout.json'
        settings=json.loads((ROOT/'tools/image-generator/layouts/0001_v2.json').read_text(encoding='utf-8'))
        self.layout.write_bytes(packed(settings))
        report=json.loads((ROOT/'assets/previews/0001_layout_v2_centered.json').read_text(encoding='utf-8'))
        report.update(input_sha256=side['artwork_sha256'],output_sha256=sha(self.preview.read_bytes()),
                      packet_sha256=sha(packed(packet)),layout_sha256=sha(packed(settings)))
        report['compression']['bytes']=len(self.preview.read_bytes())
        self.preview.with_suffix('.json').write_bytes(packed(report))
        for name,kwargs in [('comic_engine.approval_v2.PillowProcessor.inspect',{'return_value':(724,2172)}),
                            ('comic_engine.approval_v2.validate_webp',{}),
                            ('comic_engine.source_images.validate_webp',{})]:
            mock=patch(name,**kwargs);mock.start();self.addCleanup(mock.stop)

    def approve(self,**kwargs):
        return approve_v2(self.workspace,self.operational,self.source,'1',self.imports,self.output,
                          self.preview,self.layout,{'allow_live':False},'Test reviewer',confirm=kwargs.get('confirm',True))

    def snapshot(self):
        return [p.read_bytes() for p in (self.source,self.workspace/'image_manifest.csv',self.operational)]

    def test_success_and_duplicate(self):
        self.assertEqual(self.approve()['state'],'completed')
        for path in (self.operational,self.workspace/'image_manifest.csv'):
            row=read_manifest(path,self.source)[0]
            self.assertEqual((row['status'],row['review_status']),('completed','approved'))
        self.assertIn('0001_가가호호.webp',self.source.read_text(encoding='utf-8-sig'))
        before=self.snapshot()
        self.assertTrue(self.approve()['skipped'])
        self.assertEqual(before,self.snapshot())

    def test_hash_mismatch_blocks(self):
        before=self.snapshot()
        (self.output/'0001_가가호호.webp').write_bytes(b'changed')
        with self.assertRaises(EngineError):self.approve()
        self.assertEqual(before,self.snapshot())

    def test_layout_change_blocks(self):
        settings=json.loads(self.layout.read_text(encoding='utf-8'))
        settings['panels'][0]['bubble_width']=200
        self.layout.write_bytes(packed(settings))
        with self.assertRaises(EngineError):self.approve()

    def test_v1_report_blocks(self):
        self.preview.with_suffix('.json').write_bytes(packed({'layout_version':1}))
        with self.assertRaises(EngineError):self.approve()

    def test_explicit_confirmation_required(self):
        before=self.snapshot()
        with self.assertRaises(EngineError):self.approve(confirm=False)
        self.assertEqual(before,self.snapshot())

    def test_csv_failure_leaves_all_three_unchanged_then_recovers(self):
        before=self.snapshot()
        with patch('comic_engine.approval_v2.record_approved_image',side_effect=OSError('CSV failed')):
            with self.assertRaises(OSError):self.approve()
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.approve()['state'],'completed')

    def test_partial_commit_rolls_back_then_retry(self):
        before=self.snapshot()
        failed=False
        def fail_once(path,data):
            nonlocal failed
            if Path(path)==self.workspace/'image_manifest.csv' and not failed:
                failed=True
                raise OSError('manifest replace failed')
            return atomic_bytes(path,data)
        with patch('comic_engine.approval_v2.atomic_bytes',side_effect=fail_once):
            with self.assertRaises(OSError):self.approve()
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.approve()['state'],'completed')

    def test_interrupted_commit_recovers_on_next_run(self):
        before=self.snapshot()
        from comic_engine.approval_v2 import recover
        def interrupted(path,data):
            if Path(path)==self.workspace/'image_manifest.csv':
                raise KeyboardInterrupt()
            return atomic_bytes(path,data)
        # Simulate process termination before the exception handler can roll back.
        with patch('comic_engine.approval_v2.atomic_bytes',side_effect=interrupted), patch('comic_engine.approval_v2.recover') as recovery:
            with self.assertRaises(KeyboardInterrupt):self.approve()
        self.assertNotEqual(before[0],self.source.read_bytes())
        self.assertEqual(self.approve()['state'],'completed')
